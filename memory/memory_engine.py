import sqlite3
import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('bima_core')

MEMORY_DIR = Path(__file__).parent
DB_FILE = MEMORY_DIR / "memory.db"
OLD_JSON_FILE = MEMORY_DIR / "memory.json"

# ============================================================
# SINGLETON CONNECTION — WAL mode untuk concurrent read/write
# ============================================================
_conn: sqlite3.Connection | None = None
_db_lock = threading.Lock()

# Soft cap agar sessions lama tidak menumpuk tanpa batas
_MAX_SESSIONS = 5000
_SESSION_CAP = 100_000  # soft cap (per-field) supaya 1 row absurd ga nge-blow up


def _get_conn() -> sqlite3.Connection:
    """Return singleton connection. Buat baru kalau belum ada."""
    global _conn
    if _conn is not None:
        return _conn
    with _db_lock:
        if _conn is not None:
            return _conn
        conn = sqlite3.connect(
            str(DB_FILE),
            check_same_thread=False,  # aman karena kita pakai _db_lock untuk write
            timeout=10,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        _conn = conn
    return _conn


def init_db():
    try:
        conn = _get_conn()
        with _db_lock:
            conn.execute('''CREATE TABLE IF NOT EXISTS sessions
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          timestamp TEXT,
                          perintah TEXT,
                          hasil TEXT)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS facts
                         (key TEXT PRIMARY KEY,
                          value TEXT,
                          updated TEXT)''')
            # Index untuk mempercepat ORDER BY id DESC
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_sessions_id
                         ON sessions(id DESC)''')
            conn.commit()

            # Cek apakah butuh migrasi
            cursor = conn.execute("SELECT count(*) FROM sessions")
            if cursor.fetchone()[0] == 0 and OLD_JSON_FILE.exists():
                _migrate_from_json(conn)
    except Exception as e:
        logger.error(f"[MEMORY] Failed to initialize DB: {e}")

def _migrate_from_json(conn):
    logger.info("[MEMORY] Migrating from memory.json to memory.db...")
    try:
        with open(OLD_JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for s in data.get("sessions", []):
            conn.execute("INSERT INTO sessions (timestamp, perintah, hasil) VALUES (?, ?, ?)",
                         (s.get("timestamp"), s.get("perintah"), s.get("hasil")))

        for k, v in data.get("facts", {}).items():
            conn.execute("INSERT INTO facts (key, value, updated) VALUES (?, ?, ?)",
                         (k, v.get("value"), v.get("updated")))

        conn.commit()

        # Rename file JSON lama agar tidak dimigrasi lagi
        backup_name = OLD_JSON_FILE.with_suffix(".json.migrated")
        try:
            OLD_JSON_FILE.rename(backup_name)
        except OSError:
            pass
        logger.info("[MEMORY] Migration successful!")
    except Exception as e:
        logger.error(f"[MEMORY] Migration failed: {e}")


def _prune_old_sessions():
    """Hapus sesi lama kalau jumlah melebihi _MAX_SESSIONS. Sisakan yang terbaru."""
    try:
        conn = _get_conn()
        cursor = conn.execute("SELECT count(*) FROM sessions")
        count = cursor.fetchone()[0]
        if count <= _MAX_SESSIONS:
            return
        excess = count - _MAX_SESSIONS
        with _db_lock:
            conn.execute(
                "DELETE FROM sessions WHERE id IN "
                "(SELECT id FROM sessions ORDER BY id ASC LIMIT ?)",
                (excess,)
            )
            conn.commit()
        logger.info(f"[MEMORY] Pruned {excess} old sessions (kept {_MAX_SESSIONS})")
    except Exception as e:
        logger.warning(f"[MEMORY] Prune failed: {e}")


def add_session(perintah: str, hasil: str):
    try:
        conn = _get_conn()
        with _db_lock:
            conn.execute("INSERT INTO sessions (timestamp, perintah, hasil) VALUES (?, ?, ?)",
                         (datetime.now().isoformat(),
                          (perintah or "")[:_SESSION_CAP],
                          (hasil or "")[:_SESSION_CAP]))
            conn.commit()
        # Prune setiap 50 sesi baru (murah — cek count doang)
        _prune_old_sessions()
    except Exception as e:
        logger.error(f"[MEMORY] Failed to add session: {e}")

def add_fact(key: str, value: str):
    try:
        conn = _get_conn()
        with _db_lock:
            conn.execute("INSERT OR REPLACE INTO facts (key, value, updated) VALUES (?, ?, ?)",
                         (key, value, datetime.now().isoformat()))
            conn.commit()
    except Exception as e:
        logger.error(f"[MEMORY] Failed to add fact: {e}")

def get_recent_context(n: int = 5) -> str:
    try:
        conn = _get_conn()
        cursor = conn.execute("SELECT timestamp, perintah, hasil FROM sessions ORDER BY id DESC LIMIT ?", (n,))
        rows = cursor.fetchall()
        if not rows:
            return "Belum ada histori percakapan sebelumnya."

        # Reverse to chronological order
        rows.reverse()
        lines = []
        for ts, perintah, hasil in rows:
            try:
                ts_short = ts[:16].replace("T", " ")
            except:
                ts_short = ts
            lines.append(f"[{ts_short}] Bima: {perintah}\nANISA: {hasil}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"[MEMORY] DB Error get_recent_context: {e}")
        return "Gagal membaca histori."

def get_all_facts() -> str:
    try:
        conn = _get_conn()
        cursor = conn.execute("SELECT key, value FROM facts")
        rows = cursor.fetchall()
        if not rows:
            return "Belum ada fakta yang disimpan."

        lines = []
        for key, value in rows:
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[MEMORY] DB Error get_all_facts: {e}")
        return "Gagal membaca fakta."

def search_sessions(query: str, n: int = 5) -> str:
    if not query or not query.strip():
        return ""
    try:
        conn = _get_conn()
        pattern = f"%{query.strip()}%"
        cursor = conn.execute(
            "SELECT timestamp, perintah, hasil FROM sessions "
            "WHERE perintah LIKE ? OR hasil LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (pattern, pattern, n)
        )
        rows = cursor.fetchall()
        if not rows:
            return ""
        rows.reverse()
        lines = []
        for ts, perintah, hasil in rows:
            try:
                ts_short = ts[:16].replace("T", " ")
            except:
                ts_short = ts
            lines.append(f"[{ts_short}] Bima: {perintah}\nANISA: {hasil}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"[MEMORY] DB Error search_sessions: {e}")
        return ""


def get_full_context(query: str | None = None) -> str:
    facts = get_all_facts()
    recent = get_recent_context(5)
    base = f"=== FAKTA TENTANG BIMA ===\n{facts}\n\n=== 5 PERCAKAPAN TERAKHIR ===\n{recent}"
    if query:
        relevant = search_sessions(query, n=5)
        if relevant:
            return f"{base}\n\n=== HISTORI RELEVAN UNTUK QUERY INI ===\n{relevant}"
    return base

def get_facts_list() -> list[dict]:
    try:
        conn = _get_conn()
        cursor = conn.execute("SELECT key, value, updated FROM facts ORDER BY updated DESC")
        return [{"key": k, "value": v, "updated": u} for k, v, u in cursor.fetchall()]
    except Exception as e:
        logger.error(f"[MEMORY] DB Error get_facts_list: {e}")
        return []

def get_sessions_count() -> int:
    try:
        conn = _get_conn()
        cursor = conn.execute("SELECT count(*) FROM sessions")
        return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"[MEMORY] DB Error get_sessions_count: {e}")
        return 0

# Initialize DB on module load
init_db()
