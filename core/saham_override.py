"""Manual fundamental override store.

Bima input fundamental dari Stockbit/Ajaib aplikasi sendiri (yfinance ga lengkap
untuk IDX). Override dipakai oleh FundamentalAnalysisTool & DecisionEngineTool
sebagai prioritas atas data yfinance.

Field yang dikenali (mengikuti yfinance):
    per                — trailing PE
    pbv                — price to book
    eps                — earnings per share
    roe                — return on equity (decimal: 0.25 = 25%)
    der                — debt to equity (integer-ish, mis. 180)
    div_yield          — dividend yield (decimal: 0.03 = 3%)
    profit_margin      — decimal
    revenue_growth     — decimal
    earnings_growth    — decimal

Smart parse: nilai yang berakhiran '%' otomatis dibagi 100.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('bima_core')

OVERRIDE_PATH = Path(__file__).parent.parent / "outputs" / "saham_fundamental_override.json"

KNOWN_FIELDS = {
    "per", "pbv", "eps", "roe", "der",
    "div_yield", "profit_margin", "revenue_growth", "earnings_growth",
}

# Mapping ke field yfinance.info (untuk merge)
YF_FIELD_MAP = {
    "per": "trailingPE",
    "pbv": "priceToBook",
    "eps": "trailingEps",
    "roe": "returnOnEquity",
    "der": "debtToEquity",
    "div_yield": "dividendYield",
    "profit_margin": "profitMargins",
    "revenue_growth": "revenueGrowth",
    "earnings_growth": "earningsGrowth",
}


def _load() -> dict:
    if OVERRIDE_PATH.exists():
        try:
            return json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"[OVERRIDE] Korup, reset: {e}")
            return {}
    return {}


def _save(data: dict) -> None:
    OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def parse_value(s: str) -> float | None:
    """Parse '18' / '0.25' / '25%' / '180' → float. None kalau gagal."""
    s = s.strip()
    if not s:
        return None
    pct = False
    if s.endswith("%"):
        pct = True
        s = s[:-1].strip()
    try:
        v = float(s.replace(",", ""))
    except ValueError:
        return None
    if pct:
        v = v / 100.0
    return v


def set_override(ticker: str, fields: dict) -> tuple[bool, str]:
    """fields: {'per': 18, 'roe': 0.25, ...}. Return (ok, msg)."""
    from teams.t9_saham import normalisasi_ticker
    ticker = normalisasi_ticker(ticker)
    invalid = [k for k in fields if k not in KNOWN_FIELDS]
    if invalid:
        return False, f"❌ Field tidak dikenal: {', '.join(invalid)}. Daftar: {sorted(KNOWN_FIELDS)}"

    data = _load()
    existing = data.get(ticker, {})
    existing.update(fields)
    existing["updated_at"] = datetime.now().isoformat(timespec="seconds")
    data[ticker] = existing
    _save(data)
    nice = ", ".join(f"{k}={v}" for k, v in fields.items())
    return True, f"✅ Override `{ticker}` disimpan: {nice}"


def get_override(ticker: str) -> dict:
    """Return overrides dict (sans 'updated_at') atau {} kalau tidak ada."""
    from teams.t9_saham import normalisasi_ticker
    ticker = normalisasi_ticker(ticker)
    data = _load()
    o = data.get(ticker, {})
    return {k: v for k, v in o.items() if k != "updated_at"}


def get_yf_merged_info(ticker: str, info: dict) -> dict:
    """Merge override (priority) ke dict info yfinance. Output dict baru."""
    override = get_override(ticker)
    if not override:
        return info
    merged = dict(info or {})
    for our_field, yf_field in YF_FIELD_MAP.items():
        if our_field in override:
            merged[yf_field] = override[our_field]
    return merged


def clear_override(ticker: str) -> str:
    from teams.t9_saham import normalisasi_ticker
    ticker = normalisasi_ticker(ticker)
    data = _load()
    if ticker in data:
        del data[ticker]
        _save(data)
        return f"✅ Override `{ticker}` dihapus"
    return f"ℹ️ Tidak ada override untuk `{ticker}`"


def list_overrides() -> dict:
    return _load()


def parse_kv_args(tokens: list[str]) -> tuple[dict, list[str]]:
    """Parse ['per=18', 'roe=25%', ...] → ({'per': 18.0, 'roe': 0.25}, errors)."""
    out = {}
    errors = []
    for tok in tokens:
        if "=" not in tok:
            errors.append(f"format salah: {tok!r} (harus key=value)")
            continue
        k, v = tok.split("=", 1)
        k = k.strip().lower()
        parsed = parse_value(v)
        if parsed is None:
            errors.append(f"value tidak valid: {tok!r}")
            continue
        out[k] = parsed
    return out, errors
