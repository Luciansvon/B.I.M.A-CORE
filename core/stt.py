"""Speech-to-text via faster-whisper. Singleton model, lazy-loaded on first call.

Pakai:
    from core.stt import transcribe_audio
    text = transcribe_audio("/path/to/voice_note.ogg", language="id")

Env override:
    STT_MODEL_SIZE     — tiny|base|small|medium|large-v3 (default: small)
    STT_COMPUTE_TYPE   — int8|int8_float16|float16|float32 (default: int8 buat CPU efficiency)
    STT_DEVICE         — cpu|cuda (default: cpu)
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger("bima_core")

_MODEL = None
_MODEL_SIZE: str | None = None


def _get_model():
    """Lazy load faster-whisper model. ~390MB download first time (small)."""
    global _MODEL, _MODEL_SIZE
    if _MODEL is not None:
        return _MODEL
    size = os.environ.get("STT_MODEL_SIZE", "small").strip()
    compute = os.environ.get("STT_COMPUTE_TYPE", "int8").strip()
    device = os.environ.get("STT_DEVICE", "cpu").strip()
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        logger.error("[STT] faster-whisper belum terinstall — pip install faster-whisper")
        raise e
    logger.info(f"[STT] Loading model size={size} device={device} compute={compute} (first call download ~390MB kalau model belum ada di cache)")
    t0 = time.time()
    _MODEL = WhisperModel(size, device=device, compute_type=compute)
    _MODEL_SIZE = size
    logger.info(f"[STT] Model ready ({time.time() - t0:.1f}s)")
    return _MODEL


def transcribe_audio(filepath: str, language: str = "id") -> str:
    """Transcribe audio file → text. Return empty string kalau gagal (graceful).

    language: ISO 639-1 code. Default "id" (Indonesia). Pakai "en" buat English,
    atau None buat auto-detect.
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning(f"[STT] File gak ada: {filepath}")
        return ""
    try:
        model = _get_model()
    except Exception:
        return ""
    t0 = time.time()
    try:
        # initial_prompt seed konteks bahasa Indonesia casual + nama domain Bima
        # vad_filter buang silence di awal/akhir (sering jadi sumber misheard)
        # beam_size=8 nambah eksplorasi candidate buat frasa pendek
        segments, info = model.transcribe(
            str(path),
            language=language,
            beam_size=8,
            vad_filter=True,
            initial_prompt=(
                "Ini percakapan WhatsApp dalam Bahasa Indonesia casual. "
                "User namanya Bima, asisten AI namanya Anisa atau BIMA. "
                "Topik bisa: coding, saham, tugas sehari-hari, generate gambar."
            ) if language == "id" else None,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        elapsed = time.time() - t0
        logger.info(
            f"[STT] Transcribed {path.name} "
            f"(audio={info.duration:.1f}s, text={len(text)} chars, took={elapsed:.1f}s, lang={info.language})"
        )
        return text
    except Exception as e:
        logger.error(f"[STT] Transcribe failed {path.name}: {e}", exc_info=True)
        return ""
