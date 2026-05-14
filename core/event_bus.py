"""Thread-safe pub/sub bus untuk event agent → dashboard.
emit() dipanggil dari thread manapun (LangGraph router, CrewAI agent, dst).
Subscriber daftar (loop, asyncio.Queue) saat WebSocket connect — dispatch
via call_soon_threadsafe biar aman lintas-thread.

Sekaligus simpan metrik per-agent (task count, durasi, error) — di-update
otomatis dari event 'agent_state'. Snapshot diakses lewat get_metrics()."""

import asyncio
import logging
import threading
import time
from collections import deque
from datetime import datetime

logger = logging.getLogger('bima_core')

_lock = threading.Lock()
_subscribers = []  # list of (event_loop, asyncio.Queue)

_metrics_lock = threading.Lock()
_metrics: dict[str, dict] = {}  # agent_id -> counters
_started_at = time.time()

_history_lock = threading.Lock()
_history: deque = deque(maxlen=80)  # ring buffer event terakhir buat replay


def _safe_put(q, msg):
    try:
        q.put_nowait(msg)
    except asyncio.QueueFull:
        pass


def _agent_slot(agent: str) -> dict:
    slot = _metrics.get(agent)
    if slot is None:
        slot = {
            "task_count": 0,
            "error_count": 0,
            "total_duration_ms": 0,
            "last_active": None,
            "current_state": "idle",
            "_started_at": None,
        }
        _metrics[agent] = slot
    return slot


def _update_metrics(event_type: str, payload: dict):
    """Update counter agent berdasar event. Dipanggil dari emit() dengan lock dipegang."""
    if event_type != "agent_state":
        return
    agent = payload.get("agent")
    state = payload.get("state")
    if not agent or not state:
        return

    slot = _agent_slot(agent)
    now = time.time()
    slot["last_active"] = datetime.now().isoformat()
    slot["current_state"] = state

    if state == "working" or state == "thinking":
        slot["_started_at"] = now
    elif state == "talking":
        # Task selesai — hitung durasi kalau ada timer
        started = slot.pop("_started_at", None)
        if started:
            slot["total_duration_ms"] += int((now - started) * 1000)
        slot["task_count"] += 1
    elif state == "error":
        slot["error_count"] += 1
        slot["_started_at"] = None


def emit(event_type: str, **payload):
    """Broadcast ke semua subscriber. Aman dipanggil dari sync atau async context."""
    msg = {"type": event_type, "ts": datetime.now().isoformat(), **payload}

    with _metrics_lock:
        _update_metrics(event_type, payload)

    with _history_lock:
        _history.append(msg)

    with _lock:
        subs = list(_subscribers)
    dead = []
    for loop, q in subs:
        try:
            loop.call_soon_threadsafe(_safe_put, q, msg)
        except RuntimeError:
            dead.append((loop, q))
    if dead:
        with _lock:
            for entry in dead:
                if entry in _subscribers:
                    _subscribers.remove(entry)


def get_metrics() -> dict:
    """Snapshot metrik runtime: per-agent + uptime + total events."""
    with _metrics_lock:
        agents = {}
        for name, slot in _metrics.items():
            count = slot["task_count"]
            avg = (slot["total_duration_ms"] // count) if count else 0
            agents[name] = {
                "task_count": count,
                "error_count": slot["error_count"],
                "total_duration_ms": slot["total_duration_ms"],
                "avg_duration_ms": avg,
                "last_active": slot["last_active"],
                "current_state": slot["current_state"],
            }
    with _lock:
        sub_count = len(_subscribers)
    return {
        "uptime_seconds": int(time.time() - _started_at),
        "active_subscribers": sub_count,
        "agents": agents,
    }


def reset_metrics():
    """Reset semua counter (untuk testing)."""
    global _started_at
    with _metrics_lock:
        _metrics.clear()
        _started_at = time.time()
    with _history_lock:
        _history.clear()


def get_recent_events(limit: int = 80) -> list[dict]:
    """Snapshot event terakhir untuk replay ke client baru."""
    with _history_lock:
        if limit >= len(_history):
            return list(_history)
        return list(_history)[-limit:]


def subscribe(loop, q):
    with _lock:
        _subscribers.append((loop, q))
    logger.debug(f"[EVENT_BUS] subscriber added, total={len(_subscribers)}")


def unsubscribe(loop, q):
    with _lock:
        try:
            _subscribers.remove((loop, q))
        except ValueError:
            pass
    logger.debug(f"[EVENT_BUS] subscriber removed, total={len(_subscribers)}")
