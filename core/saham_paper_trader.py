"""Anisa's autonomous paper-trading engine — saldo fiktif, kontrol penuh di tangan Anisa.

Beda dari `saham_portfolio.py` punya Bima (manual `!saham buy/sell`): di sini Anisa
sendiri yang eksekusi BUY/SELL tiap tick pakai skor DecisionEngineTool, tanpa nunggu
approval Bima. Track record (untung/rugi real) dicatat ke `saham_history.py` sebagai
bukti valid/nggaknya keputusan dia — bukan window evaluasi buatan dengan tanggal tetap.

Aturan trading (deterministik, biar konsisten & bisa dianalisis):
    - BELUM pegang posisi + skor >= BUY_SCORE_THRESHOLD (STRONG BUY)  -> BUY
    - SUDAH pegang posisi  + skor <= SELL_SCORE_THRESHOLD (STRONG SELL) -> SELL semua
    - Selain itu -> HOLD (tidak ada aksi)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from teams.t9_saham import DecisionEngineTool
from core.saham_scheduler import (
    fetch_snapshot, _is_idx, _is_crypto,
    WATCHLIST_IDX, WATCHLIST_GLOBAL, WATCHLIST_CRYPTO,
)
from core.saham_portfolio import add_position, remove_position, list_positions, aggregate
from core.saham_history import (
    TradeLogEntry,
    get_recent_trades,
    get_today_trades,
    get_trade_summary,
    log_trade,
)

logger = logging.getLogger('bima_core')

MARKET_WATCHLIST: dict[str, list[str]] = {
    "idx": WATCHLIST_IDX,
    "global": WATCHLIST_GLOBAL,
    "crypto": WATCHLIST_CRYPTO,
}

STARTING_CASH: dict[str, float] = {"idx": 10_000_000.0, "global": 1_000.0, "crypto": 500.0}

BUY_SCORE_THRESHOLD = 70   # STRONG BUY band (lihat DecisionEngineTool)
SELL_SCORE_THRESHOLD = 30  # STRONG SELL band
MAX_POSITION_PCT = 0.20    # max 20% kas tersedia per posisi baru
MAX_CONCURRENT_POSITIONS = 5  # per market bucket

CASH_PATH = Path(__file__).parent.parent / "outputs" / "saham_paper_cash.json"

_SCORE_RE = re.compile(r"Skor\s*:\s*(\d+)\s*/\s*100")
_VERDICT_RE = re.compile(r"Keputusan\s*:\s*(.+)")
_PNL_RE = re.compile(r"realized P&L:\s*([+-]?[\d,]+\.?\d*)")


@dataclass(frozen=True)
class TradeResult:
    ticker: str
    market: str
    action: str  # "BUY" | "SELL"
    qty: float
    price: float
    score: int
    verdict: str
    realized_pnl: float | None
    cash_after: float
    equity_after: float


def _load_cash() -> dict[str, float]:
    if CASH_PATH.exists():
        try:
            data = json.loads(CASH_PATH.read_text(encoding="utf-8"))
            return {**STARTING_CASH, **data}
        except Exception as e:
            logger.warning(f"[PAPER TRADER] Cash state korup, reset: {e}")
    return dict(STARTING_CASH)


def _save_cash(cash: dict[str, float]) -> None:
    CASH_PATH.parent.mkdir(parents=True, exist_ok=True)
    CASH_PATH.write_text(json.dumps(cash, indent=2), encoding="utf-8")


def get_cash_balances() -> dict[str, float]:
    """Public accessor buat command `!saham papertrade`."""
    return _load_cash()


def _bucket_of(ticker: str) -> str:
    if _is_idx(ticker):
        return "idx"
    if _is_crypto(ticker):
        return "crypto"
    return "global"


def _parse_decision(decision_text: str) -> tuple[int | None, str]:
    score = None
    m = _SCORE_RE.search(decision_text)
    if m:
        score = int(m.group(1))
    verdict = ""
    m2 = _VERDICT_RE.search(decision_text)
    if m2:
        verdict = m2.group(1).strip()
    return score, verdict


def _extract_realized_pnl(remove_position_msg: str) -> float | None:
    m = _PNL_RE.search(remove_position_msg)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _count_positions_in_bucket(positions: dict, market: str) -> int:
    return sum(1 for ticker, lots in positions.items() if lots and _bucket_of(ticker) == market)


def _compute_equity(market: str, cash: dict[str, float], price_map: dict[str, float]) -> float:
    positions = list_positions(account="paper")
    agg = aggregate(positions)
    value = 0.0
    for ticker, info in agg.items():
        if _bucket_of(ticker) != market:
            continue
        price = price_map.get(ticker, info["avg_price"])
        value += info["qty"] * price
    return cash.get(market, STARTING_CASH[market]) + value


def _log(result: TradeResult) -> None:
    entry = TradeLogEntry(
        ticker=result.ticker, market=result.market, action=result.action,
        qty=result.qty, price=result.price, score=result.score, verdict=result.verdict,
        reasoning=result.verdict, realized_pnl=result.realized_pnl,
        cash_after=result.cash_after, equity_after=result.equity_after,
    )
    log_trade(entry)


def decide_and_trade(symbol: str, price_map: dict[str, float]) -> TradeResult | None:
    """Evaluasi 1 ticker, eksekusi BUY/SELL kalau kriteria kepenuhi. None kalau HOLD/gagal."""
    try:
        decision_text = DecisionEngineTool()._run(symbol)
    except Exception as e:
        logger.warning(f"[PAPER TRADER] Decision gagal {symbol}: {e}")
        return None

    score, verdict = _parse_decision(decision_text)
    if score is None:
        return None

    snap = fetch_snapshot(symbol)
    if not snap:
        return None
    ticker = snap["ticker"]
    price = snap["close"]
    price_map[ticker] = price
    market = _bucket_of(ticker)

    positions = list_positions(account="paper")
    holding = positions.get(ticker, [])
    cash = _load_cash()

    if holding:
        # === Sudah pegang posisi: exit kalau sinyal STRONG SELL ===
        if score <= SELL_SCORE_THRESHOLD:
            qty = sum(lot["qty"] for lot in holding)
            msg = remove_position(ticker, qty, price, account="paper")
            realized_pnl = _extract_realized_pnl(msg)
            cash[market] = cash.get(market, STARTING_CASH[market]) + qty * price
            _save_cash(cash)
            equity = _compute_equity(market, cash, price_map)
            result = TradeResult(
                ticker=ticker, market=market, action="SELL", qty=qty, price=price,
                score=score, verdict=verdict, realized_pnl=realized_pnl,
                cash_after=cash[market], equity_after=equity,
            )
            _log(result)
            return result
        return None

    # === Belum pegang posisi: entry kalau sinyal STRONG BUY ===
    if score >= BUY_SCORE_THRESHOLD:
        bucket_cash = cash.get(market, STARTING_CASH[market])
        if bucket_cash <= 0:
            return None
        if _count_positions_in_bucket(positions, market) >= MAX_CONCURRENT_POSITIONS:
            return None
        budget = bucket_cash * MAX_POSITION_PCT
        qty = budget / price
        if qty <= 0:
            return None
        add_position(ticker, qty, price, account="paper")
        cash[market] = bucket_cash - qty * price
        _save_cash(cash)
        equity = _compute_equity(market, cash, price_map)
        result = TradeResult(
            ticker=ticker, market=market, action="BUY", qty=qty, price=price,
            score=score, verdict=verdict, realized_pnl=None,
            cash_after=cash[market], equity_after=equity,
        )
        _log(result)
        return result

    return None


def run_tick(market: str) -> list[TradeResult]:
    """Evaluasi semua ticker di 1 market bucket, eksekusi trade kalau ada sinyal kuat."""
    watchlist = MARKET_WATCHLIST.get(market, [])
    price_map: dict[str, float] = {}
    results: list[TradeResult] = []
    for symbol in watchlist:
        try:
            result = decide_and_trade(symbol, price_map)
            if result:
                results.append(result)
        except Exception as e:
            logger.error(f"[PAPER TRADER] Tick error {symbol}: {e}", exc_info=True)
    return results


def _fmt_number(value: float, decimals: int = 0) -> str:
    rendered = f"{abs(value):,.{decimals}f}"
    return rendered.replace(",", "_").replace(".", ",").replace("_", ".")


def _fmt_money(value: float, market: str, *, signed: bool = False) -> str:
    prefix = "Rp" if market == "idx" else "$"
    decimals = 0 if market == "idx" else 2
    display_value = round(float(value), decimals)
    if signed and display_value:
        sign = "+" if display_value > 0 else "-"
    else:
        sign = "-" if display_value < 0 else ""
    return f"{sign}{prefix}{_fmt_number(display_value, decimals)}"


def _fmt_percent(value: float) -> str:
    display_value = round(float(value), 2)
    if display_value == 0:
        display_value = 0.0
    return f"{display_value:+.2f}%".replace(".", ",")


def _bucket_snapshot(
    market: str,
    cash: dict[str, float],
    positions: dict[str, dict],
) -> dict:
    bucket_positions = {
        ticker: info
        for ticker, info in positions.items()
        if _bucket_of(ticker) == market
    }
    marked_positions: list[dict] = []
    complete = True
    market_value = 0.0
    cost_basis = 0.0
    for ticker, info in bucket_positions.items():
        try:
            snapshot = fetch_snapshot(ticker)
        except Exception:
            snapshot = None
        if not snapshot or snapshot.get("close") is None:
            complete = False
            continue
        current = float(snapshot["close"])
        value = current * float(info["qty"])
        cost = float(info["total_cost"])
        market_value += value
        cost_basis += cost
        marked_positions.append(
            {
                "ticker": ticker,
                "qty": float(info["qty"]),
                "avg_price": float(info["avg_price"]),
                "current": current,
                "pnl": value - cost,
                "pnl_pct": ((value - cost) / cost * 100) if cost else 0.0,
            }
        )
    bucket_cash = float(cash.get(market, STARTING_CASH[market]))
    equity = bucket_cash + market_value if complete else None
    floating_pnl = market_value - cost_basis if complete else None
    return {
        "cash": bucket_cash,
        "starting_cash": float(STARTING_CASH[market]),
        "equity": equity,
        "floating_pnl": floating_pnl,
        "positions": marked_positions,
        "complete": complete,
    }


def build_account_report(*, include_today_trades: bool = False) -> str:
    """Laporan lengkap rekening V1 aktif tanpa menggabungkan mata uang."""
    cash = _load_cash()
    positions = aggregate(list_positions(account="paper"))
    lines = ["🤖 **DOMPET ANISA — PAPER TRADING**"]

    if include_today_trades:
        trades = get_today_trades()
        lines.extend(["", "**TRANSAKSI HARI INI**"])
        if not trades:
            lines.append("Tidak ada transaksi hari ini.")
        else:
            for trade in trades:
                action = "Beli" if trade["action"] == "BUY" else "Jual"
                lines.append(
                    f"{action} `{trade['ticker']}` {trade['qty']:.4f} "
                    f"@ {_fmt_money(trade['price'], trade['market'])}"
                )

    for market in ("idx", "global", "crypto"):
        bucket = _bucket_snapshot(market, cash, positions)
        summary = get_trade_summary(market)
        lines.extend(
            [
                "",
                f"**{market.upper()}**",
                f"Modal awal: **{_fmt_money(bucket['starting_cash'], market)}**",
                f"Kas tersedia: **{_fmt_money(bucket['cash'], market)}**",
            ]
        )
        if bucket["complete"]:
            equity = float(bucket["equity"])
            net_pnl = equity - float(bucket["starting_cash"])
            net_pct = (
                net_pnl / float(bucket["starting_cash"]) * 100
                if bucket["starting_cash"]
                else 0.0
            )
            total_label = (
                "PROFIT BERSIH TOTAL"
                if net_pnl > 0
                else "RUGI BERSIH TOTAL"
                if net_pnl < 0
                else "HASIL BERSIH TOTAL"
            )
            lines.extend(
                [
                    f"Kekayaan sekarang: **{_fmt_money(equity, market)}**",
                    f"{total_label}: **{_fmt_money(net_pnl, market, signed=True)} "
                    f"({_fmt_percent(net_pct)})**",
                    f"Total profit jual: **"
                    f"{_fmt_money(float(summary['total_profit']), market, signed=True)}**",
                    f"Total rugi jual: **"
                    f"{_fmt_money(float(summary['total_loss']), market, signed=True)}**",
                    f"Profit bersih terealisasi: **"
                    f"{_fmt_money(float(summary['realized_pnl']), market, signed=True)}**",
                    f"Untung/rugi berjalan: **"
                    f"{_fmt_money(float(bucket['floating_pnl']), market, signed=True)}**",
                ]
            )
        else:
            lines.extend(
                [
                    f"{market.upper()} — harga pasar belum lengkap.",
                    "Profit/rugi bersih total belum bisa dihitung.",
                ]
            )

        if not bucket["positions"] and bucket["complete"]:
            lines.append("Posisi terbuka: tidak ada.")
        else:
            for position in bucket["positions"]:
                lines.append(
                    f"`{position['ticker']}` {position['qty']:.4f} @ "
                    f"{_fmt_money(position['avg_price'], market)} → "
                    f"{_fmt_money(position['current'], market)} | "
                    f"{_fmt_money(position['pnl'], market, signed=True)} "
                    f"({_fmt_percent(position['pnl_pct'])})"
                )

    lines.extend(["", "**5 AKTIVITAS TERAKHIR**"])
    recent_trades = get_recent_trades(limit=5)
    if not recent_trades:
        lines.append("Anisa belum melakukan transaksi.")
    else:
        for trade in recent_trades:
            action = "Beli" if trade["action"] == "BUY" else "Jual"
            result = ""
            if trade["action"] == "SELL":
                result = (
                    " | hasil "
                    f"{_fmt_money(float(trade['realized_pnl'] or 0), trade['market'], signed=True)}"
                )
            lines.append(
                f"{action} `{trade['ticker']}` {trade['qty']:.4f} @ "
                f"{_fmt_money(float(trade['price']), trade['market'])}{result}"
            )

    lines.extend(
        [
            "",
            "Catatan: Simulasi ini belum menghitung fee broker dan settlement T+2. "
            "Angka tersebut tidak dibuat-buat.",
        ]
    )
    return "\n".join(lines)


def build_daily_report() -> str:
    """Recap harian dan ringkasan dompet dari satu sumber perhitungan."""
    return build_account_report(include_today_trades=True)
