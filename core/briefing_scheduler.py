"""Proactive daily briefing scheduler.

Kirim morning briefing ke Discord channel (BRIEFING_CHANNEL_ID) tiap pagi.
Default: weekday jam BRIEFING_HOUR (default 7 WIB), weekend jam 9 WIB.

Opt-in via ENABLE_BRIEFING=true (default off — Bima harus eksplisit aktifin).

Content:
- Greeting + tanggal/jam
- LLM-generated short briefing (motivasi + tip produktivitas + saran agent)
"""
import os
import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from langchain_core.messages import HumanMessage, SystemMessage

from core.langgraph_nodes.llm_config import default_llm

logger = logging.getLogger('bima_core')

WIB = ZoneInfo("Asia/Jakarta")

DISCORD_CHUNK_LIMIT = 1900

# Fallback content kalau LLM call gagal (briefing tetap berangkat)
_FALLBACK_MOTIVATIONS = [
    "Pelan-pelan tapi konsisten lebih jauh daripada cepat tapi sebentar.",
    "Hari ini boleh tidak sempurna, yang penting jalan dulu.",
    "Satu commit hari ini > rencana commit minggu depan.",
    "Bukan soal hasil hari ini, tapi tentang siapa yang lu jadi karena prosesnya.",
    "Kalau bingung, mulai dari yang paling kecil. Selalu jalan.",
]

_FALLBACK_TIPS = [
    "Coba teknik Pomodoro: 25 menit fokus, 5 menit istirahat. Ulangi 4 kali.",
    "Tutup tab yang ga relevan. Otak gak suka multitasking konteks.",
    "Tulis 1 task paling penting hari ini di sticky note. Selesaikan itu dulu.",
    "Kalau stuck > 15 menit, jalan-jalan 5 menit. Bener-bener jalan.",
    "Code review > coding. Review PR sebelum ngoding hari ini.",
]


def _llm_briefing(hari: str, tanggal_str: str, jam_str: str) -> str:
    """1 LLM call generate briefing pagi. Return text 4-6 baris."""
    try:
        system = (
            "Kamu adalah Anisa, asisten AI pribadi Bima. Bima adalah solo dev "
            "yang lagi build B.I.M.A Core (multi-agent AI). "
            "Buat MORNING BRIEFING ramah dan singkat (max 6 baris) untuk Bima pagi ini. "
            "Bahasa Indonesia casual, hangat, kasih energi positif. "
            "Boleh pakai emoji secukupnya. "
            "Format:\n"
            "1. Salam hangat 1 baris\n"
            "2. Motivasi singkat / quote pendek 1-2 baris\n"
            "3. Tip produktivitas / coding 1-2 baris\n"
            "4. Closing ringan 1 baris\n"
            "JANGAN sebut nama agent atau fitur teknikal. Murni daily motivation."
        )
        user = (
            f"Hari ini {hari}, {tanggal_str}, sekarang jam {jam_str} WIB. "
            "Bikin briefing pagi yang fresh dan motivating."
        )
        resp = default_llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        text = resp.content.strip()
        return text if text else ""
    except Exception as e:
        logger.warning(f"[BRIEFING] LLM call gagal, pakai fallback: {e}")
        return ""


def _fallback_briefing(hari: str, tanggal_str: str, jam_str: str) -> str:
    motiv = random.choice(_FALLBACK_MOTIVATIONS)
    tip = random.choice(_FALLBACK_TIPS)
    return (
        f"Selamat pagi Bima! 🌅\n\n"
        f"Hari {hari}, {tanggal_str} — sekarang {jam_str} WIB.\n\n"
        f"💭 _{motiv}_\n\n"
        f"💡 Tip hari ini: {tip}\n\n"
        f"Semoga produktif ya! Anisa standby kapan aja lu butuh."
    )


def build_briefing() -> str:
    """Build full briefing text. LLM call dengan fallback hardcoded."""
    now = datetime.now(WIB)
    hari_list = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    bulan_list = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    hari = hari_list[now.weekday()]
    tanggal_str = f"{now.day} {bulan_list[now.month - 1]} {now.year}"
    jam_str = now.strftime("%H:%M")

    llm_text = _llm_briefing(hari, tanggal_str, jam_str)
    if llm_text:
        # Wrap LLM text dengan header sederhana biar konsisten
        return f"☀️ **Morning Briefing — {hari}, {tanggal_str}**\n\n{llm_text}"
    return _fallback_briefing(hari, tanggal_str, jam_str)


async def _send_briefing(client) -> None:
    channel_id_str = os.environ.get("BRIEFING_CHANNEL_ID")
    if not channel_id_str:
        logger.warning("[BRIEFING] BRIEFING_CHANNEL_ID belum di-set, skip kirim")
        return
    try:
        text = await _build_briefing_async()
        channel_id = int(channel_id_str)
        ch = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        if ch is None:
            logger.error(f"[BRIEFING] Channel {channel_id} tidak ditemukan")
            return
        if len(text) <= DISCORD_CHUNK_LIMIT:
            await ch.send(text)
        else:
            for i in range(0, len(text), DISCORD_CHUNK_LIMIT):
                await ch.send(text[i:i + DISCORD_CHUNK_LIMIT])
        logger.info(f"[BRIEFING] ✅ Sent morning briefing to channel {channel_id}")
    except Exception as e:
        logger.error(f"[BRIEFING] Gagal kirim briefing: {e}", exc_info=True)


async def _build_briefing_async() -> str:
    """LLM invoke is sync; offload ke thread biar gak block event loop."""
    import asyncio
    return await asyncio.to_thread(build_briefing)


_briefing_started = False


def start_briefing_scheduler(client):
    """Start daily briefing scheduler. No-op kalau ENABLE_BRIEFING != true atau channel ga di-set."""
    global _briefing_started
    if _briefing_started:
        logger.info("[BRIEFING] Already started, skipping")
        return None
    if os.environ.get("ENABLE_BRIEFING", "false").lower() != "true":
        logger.info("[BRIEFING] ENABLE_BRIEFING=false, scheduler tidak start")
        return None
    if not os.environ.get("BRIEFING_CHANNEL_ID"):
        logger.warning("[BRIEFING] BRIEFING_CHANNEL_ID belum di-set, scheduler tidak start")
        return None

    weekday_hour = int(os.environ.get("BRIEFING_HOUR", "7"))
    weekend_hour = int(os.environ.get("BRIEFING_HOUR_WEEKEND", "9"))

    scheduler = AsyncIOScheduler(timezone=WIB)
    scheduler.add_job(
        _send_briefing,
        CronTrigger(hour=weekday_hour, minute=0, day_of_week="mon-fri", timezone=WIB),
        args=[client], id="briefing_weekday",
    )
    scheduler.add_job(
        _send_briefing,
        CronTrigger(hour=weekend_hour, minute=0, day_of_week="sat,sun", timezone=WIB),
        args=[client], id="briefing_weekend",
    )
    scheduler.start()
    _briefing_started = True
    logger.info(
        f"[BRIEFING] ✅ Started — weekday {weekday_hour:02d}:00, weekend {weekend_hour:02d}:00 WIB"
    )
    return scheduler
