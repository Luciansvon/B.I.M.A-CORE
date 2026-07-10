"""Portfolio tracking — JSON storage + P&L calculation.

Data shape:
    {
      "BBCA.JK": [{"qty": 1000, "avg_price": 5800, "buy_date": "2026-05-06"}, ...],
      "BTC-USD": [{"qty": 0.05, "avg_price": 75000, "buy_date": "2026-05-06"}],
      ...
    }

Sell pakai FIFO (lot pertama keluar duluan).
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from teams.t9_saham import normalisasi_ticker

logger = logging.getLogger('bima_core')

PORTFOLIO_PATH = Path(__file__).parent.parent / "outputs" / "saham_portfolio.json"
PAPER_PORTFOLIO_PATH = Path(__file__).parent.parent / "outputs" / "saham_paper_portfolio.json"


def _portfolio_path(account: str = "real") -> Path:
    """account: 'real' (posisi manual Bima) atau 'paper' (posisi otonom Anisa)."""
    return PAPER_PORTFOLIO_PATH if account == "paper" else PORTFOLIO_PATH


def _load(account: str = "real") -> dict:
    path = _portfolio_path(account)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"[PORTFOLIO] Korup ({account}), reset: {e}")
            return {}
    return {}


def _save(data: dict, account: str = "real") -> None:
    path = _portfolio_path(account)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def add_position(symbol: str, qty: float, price: float, account: str = "real") -> str:
    """Tambah posisi baru. qty positif. Return pesan status."""
    if qty <= 0 or price <= 0:
        return f"❌ qty & price harus > 0 (qty={qty}, price={price})"
    ticker = normalisasi_ticker(symbol)
    data = _load(account)
    data.setdefault(ticker, []).append({
        "qty": qty,
        "avg_price": price,
        "buy_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    _save(data, account)
    return f"✅ Catat BELI {qty} {ticker} @ {price:,.2f}"


def remove_position(symbol: str, qty: float, price: float, account: str = "real") -> str:
    """Kurangi posisi (FIFO). Return pesan + realized P&L."""
    if qty <= 0:
        return f"❌ qty harus > 0"
    ticker = normalisasi_ticker(symbol)
    data = _load(account)
    if ticker not in data or not data[ticker]:
        return f"❌ Tidak ada posisi {ticker} di portfolio"

    available = sum(l["qty"] for l in data[ticker])
    if qty > available:
        return f"❌ Stok {ticker} hanya {available:g}, tidak cukup untuk jual {qty:g}. Tidak ada perubahan."

    sisa = qty
    realized_pnl = 0.0
    while sisa > 0 and data[ticker]:
        lot = data[ticker][0]
        if lot["qty"] <= sisa:
            realized_pnl += (price - lot["avg_price"]) * lot["qty"]
            sisa -= lot["qty"]
            data[ticker].pop(0)
        else:
            realized_pnl += (price - lot["avg_price"]) * sisa
            lot["qty"] -= sisa
            sisa = 0

    if not data[ticker]:
        del data[ticker]
    _save(data, account)

    sign = "+" if realized_pnl >= 0 else ""
    return f"✅ Catat JUAL {qty:g} {ticker} @ {price:,.2f} | realized P&L: {sign}{realized_pnl:,.2f}"


def list_positions(account: str = "real") -> dict:
    """Return raw portfolio dict (FIFO order intact)."""
    return _load(account)


def aggregate(positions: dict) -> dict:
    """Aggregate per ticker: total_qty, weighted_avg_price, total_cost."""
    out = {}
    for ticker, lots in positions.items():
        total_qty = sum(l["qty"] for l in lots)
        total_cost = sum(l["qty"] * l["avg_price"] for l in lots)
        if total_qty > 0:
            out[ticker] = {
                "qty": total_qty,
                "avg_price": total_cost / total_qty,
                "total_cost": total_cost,
                "lots": len(lots),
            }
    return out


def reset(account: str = "real") -> str:
    path = _portfolio_path(account)
    if path.exists():
        path.unlink()
    return "✅ Portfolio direset. Mulai dari awal."


def parse_qty_price(arg: str) -> tuple[float, float] | None:
    """Parse 'qty@price' → (qty, price). Return None kalau gagal."""
    arg = arg.strip().replace(",", "")
    if "@" not in arg:
        return None
    qty_str, price_str = arg.split("@", 1)
    try:
        return float(qty_str.strip()), float(price_str.strip())
    except ValueError:
        return None
