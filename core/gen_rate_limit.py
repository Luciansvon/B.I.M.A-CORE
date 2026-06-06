"""In-memory rate limiter buat image/video generation per Discord user.

T1-D: extended dengan persistent daily LLM cost tracking via SQLite.
"""
from __future__ import annotations

import os
import sqlite3
import time
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from threading import Lock

logger = logging.getLogger('bima_core')

# (max_count, window_seconds)
_LIMITS = {
    "image": (10, 3600),
    "video": (3, 3600),
}

_store: dict[tuple[str, str], list[float]] = defaultdict(list)
_lock = Lock()


def check_and_consume(user_id: str, mode: str) -> tuple[bool, str]:
    """Return (allowed, error_message). Kalau allowed=True, satu slot dikonsumsi."""
    if mode not in _LIMITS:
        return True, ""
    cap, window = _LIMITS[mode]
    now = time.time()
    key = (str(user_id or "anon"), mode)
    with _lock:
        _store[key] = [t for t in _store[key] if now - t < window]
        if len(_store[key]) >= cap:
            wait_s = int(window - (now - _store[key][0]))
            wait_min = max(1, wait_s // 60)
            return False, f"Rate limit: {mode} max {cap}/jam. Coba lagi {wait_min} menit."
        _store[key].append(now)
    return True, ""


# === T1-D: Persistent daily LLM cost tracker ===

_COST_DB = Path(__file__).parent.parent / "memory" / "cost_tracker.db"
_cost_lock = Lock()


def _ensure_cost_schema() -> None:
    _COST_DB.parent.mkdir(exist_ok=True)
    with sqlite3.connect(str(_COST_DB)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cost (
                user_id TEXT NOT NULL,
                day TEXT NOT NULL,
                cost_usd REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, day)
            )
            """
        )
        conn.commit()


def add_actual_cost(user_id: str, cost_usd: float) -> None:
    """Akumulasi cost actual (dari OpenRouter usage field) per user per hari."""
    if cost_usd <= 0:
        return
    uid = str(user_id or "anon")
    day = datetime.now().strftime("%Y-%m-%d")
    try:
        with _cost_lock:
            _ensure_cost_schema()
            with sqlite3.connect(str(_COST_DB)) as conn:
                conn.execute(
                    """
                    INSERT INTO llm_cost (user_id, day, cost_usd) VALUES (?, ?, ?)
                    ON CONFLICT(user_id, day) DO UPDATE SET cost_usd = cost_usd + excluded.cost_usd
                    """,
                    (uid, day, float(cost_usd)),
                )
                conn.commit()
    except Exception as e:
        logger.warning(f"[cost_tracker] add_actual_cost gagal (non-fatal): {e}")


def check_daily_cost(user_id: str) -> tuple[bool, str]:
    """Return (allowed, error_msg). Allowed=False kalau cost hari ini ≥ DAILY_COST_LIMIT_USD."""
    if os.environ.get("ENABLE_COST_GUARDRAILS", "false").lower() != "true":
        return True, ""
    try:
        limit = float(os.environ.get("DAILY_COST_LIMIT_USD", "2.0"))
    except ValueError:
        limit = 2.0
    uid = str(user_id or "anon")
    day = datetime.now().strftime("%Y-%m-%d")
    try:
        with _cost_lock:
            _ensure_cost_schema()
            with sqlite3.connect(str(_COST_DB)) as conn:
                cur = conn.execute(
                    "SELECT cost_usd FROM llm_cost WHERE user_id = ? AND day = ?",
                    (uid, day),
                )
                row = cur.fetchone()
        cost = float(row[0]) if row else 0.0
        if cost >= limit:
            return False, (
                f"⚠️ Budget LLM harian habis: ${cost:.4f} / ${limit:.2f}. "
                f"Reset besok pagi. Adjust `DAILY_COST_LIMIT_USD` di .env kalau perlu."
            )
        return True, ""
    except Exception as e:
        logger.warning(f"[cost_tracker] check_daily_cost gagal (allow by default): {e}")
        return True, ""


def get_daily_cost(user_id: str) -> float:
    """Get cost hari ini buat reporting. 0.0 kalau ga ada."""
    uid = str(user_id or "anon")
    day = datetime.now().strftime("%Y-%m-%d")
    try:
        with _cost_lock:
            _ensure_cost_schema()
            with sqlite3.connect(str(_COST_DB)) as conn:
                cur = conn.execute(
                    "SELECT cost_usd FROM llm_cost WHERE user_id = ? AND day = ?",
                    (uid, day),
                )
                row = cur.fetchone()
        return float(row[0]) if row else 0.0
    except Exception:
        return 0.0
