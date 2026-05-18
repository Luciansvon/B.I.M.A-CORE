"""Text-to-speech via F5-TTS (Eempostor Indo V2 finetune).
Output .ogg/Opus codec — kompatibel WA voice note (sendAudioAsVoice: true).

Pakai:
    from core.tts import synthesize_voice
    path = await synthesize_voice("Halo Bima, apa kabar?")

Env override:
    TTS_MODEL_PATH  — path atau HF repo ID model F5-TTS Indo (default: Eempostor/F5-TTS-INDO-FINETUNE-V2)
    TTS_REF_AUDIO   — path ke audio referensi untuk voice cloning (wajib untuk F5-TTS)
    TTS_REF_TEXT    — transkrip teks dari audio referensi
    TTS_DEVICE      — "cuda" atau "cpu" (default: "cuda")

Note: F5-TTS load model per request (unload setelah selesai) untuk hemat VRAM.
Model di-download otomatis dari HuggingFace saat pertama kali dipakai (~1.2GB).
Output WAV di-convert ke OGG/Opus via ffmpeg untuk WA voice note compat.

Fallback: kalau f5-tts tidak terinstall atau gagal, otomatis fallback ke edge-tts.
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

_DEFAULT_HF_REPO = "Eempostor/F5-TTS-INDO-FINETUNE-V2"
_DEFAULT_CKPT_FILE = "f5_tts_indo_v2.pt"
_DEFAULT_VOCAB_FILE = "vocab.txt"
_DEFAULT_BASE_MODEL = "F5TTS_v1_Base"  # finetune di-train dari config base ini
_DEFAULT_REF_AUDIO = str(Path(__file__).resolve().parent.parent / "assets" / "tts_ref.wav")
_DEFAULT_REF_TEXT = "Halo, saya Anisa, asisten AI yang siap membantu kamu."

# Cache path hasil download dari HF (dipersist supaya gak re-download tiap call)
_HF_CACHE_DIR = Path(__file__).resolve().parent.parent / "assets" / "f5_tts_cache"


def _ensure_f5_checkpoint() -> tuple[str, str] | None:
    """Download checkpoint + vocab dari HuggingFace kalau belum ada di cache.
    Return (ckpt_path, vocab_path) absolute, atau None kalau gagal."""
    repo = os.environ.get("TTS_HF_REPO", _DEFAULT_HF_REPO)
    ckpt_name = os.environ.get("TTS_CKPT_FILE", _DEFAULT_CKPT_FILE)
    vocab_name = os.environ.get("TTS_VOCAB_FILE", _DEFAULT_VOCAB_FILE)

    _HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        logger.error("[TTS] huggingface_hub belum terinstall")
        return None

    try:
        ckpt_path = hf_hub_download(repo_id=repo, filename=ckpt_name, cache_dir=str(_HF_CACHE_DIR))
        vocab_path = hf_hub_download(repo_id=repo, filename=vocab_name, cache_dir=str(_HF_CACHE_DIR))
        return ckpt_path, vocab_path
    except Exception as e:
        logger.error(f"[TTS] HF download gagal ({repo}): {e}", exc_info=True)
        return None


async def _synthesize_f5(text: str, wav_fp: Path) -> bool:
    """Jalankan F5-TTS inference di thread terpisah (CPU-bound). Return True kalau sukses."""
    ref_audio = os.environ.get("TTS_REF_AUDIO", _DEFAULT_REF_AUDIO)
    ref_text = os.environ.get("TTS_REF_TEXT", _DEFAULT_REF_TEXT)
    device = os.environ.get("TTS_DEVICE", "cuda")
    base_model = os.environ.get("TTS_BASE_MODEL", _DEFAULT_BASE_MODEL)

    def _run():
        try:
            from f5_tts.api import F5TTS
        except ImportError:
            logger.error("[TTS] f5-tts belum terinstall — pip install f5-tts")
            return False

        if not Path(ref_audio).exists():
            logger.error(f"[TTS] TTS_REF_AUDIO tidak ditemukan: {ref_audio}")
            return False

        # Download checkpoint + vocab dari HF (cached setelah first call)
        paths = _ensure_f5_checkpoint()
        if not paths:
            return False
        ckpt_file, vocab_file = paths

        try:
            tts = F5TTS(
                model=base_model,
                ckpt_file=ckpt_file,
                vocab_file=vocab_file,
                device=device,
            )
            tts.infer(
                ref_file=ref_audio,
                ref_text=ref_text,
                gen_text=text,
                file_wave=str(wav_fp),
            )
            # Unload model dari VRAM/RAM setelah selesai (load per request)
            del tts
            try:
                import torch
                if device == "cuda" and torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"[TTS] F5-TTS inference gagal: {e}", exc_info=True)
            return False

    return await asyncio.to_thread(_run)


async def _synthesize_edge_fallback(text: str, mp3_fp: Path) -> bool:
    """Fallback ke edge-tts kalau F5-TTS gagal."""
    try:
        import edge_tts
    except ImportError:
        logger.error("[TTS] edge-tts fallback juga tidak terinstall")
        return False

    voice = os.environ.get("TTS_VOICE", "id-ID-GadisNeural")
    rate = os.environ.get("TTS_RATE", "+0%")
    volume = os.environ.get("TTS_VOLUME", "+0%")
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        await communicate.save(str(mp3_fp))
        return True
    except Exception as e:
        logger.error(f"[TTS] edge-tts fallback gagal: {e}", exc_info=True)
        return False


async def _convert_to_ogg(src: Path, ogg_fp: Path) -> Path:
    """Convert audio ke OGG/Opus. Return ogg_fp kalau sukses, src kalau ffmpeg gagal."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(src),
            "-c:a", "libopus", "-b:a", "32k", "-vbr", "on",
            "-application", "voip", "-frame_duration", "20",
            str(ogg_fp),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        ret = await proc.wait()
        if ret != 0 or not ogg_fp.exists():
            logger.warning(f"[TTS] ffmpeg convert gagal (exit={ret}), fallback ke file asli")
            return src
        src.unlink(missing_ok=True)
        return ogg_fp
    except FileNotFoundError:
        logger.warning("[TTS] ffmpeg tidak ada di PATH — kirim file asli")
        return src


