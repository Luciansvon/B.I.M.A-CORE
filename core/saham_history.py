"""Log historis trade paper-trading Anisa — SQLite, terpisah dari agentmemory/LanceDB.

Data trade (BUY/SELL, skor, realized P&L) itu tabular & butuh query agregat
("gimana akurasi minggu ini?"), bukan similarity search — makanya disimpan sendiri,
bukan di-embed ke RAG atau nyampur ke episodic memory chat biasa.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger('bima_core')

WIB = ZoneInfo("Asia/Jakarta")
DB_PATH = Path(__file__).parent.parent / "memory" / "saham_history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL,
    action TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL NOT NULL,
    score INTEGER,
    verdict TEXT,
    reasoning TEXT,
    realized_pnl REAL,
    cash_after REAL NOT NULL,
    equity_after REAL NOT NULL
)
"""


@dataclass(frozen=True)
class TradeLogEntry:
    ticker: str
    market: str
    action: str  # "BUY" | "SELL"
    qty: float
    price: float
    score: int | None
    verdict: str
    reasoning: str
    realized_pnl: float | None
    cash_after: float
    equity_after: float


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def log_trade(entry: TradeLogEntry) -> None:
    """Simpan 1 trade paper ke history. Gagal-diam (log warning) supaya trading tetap jalan."""
    try:
        conn = _get_conn()
        try:
            conn.execute(
                """INSERT INTO paper_trades
                   (timestamp, ticker, market, action, qty, price, score, verdict,
                    reasoning, realized_pnl, cash_after, equity_after)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(WIB).isoformat(),
                    entry.ticker, entry.market, entry.action, entry.qty, entry.price,
                    entry.score, entry.verdict, entry.reasoning, entry.realized_pnl,
                    entry.cash_after, entry.equity_after,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"[SAHAM HISTORY] Gagal log trade {entry.ticker}: {e}", exc_info=True)


def get_trades_since(since_iso: str, market: str | None = None) -> list[dict]:
    """Semua trade dengan timestamp >= since_iso (ISO string), opsional filter market."""
    conn = _get_conn()
    try:
        if market:
            cur = conn.execute(
                "SELECT * FROM paper_trades WHERE timestamp >= ? AND market = ? ORDER BY timestamp",
                (since_iso, market),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM paper_trades WHERE timestamp >= ? ORDER BY timestamp",
                (since_iso,),
            )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def get_today_trades(market: str | None = None) -> list[dict]:
    """Trade hari ini (WIB), opsional filter market."""
    since = datetime.now(WIB).strftime("%Y-%m-%dT00:00:00")
    return get_trades_since(since, market)


def get_trade_summary(market: str | None = None) -> dict[str, float | int]:
    """Ringkasan realized P&L SELL; BUY tidak dihitung sebagai hasil jual."""
    conn = _get_conn()
    try:
        where = "WHERE market = ?" if market else ""
        params = (market,) if market else ()
        row = conn.execute(
            f"""
            SELECT
                COALESCE(SUM(
                    CASE WHEN action = 'SELL' AND realized_pnl > 0
                    THEN realized_pnl ELSE 0 END
                ), 0) AS total_profit,
                COALESCE(SUM(
                    CASE WHEN action = 'SELL' AND realized_pnl < 0
                    THEN realized_pnl ELSE 0 END
                ), 0) AS total_loss,
                COALESCE(SUM(
                    CASE WHEN action = 'SELL'
                    THEN realized_pnl ELSE 0 END
                ), 0) AS realized_pnl,
                COALESCE(SUM(
                    CASE WHEN action = 'SELL' THEN 1 ELSE 0 END
                ), 0) AS sell_count
            FROM paper_trades
            {where}
            """,
            params,
        ).fetchone()
        return {
            "total_profit": float(row[0]),
            "total_loss": float(row[1]),
            "realized_pnl": float(row[2]),
            "sell_count": int(row[3]),
        }
    finally:
        conn.close()


def get_recent_trades(
    limit: int = 5,
    market: str | None = None,
) -> list[dict]:
    """Trade terbaru, dibatasi agar laporan Discord tetap ringkas."""
    safe_limit = max(0, int(limit))
    conn = _get_conn()
    try:
        if market:
            cur = conn.execute(
                """
                SELECT * FROM paper_trades
                WHERE market = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (market, safe_limit),
            )
        else:
            cur = conn.execute(
                """
                SELECT * FROM paper_trades
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
        columns = [item[0] for item in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()
