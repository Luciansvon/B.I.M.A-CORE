"""Text-to-speech via edge-tts (Microsoft neural voice).
Output .ogg/Opus codec — kompatibel WA voice note (sendAudioAsVoice: true).

Pakai:
    from core.tts import synthesize_voice
    path = await synthesize_voice("Halo Bima, apa kabar?")

Env override:
    TTS_VOICE   — voice ID Microsoft (default: id-ID-GadisNeural — female Indonesia)
    TTS_RATE    — speed offset, e.g. '+10%' atau '-5%' (default: '+0%')
    TTS_VOLUME  — volume offset (default: '+0%')

Note: edge-tts default output MP3. Untuk WA voice note compat, MP3 di-convert
ke OGG/Opus via ffmpeg (system binary, harus ada di PATH).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger("bima_core")

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
_OUTPUT_DIR.mkdir(exist_ok=True)

# Smart filter — reply text di atas threshold ini skip TTS atau pakai summary
TTS_FULL_MAX_CHARS = 300
TTS_SUMMARY_LINE = "Anisa kirim jawaban lengkap di chat, baca dari teks ya."


async def synthesize_voice(text: str, slug_hint: str = "anisa") -> Path | None:
    """Generate audio file dari text. Return path .ogg (Opus codec, kompatibel WA voice note).
    Return None kalau gagal. Async — pakai await."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        import edge_tts
    except ImportError:
        logger.error("[TTS] edge-tts belum terinstall — pip install edge-tts")
        return None

    voice = os.environ.get("TTS_VOICE", "id-ID-GadisNeural")
    rate = os.environ.get("TTS_RATE", "+0%")
    volume = os.environ.get("TTS_VOLUME", "+0%")

    # edge-tts limit ~5000 char per request — truncate biar gak error
    if len(text) > 4500:
        text = text[:4500] + " ... potong di sini."

    ts = int(time.time())
    mp3_fp = _OUTPUT_DIR / f"anisa_tts_{slug_hint}_{ts}.mp3"
    ogg_fp = _OUTPUT_DIR / f"anisa_tts_{slug_hint}_{ts}.ogg"
    t0 = time.time()
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        await communicate.save(str(mp3_fp))
    except Exception as e:
        logger.error(f"[TTS] edge-tts synthesis gagal: {e}", exc_info=True)
        return None

    # Convert MP3 → OGG/Opus untuk WA voice note compatibility (sendAudioAsVoice)
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(mp3_fp),
            "-c:a", "libopus", "-b:a", "32k", "-vbr", "on",
            "-application", "voip", "-frame_duration", "20",
            str(ogg_fp),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        ret = await proc.wait()
        if ret != 0 or not ogg_fp.exists():
            logger.warning(f"[TTS] ffmpeg convert gagal (exit={ret}), fallback ke .mp3")
            return mp3_fp  # graceful — kirim MP3 jadi audio attachment biasa
        mp3_fp.unlink(missing_ok=True)
    except FileNotFoundError:
        logger.warning("[TTS] ffmpeg gak ada di PATH — fallback ke .mp3 (WA bakal kirim sbg audio attachment, bukan voice note)")
        return mp3_fp

    elapsed = time.time() - t0
    size_kb = ogg_fp.stat().st_size // 1024
    logger.info(f"[TTS] Synthesized {ogg_fp.name} ({len(text)} chars → {size_kb} KB, took {elapsed:.1f}s, voice={voice})")

    # Prune old TTS files (keep 20 dari masing-masing format)
    try:
        from core.output_prune import prune_outputs
        prune_outputs(_OUTPUT_DIR, "anisa_tts_*.ogg", keep=20)
        prune_outputs(_OUTPUT_DIR, "anisa_tts_*.mp3", keep=5)
    except Exception:
        pass

    return ogg_fp


def decide_voice_mode(reply_text: str) -> str:
    """Smart filter: 'full' (voice + minimal text) | 'summary' (text + 1-line voice) | 'skip'."""
    text = (reply_text or "").strip()
    if not text:
        return "skip"
    if len(text) <= TTS_FULL_MAX_CHARS:
        return "full"
    return "summary"