async def synthesize_voice(text: str, slug_hint: str = "anisa") -> Path | None:
    """Generate audio file dari text. Return path .ogg (Opus codec, kompatibel WA voice note).
    Return None kalau gagal. Async — pakai await."""
    text = (text or "").strip()
    if not text:
        return None

    if len(text) > 4500:
        text = text[:4500] + " ... potong di sini."

    ts = int(time.time())
    wav_fp = _OUTPUT_DIR / f"anisa_tts_{slug_hint}_{ts}.wav"
    ogg_fp = _OUTPUT_DIR / f"anisa_tts_{slug_hint}_{ts}.ogg"
    t0 = time.time()

    # Coba F5-TTS dulu, fallback ke edge-tts kalau gagal
    f5_ok = await _synthesize_f5(text, wav_fp)
    if f5_ok and wav_fp.exists():
        result = await _convert_to_ogg(wav_fp, ogg_fp)
    else:
        logger.warning("[TTS] F5-TTS gagal, fallback ke edge-tts")
        mp3_fp = _OUTPUT_DIR / f"anisa_tts_{slug_hint}_{ts}.mp3"
        edge_ok = await _synthesize_edge_fallback(text, mp3_fp)
        if not edge_ok:
            return None
        result = await _convert_to_ogg(mp3_fp, ogg_fp)

    elapsed = time.time() - t0
    size_kb = result.stat().st_size // 1024 if result.exists() else 0
    logger.info(f"[TTS] Synthesized {result.name} ({len(text)} chars → {size_kb} KB, took {elapsed:.1f}s)")

    # Prune old TTS files
    try:
        from core.output_prune import prune_outputs
        prune_outputs(_OUTPUT_DIR, "anisa_tts_*.ogg", keep=20)
        prune_outputs(_OUTPUT_DIR, "anisa_tts_*.wav", keep=5)
        prune_outputs(_OUTPUT_DIR, "anisa_tts_*.mp3", keep=5)
    except Exception:
        pass

    return result if result.exists() else None


def decide_voice_mode(reply_text: str) -> str:
    """Smart filter: 'full' (voice + minimal text) | 'summary' (text + 1-line voice) | 'skip'."""
    text = (reply_text or "").strip()
    if not text:
        return "skip"
    if len(text) <= TTS_FULL_MAX_CHARS:
        return "full"
    return "summary"
