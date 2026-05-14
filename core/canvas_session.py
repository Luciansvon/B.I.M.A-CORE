"""Canvas Session — state per-user buat PDF Canvas iterative editing (F4b).

Tiap session simpan PDF spec (sections, metadata, style) di `outputs/canvas/{user_id}.json`.
TTL 1 jam. Per-session asyncio.Lock biar mutasi gak race kalau user kirim 2 msg cepat.

Lifecycle:
  init(user_id, initial_spec)  → bikin session baru
  load(user_id)                → ambil session aktif (None kalau gak ada / expired)
  update(user_id, new_spec)    → overwrite spec (mutasi atomic via lock)
  bump_version(user_id)        → naikin version counter
  close(user_id)                → hapus session file
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("bima_core.canvas")

_CANVAS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "canvas"
_TTL_SECONDS = 60 * 60  # 1 jam

# Lock per user_id, dibuat lazy. Hidup selama proses bot — kalau bot restart,
# lock reset. File-level lock di luar scope MVP.
_locks: dict[str, asyncio.Lock] = {}


def _ensure_dir() -> None:
    _CANVAS_DIR.mkdir(parents=True, exist_ok=True)


def _path_for(user_id: str) -> Path:
    safe = "".join(c for c in str(user_id) if c.isalnum() or c in ("-", "_"))
    if not safe:
        safe = "anon"
    return _CANVAS_DIR / f"{safe}.json"


def get_lock(user_id: str) -> asyncio.Lock:
    """Return asyncio.Lock untuk user_id ini (singleton per proses)."""
    if user_id not in _locks:
        _locks[user_id] = asyncio.Lock()
    return _locks[user_id]


def _now() -> float:
    return time.time()


def has_active(user_id: str) -> bool:
    """True kalau session file ada DAN belum expired. Cheap (mtime check)."""
    path = _path_for(user_id)
    if not path.exists():
        return False
    try:
        age = _now() - path.stat().st_mtime
    except OSError:
        return False
    return age <= _TTL_SECONDS


def load(user_id: str) -> dict | None:
    """Return session dict atau None kalau gak ada / expired / korup."""
    path = _path_for(user_id)
    if not path.exists():
        return None
    try:
        age = _now() - path.stat().st_mtime
        if age > _TTL_SECONDS:
            logger.info(f"[canvas] session user={user_id} expired ({age:.0f}s > {_TTL_SECONDS}s), drop")
            try:
                path.unlink()
            except OSError:
                pass
            return None
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[canvas] load gagal user={user_id}: {e}")
        return None


def init(user_id: str, initial_spec: dict, topic: str = "") -> dict:
    """Bikin session baru, overwrite kalau udah ada. Return session dict."""
    _ensure_dir()
    session = {
        "user_id": str(user_id),
        "topic": topic,
        "version": 1,
        "created_at": _now(),
        "last_modified": _now(),
        "spec": initial_spec,
        "history_summary": [f"v1: initial draft tentang '{topic}'" if topic else "v1: initial draft"],
    }
    path = _path_for(user_id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(session, f, indent=2)
    logger.info(f"[canvas] init session user={user_id} topic={topic!r}")
    return session


def update(user_id: str, new_spec: dict, change_note: str = "") -> dict | None:
    """Overwrite spec. Bump version. Return updated session, None kalau gagal."""
    existing = load(user_id)
    if existing is None:
        return None
    existing["spec"] = new_spec
    existing["version"] += 1
    existing["last_modified"] = _now()
    if change_note:
        existing["history_summary"].append(f"v{existing['version']}: {change_note}")

    path = _path_for(user_id)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
        logger.info(f"[canvas] update session user={user_id} → v{existing['version']}")
        return existing
    except OSError as e:
        logger.error(f"[canvas] update gagal user={user_id}: {e}")
        return None


def close(user_id: str) -> bool:
    """Hapus session file. Return True kalau ada & dihapus."""
    path = _path_for(user_id)
    if path.exists():
        try:
            path.unlink()
            logger.info(f"[canvas] close session user={user_id}")
            return True
        except OSError as e:
            logger.warning(f"[canvas] close gagal user={user_id}: {e}")
    return False


def list_active() -> list[dict]:
    """List semua session aktif (debugging)."""
    if not _CANVAS_DIR.exists():
        return []
    out = []
    for path in _CANVAS_DIR.glob("*.json"):
        try:
            age = _now() - path.stat().st_mtime
            if age <= _TTL_SECONDS:
                with path.open("r", encoding="utf-8") as f:
                    d = json.load(f)
                out.append({
                    "user_id": d.get("user_id"),
                    "topic": d.get("topic"),
                    "version": d.get("version"),
                    "age_min": int(age / 60),
                })
        except Exception:
            pass
    return out
