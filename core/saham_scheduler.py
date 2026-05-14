"""Scheduler buat digest & alert saham + crypto otomatis.

- Digest 2x/hari (08:30 + 16:30 WIB) hari kerja: snapshot watchlist + saran ramah
  pemula + ringkasan eksekutif LLM.
- Alert IDX tiap 30 menit (jam buka), Global tiap jam (jam buka US),
  Crypto tiap 2 jam (24/7).
- Output: Discord channel SAHAM_CHANNEL_ID (split jadi beberapa pesan kalau panjang)
  + Obsidian vault {OBSIDIAN_PATH}/Saham/.
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
import pandas_ta as ta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from langchain_core.messages import HumanMessage, SystemMessage

from teams.t9_saham import normalisasi_ticker, DecisionEngineTool
from core.langgraph_nodes.llm_config import default_llm

logger = logging.getLogger('bima_core')

WIB = ZoneInfo("Asia/Jakarta")

# === Watchlist (3 group) ===
WATCHLIST_IDX = [
    # Banking
    "BBCA", "BBRI", "BMRI", "BBNI", "ARTO", "BRIS",
    # Telco
    "TLKM",
    # Industrial / Auto
    "ASII",
    # Consumer
    "UNVR", "ICBP", "MYOR", "KLBF",
    # Energy / Mining
    "AMMN", "BREN", "MEDC", "ANTM", "ADRO", "INCO", "PGAS",
    # Tech / Internet
    "GOTO",
]
WATCHLIST_GLOBAL = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "META"]
WATCHLIST_CRYPTO = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX"]
WATCHLIST_ALL = WATCHLIST_IDX + WATCHLIST_GLOBAL + WATCHLIST_CRYPTO

# === Paths ===
BASE_DIR = Path(__file__).parent.parent
ALERT_STATE_PATH = BASE_DIR / "outputs" / "saham_alert_state.json"
OBSIDIAN_PATH = Path(os.environ.get("OBSIDIAN_PATH", str(BASE_DIR / "vault")))
SAHAM_VAULT_DIR = OBSIDIAN_PATH / "Saham"

ALERT_COOLDOWN_HOURS = 6
DISCORD_CHUNK_LIMIT = 1900


# === Helpers ===

def _load_alert_state() -> dict:
    if ALERT_STATE_PATH.exists():
        try:
            return json.loads(ALERT_STATE_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[SAHAM SCHEDULER] Alert state korup, reset: {e}")
            return {}
    return {}


def _save_alert_state(state: dict) -> None:
    ALERT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALERT_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _is_idx(ticker: str) -> bool:
    return ticker.endswith(".JK")


def _is_crypto(ticker: str) -> bool:
    return ticker.endswith("-USD")


def _fmt_price(val: float, ticker: str) -> str:
    if _is_idx(ticker):
        return f"Rp{val:,.0f}"
    if _is_crypto(ticker):
        # Adaptif: BTC ~95k → no decimal, SOL ~185 → 2dec, DOGE ~0.4 → 4dec
        if val >= 1000:
            return f"${val:,.0f}"
        if val >= 1:
            return f"${val:,.2f}"
        return f"${val:.4f}"
    return f"${val:,.2f}"


def _short_label(ticker: str) -> str:
    """Display label tanpa suffix .JK / -USD biar pendek di table."""
    if _is_idx(ticker):
        return ticker[:-3]
    if _is_crypto(ticker):
        return ticker[:-4]
    return ticker


# === Snapshot ===

def fetch_snapshot(symbol: str) -> dict | None:
    """Quote + indikator teknikal (RSI, MACD, SMA20, SMA50). Return None kalau gagal."""
    ticker = normalisasi_ticker(symbol)
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="3mo")
        if df.empty or len(df) < 30:
            return None
        info = t.info or {}

        df["RSI"] = ta.rsi(df["Close"], 14)
        macd = ta.macd(df["Close"])
        df = df.join(macd)
        df["SMA20"] = ta.sma(df["Close"], 20)
        df["SMA50"] = ta.sma(df["Close"], 50)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(last["Close"])
        prev_close = float(prev["Close"])
        change_pct = (close - prev_close) / prev_close * 100 if prev_close else 0.0

        def _safe(val):
            return float(val) if val is not None and not pd.isna(val) else None

        rsi = _safe(last.get("RSI"))
        sma20 = _safe(last.get("SMA20"))
        sma50 = _safe(last.get("SMA50"))

        macd_now = float(last.get("MACD_12_26_9", 0) or 0)
        macd_sig_now = float(last.get("MACDs_12_26_9", 0) or 0)
        macd_prev = float(prev.get("MACD_12_26_9", 0) or 0)
        macd_sig_prev = float(prev.get("MACDs_12_26_9", 0) or 0)

        bullish_cross = macd_prev <= macd_sig_prev and macd_now > macd_sig_now
        bearish_cross = macd_prev >= macd_sig_prev and macd_now < macd_sig_now

        return {
            "ticker": ticker,
            "raw_symbol": symbol,
            "label": _short_label(ticker),
            "name": info.get("longName", info.get("shortName", ticker)),
            "close": close,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "rsi": rsi,
            "sma20": sma20,
            "sma50": sma50,
            "volume": int(last.get("Volume", 0) or 0),
            "macd": macd_now,
            "macd_signal": macd_sig_now,
            "bullish_cross": bullish_cross,
            "bearish_cross": bearish_cross,
            "currency": info.get("currency", "USD"),
        }
    except Exception as e:
        logger.warning(f"[SAHAM SCHEDULER] Gagal fetch {ticker}: {e}")
        return None


def detect_signals(snap: dict) -> list[str]:
    signals = []
    if snap.get("rsi") is not None:
        if snap["rsi"] >= 75:
            signals.append("RSI_OVERBOUGHT")
        elif snap["rsi"] <= 25:
            signals.append("RSI_OVERSOLD")
    if abs(snap["change_pct"]) >= 3:
        signals.append("PRICE_SPIKE")
    if snap["bullish_cross"]:
        signals.append("MACD_BULL_CROSS")
    if snap["bearish_cross"]:
        signals.append("MACD_BEAR_CROSS")
    return signals


def signal_emoji(signals: list[str]) -> str:
    if not signals:
        return "—"
    if "RSI_OVERSOLD" in signals or "MACD_BULL_CROSS" in signals:
        return "🟢"
    if "RSI_OVERBOUGHT" in signals or "MACD_BEAR_CROSS" in signals:
        return "🔴"
    if "PRICE_SPIKE" in signals:
        return "⚡"
    return "—"


# === Saran ramah pemula (rule-based) ===

def awam_advice(snap: dict) -> dict:
    """Return {action, level, alasan, edukasi}.
    action: emoji+label simple. level: LOW/MED/HIGH risk. edukasi: 1 line."""
    rsi = snap.get("rsi")
    close = snap["close"]
    sma20 = snap.get("sma20")
    sma50 = snap.get("sma50")
    change = snap["change_pct"]
    bull = snap.get("bullish_cross", False)
    bear = snap.get("bearish_cross", False)

    if sma20 and sma50 and close > sma20 > sma50:
        trend = "uptrend"
    elif sma20 and sma50 and close < sma20 < sma50:
        trend = "downtrend"
    else:
        trend = "sideways"

    r = rsi if rsi is not None else 50  # fallback netral

    # === Priority 1: SELL / HATI-HATI ===
    if r >= 78 and change < -1:
        return {
            "action": "🔴 KURANGI / JUAL", "level": "HIGH",
            "alasan": f"RSI {r:.0f} (kepenuhan) + sudah turun {change:.1f}%.",
            "edukasi": "Saham 'kepanasan' sering koreksi. Pertimbangkan ambil profit.",
        }
    if bear and r > 60:
        return {
            "action": "🔴 KURANGI / JUAL", "level": "HIGH",
            "alasan": f"MACD berbalik turun (bearish cross) + RSI {r:.0f}.",
            "edukasi": "Sinyal momentum berubah ke arah turun. Jaga risiko.",
        }
    if bear and change <= -2:
        return {
            "action": "🔴 KURANGI / JUAL", "level": "HIGH",
            "alasan": f"Bearish cross + harga jatuh {change:.1f}%.",
            "edukasi": "Momentum turun + harga drop tajam = tunggu konfirmasi dasar dulu.",
        }
    if change <= -5:
        return {
            "action": "🔴 HINDARI", "level": "HIGH",
            "alasan": f"Anjlok {change:.1f}% — drop tajam.",
            "edukasi": "Penurunan ekstrem sering disusul ketidakpastian. Tunggu pasar tenang dulu.",
        }
    if r >= 75:
        return {
            "action": "🔴 HATI-HATI", "level": "HIGH",
            "alasan": f"RSI {r:.0f} > 70 = jenuh beli, potensi koreksi.",
            "edukasi": "RSI tinggi = saham mungkin sudah 'mahal' jangka pendek.",
        }
    if change >= 4 and r > 70:
        return {
            "action": "🔴 HATI-HATI (FOMO)", "level": "HIGH",
            "alasan": f"Lompat {change:.1f}% + RSI {r:.0f}.",
            "edukasi": "Lonjakan + RSI ekstrem sering disusul koreksi. Hindari FOMO.",
        }

    # === Priority 2: BUY / LIRIK ===
    if r <= 28:
        return {
            "action": "🟢 LIRIK BELI (DCA)", "level": "MED",
            "alasan": f"RSI {r:.0f} = jenuh jual, potensi pantulan.",
            "edukasi": "Oversold sering disusul rebound. DCA = beli bertahap untuk hindari salah timing.",
        }
    if bull and r < 70:
        return {
            "action": "🟢 LIRIK BELI", "level": "MED",
            "alasan": f"MACD baru golden cross + RSI {r:.0f} (zona aman).",
            "edukasi": "Golden cross = sinyal momentum berubah ke arah naik. Tahap awal trend baru.",
        }
    if change >= 3 and r < 65 and not bear:
        return {
            "action": "🟢 LIRIK BELI", "level": "MED",
            "alasan": f"Naik {change:.1f}% dengan RSI {r:.0f} (belum kepanasan).",
            "edukasi": "Momentum positif + RSI sehat = konfirmasi awal trend naik.",
        }

    # === Priority 3: KUMPULIN PELAN (uptrend sehat) ===
    if trend == "uptrend" and 40 <= r <= 65:
        return {
            "action": "🟢 KUMPULIN PELAN", "level": "LOW",
            "alasan": f"Trend naik + RSI {r:.0f} (zona aman).",
            "edukasi": "Trend naik + RSI moderat = kondisi paling sehat untuk akumulasi bertahap.",
        }
    if trend == "uptrend" and change > 0:
        return {
            "action": "🟢 KUMPULIN PELAN", "level": "LOW",
            "alasan": "Trend naik & masih hijau hari ini.",
            "edukasi": "Akumulasi pelan-pelan di trend naik = strategi paling sederhana untuk pemula.",
        }

    # === Priority 4: HINDARI ===
    if trend == "downtrend" and r > 35:
        return {
            "action": "🔴 HINDARI", "level": "HIGH",
            "alasan": "Trend turun + belum oversold.",
            "edukasi": "Jangan tangkap pisau jatuh. Tunggu pembalikan trend dulu.",
        }
    if bear and r >= 40:
        return {
            "action": "🔴 HINDARI", "level": "MED",
            "alasan": f"MACD berbalik turun + RSI {r:.0f}.",
            "edukasi": "Bearish cross di RSI moderat = momentum mulai memburuk.",
        }

    # === Default ===
    return {
        "action": "🟡 TUNGGU DULU", "level": "MED",
        "alasan": "Belum ada sinyal jelas, pasar sideways.",
        "edukasi": "Saat ragu, lebih aman tunggu konfirmasi arah.",
    }


# === LLM ringkasan eksekutif ===

def llm_executive_summary(snapshots: list[dict], label: str) -> str:
    """1 panggilan LLM untuk narasi 4-6 baris ringkasan kondisi market."""
    try:
        # Kompres data biar prompt hemat token
        groups = {"IDX": [], "GLOBAL": [], "CRYPTO": []}
        for s in snapshots:
            row = (
                f"{s['label']:<6} {s['change_pct']:+.2f}% "
                f"RSI={s['rsi']:.0f}" if s.get("rsi") is not None else f"{s['label']:<6} {s['change_pct']:+.2f}%"
            )
            sig = ",".join(s.get("signals", [])) or "-"
            row = f"{s['label']:<6} {s['change_pct']:+5.2f}% RSI={s['rsi']:.0f} sig=[{sig}]" if s.get("rsi") is not None else f"{s['label']:<6} {s['change_pct']:+5.2f}% sig=[{sig}]"
            if _is_idx(s["ticker"]):
                groups["IDX"].append(row)
            elif _is_crypto(s["ticker"]):
                groups["CRYPTO"].append(row)
            else:
                groups["GLOBAL"].append(row)

        data_block = ""
        for k, rows in groups.items():
            if rows:
                data_block += f"\n[{k}]\n" + "\n".join(rows) + "\n"

        system = (
            "Kamu adalah Anisa, asisten finansial untuk Bima yang masih AWAM di pasar saham/crypto. "
            "Tugasmu bikin RINGKASAN EKSEKUTIF dari snapshot watchlist hari ini, "
            "dalam Bahasa Indonesia yang ramah, hangat, pakai emoji secukupnya. "
            "Maks 5-6 baris. Sebut 1-2 ticker yang menarik (positif/negatif) dengan alasan singkat. "
            "Akhiri dengan 1 saran umum (mis: 'fokus ke trend uptrend dulu', 'wait & see kalau sideways', dll). "
            "JANGAN kasih harga absolut, JANGAN ngarang. JANGAN kasih ajakan investasi spesifik."
        )
        user = f"Snapshot {label}:{data_block}\n\nBuat ringkasan eksekutif 5-6 baris."

        resp = default_llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return resp.content.strip()
    except Exception as e:
        logger.warning(f"[SAHAM SCHEDULER] LLM exec summary gagal: {e}")
        return ""


# === Format helpers ===

GLOSSARY = (
    "📚 *Cheat sheet pemula*: "
    "**RSI** <30 = murah/jenuh jual, >70 = mahal/jenuh beli. "
    "**MACD cross** = sinyal momentum berubah arah. "
    "**SMA20/50** = harga rata2 20/50 hari (acuan trend). "
    "*DYOR — ini bukan ajakan beli/jual.*"
)


def _format_table(snaps: list[dict], group_label: str) -> str:
    if not snaps:
        return ""
    lines = [f"**{group_label}** ({len(snaps)} ticker)"]
    lines.append("```")
    lines.append(f"{'Ticker':<7}{'Harga':>12}{'%':>9}{'RSI':>5}  Saran")
    lines.append("-" * 60)
    for s in snaps:
        rsi_str = f"{s['rsi']:.0f}" if s.get("rsi") is not None else "n/a"
        adv = awam_advice(s)
        action_short = adv["action"]  # already includes emoji
        price_str = _fmt_price(s["close"], s["ticker"])
        lines.append(
            f"{s['label']:<7}{price_str:>12}{s['change_pct']:>+8.2f}%{rsi_str:>5}  {action_short}"
        )
    lines.append("```")
    return "\n".join(lines)


def _format_detail(snaps_with_signal: list[dict]) -> str:
    if not snaps_with_signal:
        return ""
    lines = ["🔍 **Detail Signal Kuat & Saran Lengkap**\n"]
    for s in snaps_with_signal:
        adv = awam_advice(s)
        decision_text = DecisionEngineTool()._run(s["raw_symbol"])
        keputusan, skor = "—", "—"
        for ln in decision_text.splitlines():
            if "Keputusan" in ln:
                keputusan = ln.split(":", 1)[-1].strip()
            elif "Skor" in ln:
                skor = ln.split(":", 1)[-1].strip()
        sig_str = ", ".join(s["signals"])
        lines.append(
            f"**`{s['label']}`** — {_fmt_price(s['close'], s['ticker'])} ({s['change_pct']:+.2f}%)"
        )
        lines.append(f"• Saran: **{adv['action']}** (risk: {adv['level']})")
        lines.append(f"• Alasan: {adv['alasan']}")
        lines.append(f"• Edukasi: _{adv['edukasi']}_")
        lines.append(f"• Sinyal teknikal: {sig_str}")
        lines.append(f"• Decision Engine: **{keputusan}** (skor {skor})")
        lines.append("")
    return "\n".join(lines)


# === Build digest ===

def build_digest(label: str = "Digest") -> dict:
    """Build digest. Return:
    {'messages': list[str], 'markdown': str, 'snapshots': list[dict]}.
    'messages' = list pesan Discord yang siap dikirim berurutan.
    """
    now = datetime.now(WIB)
    snaps = []
    failed = []
    for sym in WATCHLIST_ALL:
        snap = fetch_snapshot(sym)
        if snap:
            snap["signals"] = detect_signals(snap)
            snaps.append(snap)
        else:
            failed.append(sym)

    snaps_idx = [s for s in snaps if _is_idx(s["ticker"])]
    snaps_global = [s for s in snaps if not _is_idx(s["ticker"]) and not _is_crypto(s["ticker"])]
    snaps_crypto = [s for s in snaps if _is_crypto(s["ticker"])]
    snaps_signaled = [s for s in snaps if s["signals"]]

    # === Pesan 1: header + ringkasan eksekutif + tabel IDX ===
    summary = llm_executive_summary(snaps, label)
    msg1_parts = [
        f"📈 **BIMA Saham Digest — {label}**",
        f"🕒 {now.strftime('%A, %d %B %Y · %H:%M WIB')}",
        "",
    ]
    if summary:
        msg1_parts.append("💬 **Ringkasan Anisa:**")
        msg1_parts.append(summary)
        msg1_parts.append("")
    if snaps_idx:
        msg1_parts.append(_format_table(snaps_idx, "🇮🇩 SAHAM IDX"))
    msg1 = "\n".join(msg1_parts)

    # === Pesan 2: Global + Crypto tabel ===
    msg2_parts = []
    if snaps_global:
        msg2_parts.append(_format_table(snaps_global, "🌎 SAHAM GLOBAL"))
        msg2_parts.append("")
    if snaps_crypto:
        msg2_parts.append(_format_table(snaps_crypto, "₿ CRYPTO"))
    msg2 = "\n".join(msg2_parts).strip()

    # === Pesan 3: detail signal kuat + glossary ===
    msg3_parts = []
    detail = _format_detail(snaps_signaled)
    if detail:
        msg3_parts.append(detail)
    else:
        msg3_parts.append("✅ Tidak ada signal kuat hari ini — pasar relatif tenang.")
    msg3_parts.append("")
    msg3_parts.append(GLOSSARY)
    if failed:
        msg3_parts.append(f"\n⚠️ Gagal fetch: {', '.join(failed)}")
    msg3 = "\n".join(msg3_parts)

    messages = [m for m in [msg1, msg2, msg3] if m.strip()]

    # === Markdown utk Obsidian ===
    md_lines = [
        f"# Saham Digest — {label}",
        f"_{now.strftime('%A, %d %B %Y · %H:%M WIB')}_",
        "",
    ]
    if summary:
        md_lines += ["## Ringkasan Eksekutif", "", summary, ""]

    def _md_table(group_snaps, header):
        if not group_snaps:
            return []
        out = [f"## {header}", "", "| Ticker | Harga | % | RSI | Saran | Alasan |", "|---|---|---|---|---|---|"]
        for s in group_snaps:
            adv = awam_advice(s)
            rsi_str = f"{s['rsi']:.1f}" if s.get("rsi") is not None else "n/a"
            out.append(
                f"| {s['label']} | {_fmt_price(s['close'], s['ticker'])} | "
                f"{s['change_pct']:+.2f}% | {rsi_str} | {adv['action']} | {adv['alasan']} |"
            )
        out.append("")
        return out

    md_lines += _md_table(snaps_idx, "🇮🇩 Saham IDX")
    md_lines += _md_table(snaps_global, "🌎 Saham Global")
    md_lines += _md_table(snaps_crypto, "₿ Crypto")

    if snaps_signaled:
        md_lines += ["## Detail Signal Kuat", ""]
        for s in snaps_signaled:
            adv = awam_advice(s)
            md_lines.append(f"### {s['label']} — {s['name']}")
            md_lines.append(f"- Harga: {_fmt_price(s['close'], s['ticker'])} ({s['change_pct']:+.2f}%)")
            if s.get("rsi") is not None:
                md_lines.append(f"- RSI: {s['rsi']:.1f}")
            md_lines.append(f"- Saran: **{adv['action']}** (risk: {adv['level']})")
            md_lines.append(f"- Alasan: {adv['alasan']}")
            md_lines.append(f"- Edukasi: _{adv['edukasi']}_")
            md_lines.append(f"- Sinyal: {', '.join(s['signals'])}")
            md_lines.append("")
            decision = DecisionEngineTool()._run(s["raw_symbol"])
            md_lines.append("```")
            md_lines.append(decision)
            md_lines.append("```")
            md_lines.append("")

    md_lines += ["", "## Glossary", "", GLOSSARY.replace("*", "")]
    if failed:
        md_lines.append(f"\n> ⚠️ Gagal fetch: {', '.join(failed)}")

    return {"messages": messages, "markdown": "\n".join(md_lines), "snapshots": snaps}


def save_to_obsidian(label: str, markdown: str) -> Path | None:
    try:
        SAHAM_VAULT_DIR.mkdir(parents=True, exist_ok=True)
        slug = label.lower().replace(" ", "-")
        now = datetime.now(WIB)
        path = SAHAM_VAULT_DIR / f"{now.strftime('%Y-%m-%d')}-{slug}.md"
        path.write_text(markdown, encoding="utf-8")
        logger.info(f"[SAHAM SCHEDULER] Saved Obsidian: {path}")
        return path
    except Exception as e:
        logger.error(f"[SAHAM SCHEDULER] Gagal save Obsidian: {e}")
        return None


# === Alert scan ===

def scan_alerts(market: str = "all") -> list[dict]:
    if market == "idx":
        watchlist = WATCHLIST_IDX
    elif market == "global":
        watchlist = WATCHLIST_GLOBAL
    elif market == "crypto":
        watchlist = WATCHLIST_CRYPTO
    else:
        watchlist = WATCHLIST_ALL

    state = _load_alert_state()
    now = datetime.now(timezone.utc)
    cooldown = timedelta(hours=ALERT_COOLDOWN_HOURS)

    alerts = []
    for sym in watchlist:
        snap = fetch_snapshot(sym)
        if not snap:
            continue
        signals = detect_signals(snap)
        if not signals:
            continue
        for sig in signals:
            key = f"{snap['ticker']}|{sig}"
            last_iso = state.get(key)
            if last_iso:
                try:
                    last_dt = datetime.fromisoformat(last_iso)
                    if now - last_dt < cooldown:
                        continue
                except Exception:
                    pass
            alerts.append({"ticker": snap["ticker"], "signal": sig, "snap": snap})
            state[key] = now.isoformat()

    if alerts:
        _save_alert_state(state)
    return alerts


def format_alerts(alerts: list[dict]) -> str:
    if not alerts:
        return ""
    now = datetime.now(WIB)
    lines = [f"🚨 **BIMA Saham/Crypto Alert** — {now.strftime('%H:%M WIB')}\n"]
    for a in alerts:
        s = a["snap"]
        emoji = signal_emoji([a["signal"]])
        rsi_str = f"RSI {s['rsi']:.0f}" if s.get("rsi") is not None else "RSI n/a"
        adv = awam_advice(s)
        lines.append(
            f"{emoji} `{s['label']}` — {_fmt_price(s['close'], s['ticker'])} "
            f"({s['change_pct']:+.2f}%) | {rsi_str} | **{a['signal']}**"
        )
        lines.append(f"   ↳ Saran: {adv['action']} — {adv['alasan']}")
    return "\n".join(lines)


# === Discord senders ===

async def _send_chunk(client, channel_id: int, content: str) -> None:
    try:
        ch = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        if ch is None:
            logger.error(f"[SAHAM SCHEDULER] Channel {channel_id} tidak ditemukan")
            return
        if len(content) <= DISCORD_CHUNK_LIMIT:
            await ch.send(content)
        else:
            for i in range(0, len(content), DISCORD_CHUNK_LIMIT):
                await ch.send(content[i:i + DISCORD_CHUNK_LIMIT])
    except Exception as e:
        logger.error(f"[SAHAM SCHEDULER] Gagal kirim Discord: {e}")


async def _send_charts(client, channel_id: int, snaps_signaled: list[dict], max_charts: int = 5) -> None:
    """Generate & kirim chart untuk signal-strong tickers (max N)."""
    if not snaps_signaled:
        return
    try:
        import discord
        from core.saham_chart import make_chart
    except ImportError as e:
        logger.warning(f"[SAHAM SCHEDULER] Chart skip (import): {e}")
        return
    try:
        ch = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        if ch is None:
            return
        for snap in snaps_signaled[:max_charts]:
            path = await asyncio.to_thread(make_chart, snap["raw_symbol"], 60)
            if path:
                try:
                    await ch.send(file=discord.File(str(path)))
                    await asyncio.sleep(0.4)
                except Exception as e:
                    logger.warning(f"[SAHAM SCHEDULER] Gagal kirim chart {snap['ticker']}: {e}")
    except Exception as e:
        logger.error(f"[SAHAM SCHEDULER] _send_charts error: {e}")


async def send_digest(client, label: str) -> None:
    channel_id_str = os.getenv("SAHAM_CHANNEL_ID")
    if not channel_id_str:
        logger.warning("[SAHAM SCHEDULER] SAHAM_CHANNEL_ID belum di-set")
        return
    logger.info(f"[SAHAM SCHEDULER] Building digest: {label}")
    digest = await asyncio.to_thread(build_digest, label)
    channel_id = int(channel_id_str)
    for msg in digest["messages"]:
        await _send_chunk(client, channel_id, msg)
        await asyncio.sleep(0.5)  # rate-limit guard
    # Chart untuk signal-strong tickers
    snaps_signaled = [s for s in digest["snapshots"] if s.get("signals")]
    await _send_charts(client, channel_id, snaps_signaled, max_charts=5)
    save_to_obsidian(label, digest["markdown"])


async def send_alerts(client, market: str = "all") -> None:
    channel_id_str = os.getenv("SAHAM_CHANNEL_ID")
    if not channel_id_str:
        return
    alerts = await asyncio.to_thread(scan_alerts, market)
    if not alerts:
        logger.info(f"[SAHAM SCHEDULER] Scan {market}: no signals")
        return
    text = format_alerts(alerts)
    await _send_chunk(client, int(channel_id_str), text)
    logger.info(f"[SAHAM SCHEDULER] Sent {len(alerts)} alerts ({market})")


_scheduler_started = False


def start_saham_scheduler(client):
    global _scheduler_started
    if _scheduler_started:
        logger.info("[SAHAM SCHEDULER] Already started, skipping")
        return None
    if not os.getenv("SAHAM_CHANNEL_ID"):
        logger.warning("[SAHAM SCHEDULER] SAHAM_CHANNEL_ID belum di-set, scheduler tidak start")
        return None

    scheduler = AsyncIOScheduler(timezone=WIB)
    scheduler.add_job(
        send_digest,
        CronTrigger(hour=8, minute=30, day_of_week="mon-fri", timezone=WIB),
        args=[client, "Digest Pagi"], id="digest_pagi",
    )
    scheduler.add_job(
        send_digest,
        CronTrigger(hour=16, minute=30, day_of_week="mon-fri", timezone=WIB),
        args=[client, "Digest Sore"], id="digest_sore",
    )
    scheduler.add_job(
        send_alerts,
        CronTrigger(minute="*/30", hour="9-15", day_of_week="mon-fri", timezone=WIB),
        args=[client, "idx"], id="alert_idx",
    )
    scheduler.add_job(
        send_alerts,
        CronTrigger(minute=0, hour="22,23,0,1,2,3,4", day_of_week="tue-sat", timezone=WIB),
        args=[client, "global"], id="alert_global",
    )
    # Crypto: 24/7, tiap 2 jam
    scheduler.add_job(
        send_alerts,
        CronTrigger(minute=0, hour="*/2", timezone=WIB),
        args=[client, "crypto"], id="alert_crypto",
    )
    scheduler.start()
    _scheduler_started = True
    logger.info(
        "[SAHAM SCHEDULER] ✅ Started — digest 2x/day + alerts "
        "(IDX 30min, global 1h, crypto 2h 24/7)"
    )
    return scheduler
