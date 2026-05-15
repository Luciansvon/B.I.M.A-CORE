"""In-memory rate limiter buat image/video generation per Discord user."""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

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
