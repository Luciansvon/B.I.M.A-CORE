"""Generate chart harga + RSI per ticker. Output PNG ke outputs/charts/."""
import logging
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import yfinance as yf
import pandas_ta as ta

from teams.t9_saham import normalisasi_ticker
from core.api_retry import call_with_retry

logger = logging.getLogger('bima_core')

CHART_DIR = Path(__file__).parent.parent / "outputs" / "charts"


def make_chart(symbol: str, days: int = 60) -> Path | None:
    """Plot harga (line + SMA20/50) + RSI subplot. Return path PNG atau None."""
    ticker = normalisasi_ticker(symbol)
    try:
        df = call_with_retry(lambda: yf.Ticker(ticker).history(period=f"{days * 2}d"), label="yfinance_chart_hist")
        if df.empty or len(df) < 30:
            return None

        df["SMA20"] = ta.sma(df["Close"], 20)
        df["SMA50"] = ta.sma(df["Close"], 50)
        df["RSI"] = ta.rsi(df["Close"], 14)

        # Trim ke `days` terakhir biar chart fokus
        df = df.tail(days)

        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(10, 6), sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )

        # === Top: harga + SMA ===
        ax1.plot(df.index, df["Close"], color="#2563eb", linewidth=1.6, label="Close")
        if df["SMA20"].notna().any():
            ax1.plot(df.index, df["SMA20"], color="#f59e0b", linewidth=1, alpha=0.8, label="SMA20")
        if df["SMA50"].notna().any():
            ax1.plot(df.index, df["SMA50"], color="#ef4444", linewidth=1, alpha=0.8, label="SMA50")

        last_close = df["Close"].iloc[-1]
        first_close = df["Close"].iloc[0]
        change_pct = (last_close - first_close) / first_close * 100
        title_color = "#16a34a" if change_pct >= 0 else "#dc2626"
        ax1.set_title(
            f"{ticker} — last {df['Close'].iloc[-1]:,.2f}  ({change_pct:+.2f}% in {days}d)",
            fontsize=12, color=title_color, fontweight="bold",
        )
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc="upper left", fontsize=8)
        ax1.set_ylabel("Harga")

        # === Bottom: RSI ===
        ax2.plot(df.index, df["RSI"], color="#7c3aed", linewidth=1.4)
        ax2.axhline(70, color="#dc2626", linestyle="--", linewidth=0.8, alpha=0.6)
        ax2.axhline(30, color="#16a34a", linestyle="--", linewidth=0.8, alpha=0.6)
        ax2.fill_between(df.index, 70, 100, color="#dc2626", alpha=0.08)
        ax2.fill_between(df.index, 0, 30, color="#16a34a", alpha=0.08)
        ax2.set_ylim(0, 100)
        ax2.set_ylabel("RSI(14)")
        ax2.grid(True, alpha=0.3)

        # X-axis format
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        fig.autofmt_xdate(rotation=30)

        plt.tight_layout()
        CHART_DIR.mkdir(parents=True, exist_ok=True)
        path = CHART_DIR / f"{ticker.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.png"
        fig.savefig(path, dpi=110, bbox_inches="tight")
        plt.close(fig)
        return path
    except Exception as e:
        logger.warning(f"[SAHAM CHART] Gagal generate chart {ticker}: {e}")
        return None
