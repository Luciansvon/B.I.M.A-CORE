"""Discord !saham command router.

Subcommands:
    !saham help                              — list commands
    !saham now                               — trigger digest manual
    !saham idx | global | crypto             — mini digest per group
    !saham watchlist                         — list watchlist saat ini
    !saham <TICKER>                          — laporan single ticker (snapshot + saran + chart)
    !saham chart <TICKER> [days]             — chart only
    !saham buy <TICKER> <qty>@<price>        — catat beli
    !saham sell <TICKER> <qty>@<price>       — catat jual (FIFO)
    !saham portfolio                         — list holdings + P&L
    !saham portfolio reset                   — reset portfolio (konfirmasi via 'reset confirm')
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import discord

from core.saham_scheduler import (
    fetch_snapshot, awam_advice, detect_signals, signal_emoji,
    build_digest, _format_table, _fmt_price, _is_idx, _is_crypto,
    WATCHLIST_IDX, WATCHLIST_GLOBAL, WATCHLIST_CRYPTO, WATCHLIST_ALL,
    GLOSSARY,
)
from core.saham_chart import make_chart
from core.saham_portfolio import (
    add_position, remove_position, list_positions, aggregate, reset, parse_qty_price,
)
from core.saham_override import (
    set_override, clear_override, list_overrides, parse_kv_args, KNOWN_FIELDS,
)
from teams.t9_saham import normalisasi_ticker, DecisionEngineTool

logger = logging.getLogger('bima_core')

HELP_TEXT = """📈 **`!saham` — Daftar Perintah**
```
!saham help                       → tampilkan ini
!saham now                        → digest lengkap sekarang
!saham idx | global | crypto      → mini-digest per group
!saham watchlist                  → daftar saham yg dipantau
!saham <TICKER>                   → laporan 1 ticker (mis. !saham BBCA)
!saham chart <TICKER> [days]      → chart 1 ticker (default 60d)
!saham buy <TICKER> <qty>@<price> → catat beli (mis. !saham buy BBCA 100@5800)
!saham sell <TICKER> <qty>@<price> → catat jual (FIFO)
!saham portfolio                  → list holdings + P&L
!saham portfolio reset confirm    → hapus semua holdings
!saham set <TICKER> <field>=<v> ...→ override fundamental manual
!saham unset <TICKER>             → hapus override 1 ticker
!saham overrides                  → list semua override
```
*IDX: qty = jumlah saham (1 lot = 100 saham). Crypto: qty = jumlah coin (boleh desimal).*
*Override field: per, pbv, eps, roe, der, div_yield, profit_margin, revenue_growth, earnings_growth.*
*Value bisa pakai % (mis. `roe=25%` = 0.25).*
"""


async def _build_single_ticker_report(symbol: str) -> tuple[str, Path | None]:
    """Return (text, chart_path)."""
    snap = await asyncio.to_thread(fetch_snapshot, symbol)
    if not snap:
        return f"❌ Ticker `{symbol}` tidak ditemukan / data kurang.", None

    snap["signals"] = detect_signals(snap)
    adv = awam_advice(snap)
    decision_text = await asyncio.to_thread(DecisionEngineTool()._run, symbol)
    keputusan, skor = "—", "—"
    for ln in decision_text.splitlines():
        if "Keputusan" in ln:
            keputusan = ln.split(":", 1)[-1].strip()
        elif "Skor" in ln:
            skor = ln.split(":", 1)[-1].strip()

    rsi_str = f"{snap['rsi']:.1f}" if snap.get("rsi") is not None else "n/a"
    sma20 = snap.get("sma20")
    sma50 = snap.get("sma50")
    sig_str = ", ".join(snap["signals"]) if snap["signals"] else "—"

    lines = [
        f"📊 **{snap['name']}** (`{snap['ticker']}`)",
        f"💰 Harga: **{_fmt_price(snap['close'], snap['ticker'])}** ({snap['change_pct']:+.2f}%)",
        f"📈 RSI(14): **{rsi_str}**" + (f" · SMA20: {sma20:,.2f} · SMA50: {sma50:,.2f}" if sma20 and sma50 else ""),
        f"🚦 Sinyal: {sig_str}",
        "",
        f"🤝 **Saran Anisa**: {adv['action']} (risk: {adv['level']})",
        f"   ↳ Alasan: {adv['alasan']}",
        f"   ↳ Edukasi: _{adv['edukasi']}_",
        "",
        f"⚖️ **Decision Engine**: {keputusan} (skor {skor})",
        "",
        GLOSSARY,
    ]
    text = "\n".join(lines)

    chart_path = await asyncio.to_thread(make_chart, symbol, 60)
    return text, chart_path


async def _build_mini_digest(group: str) -> str:
    if group == "idx":
        watchlist = WATCHLIST_IDX
        header = "🇮🇩 SAHAM IDX"
    elif group == "global":
        watchlist = WATCHLIST_GLOBAL
        header = "🌎 SAHAM GLOBAL"
    elif group == "crypto":
        watchlist = WATCHLIST_CRYPTO
        header = "₿ CRYPTO"
    else:
        return f"❌ Group tidak dikenal: {group}"

    snaps = []
    for sym in watchlist:
        s = await asyncio.to_thread(fetch_snapshot, sym)
        if s:
            s["signals"] = detect_signals(s)
            snaps.append(s)
    if not snaps:
        return f"❌ Gagal fetch data {group}"

    now = datetime.now()
    lines = [
        f"📈 **Mini Digest — {header}**",
        f"🕒 {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        _format_table(snaps, header),
    ]
    return "\n".join(lines)


async def _build_portfolio_report() -> str:
    positions = list_positions()
    if not positions:
        return "📭 Portfolio kosong. Pakai `!saham buy <TICKER> <qty>@<price>` untuk mulai."

    agg = aggregate(positions)
    lines = ["💼 **Portfolio Bima**\n"]
    lines.append("```")
    lines.append(f"{'Ticker':<10}{'Qty':>10}{'Avg':>12}{'Now':>12}{'P&L%':>8}")
    lines.append("-" * 55)

    total_cost = 0.0
    total_value = 0.0
    for ticker, info in agg.items():
        snap = await asyncio.to_thread(fetch_snapshot, ticker)
        if not snap:
            current = info["avg_price"]
            now_str = "n/a"
        else:
            current = snap["close"]
            now_str = _fmt_price(current, ticker)
        cost = info["total_cost"]
        value = current * info["qty"]
        pnl_pct = (current - info["avg_price"]) / info["avg_price"] * 100 if info["avg_price"] else 0
        total_cost += cost
        total_value += value
        lines.append(
            f"{ticker:<10}{info['qty']:>10.4f}{_fmt_price(info['avg_price'], ticker):>12}"
            f"{now_str:>12}{pnl_pct:>+7.2f}%"
        )
    lines.append("-" * 55)
    total_pnl = total_value - total_cost
    total_pct = (total_pnl / total_cost * 100) if total_cost else 0
    lines.append(f"{'TOTAL':<10}{'':>10}{total_cost:>12,.0f}{total_value:>12,.0f}{total_pct:>+7.2f}%")
    lines.append("```")
    sign = "+" if total_pnl >= 0 else ""
    lines.append(f"💰 Unrealized P&L: **{sign}{total_pnl:,.2f}** ({total_pct:+.2f}%)")
    lines.append("\n*Harga sekarang dari yfinance. Mata uang dasar mengikuti ticker (Rp untuk IDX, $ untuk global/crypto).*")
    return "\n".join(lines)


async def handle_saham_command(message, args: str, bot_client=None) -> bool:
    """Process !saham command. Return True kalau ditangani (caller harus return)."""
    args = args.strip()
    if not args or args.lower() in {"help", "?", "-h", "--help"}:
        await message.reply(HELP_TEXT)
        return True

    parts = args.split()
    sub = parts[0].lower()
    rest = parts[1:] if len(parts) > 1 else []

    try:
        # === now / digest manual ===
        if sub == "now":
            await message.reply("⏳ *Anisa lagi build digest manual...*")
            digest = await asyncio.to_thread(build_digest, "Manual (on-demand)")
            for msg in digest["messages"]:
                if len(msg) <= 1900:
                    await message.channel.send(msg)
                else:
                    for i in range(0, len(msg), 1900):
                        await message.channel.send(msg[i:i + 1900])
                await asyncio.sleep(0.4)
            return True

        # === mini digest ===
        if sub in {"idx", "global", "crypto"}:
            text = await _build_mini_digest(sub)
            for i in range(0, len(text), 1900):
                await message.channel.send(text[i:i + 1900])
            return True

        # === watchlist ===
        if sub == "watchlist":
            text = (
                f"📋 **Watchlist Anisa**\n"
                f"🇮🇩 IDX ({len(WATCHLIST_IDX)}): {', '.join(WATCHLIST_IDX)}\n"
                f"🌎 Global ({len(WATCHLIST_GLOBAL)}): {', '.join(WATCHLIST_GLOBAL)}\n"
                f"₿ Crypto ({len(WATCHLIST_CRYPTO)}): {', '.join(WATCHLIST_CRYPTO)}\n"
                f"Total: **{len(WATCHLIST_ALL)}** ticker"
            )
            await message.reply(text)
            return True

        # === chart only ===
        if sub == "chart":
            if not rest:
                await message.reply("Format: `!saham chart <TICKER> [days]`")
                return True
            ticker = rest[0].upper()
            days = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 60
            await message.reply(f"📊 Generating chart {ticker} ({days}d)...")
            path = await asyncio.to_thread(make_chart, ticker, days)
            if path:
                await message.channel.send(file=discord.File(str(path)))
            else:
                await message.reply(f"❌ Gagal generate chart {ticker}")
            return True

        # === buy / sell ===
        if sub == "buy":
            if len(rest) < 2:
                await message.reply("Format: `!saham buy <TICKER> <qty>@<price>`")
                return True
            ticker = rest[0].upper()
            parsed = parse_qty_price(" ".join(rest[1:]))
            if not parsed:
                await message.reply("❌ Format qty@price salah. Contoh: `100@5800`")
                return True
            qty, price = parsed
            await message.reply(add_position(ticker, qty, price))
            return True

        if sub == "sell":
            if len(rest) < 2:
                await message.reply("Format: `!saham sell <TICKER> <qty>@<price>`")
                return True
            ticker = rest[0].upper()
            parsed = parse_qty_price(" ".join(rest[1:]))
            if not parsed:
                await message.reply("❌ Format qty@price salah. Contoh: `50@6200`")
                return True
            qty, price = parsed
            await message.reply(remove_position(ticker, qty, price))
            return True

        # === fundamental override ===
        if sub == "set":
            if len(rest) < 2:
                await message.reply(
                    "Format: `!saham set <TICKER> <field>=<value> ...`\n"
                    f"Field: {', '.join(sorted(KNOWN_FIELDS))}\n"
                    "Contoh: `!saham set BBCA per=18 pbv=2.5 roe=25%`"
                )
                return True
            ticker = rest[0].upper()
            kvs, errors = parse_kv_args(rest[1:])
            if errors:
                await message.reply("❌ " + " | ".join(errors))
                return True
            if not kvs:
                await message.reply("❌ Tidak ada field valid")
                return True
            ok, msg = set_override(ticker, kvs)
            await message.reply(msg)
            return True

        if sub == "unset":
            if not rest:
                await message.reply("Format: `!saham unset <TICKER>`")
                return True
            await message.reply(clear_override(rest[0].upper()))
            return True

        if sub == "overrides":
            data = list_overrides()
            if not data:
                await message.reply("📭 Belum ada override fundamental.")
                return True
            lines = ["📝 **Override fundamental aktif:**\n"]
            for ticker, fields in data.items():
                updated = fields.get("updated_at", "?")[:16]
                vals = ", ".join(f"{k}={v}" for k, v in fields.items() if k != "updated_at")
                lines.append(f"• `{ticker}` — {vals}  _(updated {updated})_")
            await message.reply("\n".join(lines))
            return True

        # === portfolio ===
        if sub == "portfolio":
            if rest and rest[0].lower() == "reset":
                if len(rest) >= 2 and rest[1].lower() == "confirm":
                    await message.reply(reset())
                else:
                    await message.reply(
                        "⚠️ Mau hapus SEMUA holdings? Ketik `!saham portfolio reset confirm`"
                    )
                return True
            await message.reply("⏳ *Hitung P&L portfolio...*")
            text = await _build_portfolio_report()
            for i in range(0, len(text), 1900):
                await message.channel.send(text[i:i + 1900])
            return True

        # === single ticker (fallback) ===
        ticker_input = sub.upper()
        await message.reply(f"⏳ *Analisis `{ticker_input}`...*")
        text, chart_path = await _build_single_ticker_report(ticker_input)
        for i in range(0, len(text), 1900):
            await message.channel.send(text[i:i + 1900])
        if chart_path:
            await message.channel.send(file=discord.File(str(chart_path)))
        return True

    except Exception as e:
        logger.error(f"[SAHAM CMD] Error '{args}': {e}", exc_info=True)
        try:
            await message.reply(f"❌ Error: `{e}`")
        except Exception:
            pass
        return True
