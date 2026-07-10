"""Text-to-speech via F5-TTS (Eempostor Indo V2 finetune).
Output .ogg/Opus codec — kompatibel WA voice note (sendAudioAsVoice: true).

Pakai:
    from core.tts import synthesize_voice
    path = await synthesize_voice("Halo Bima, apa kabar?")

Env override:
    ENABLE_TTS       — true untuk mengaktifkan TTS (default: false)
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
import random
import time
from pathlib import Path

logger = logging.getLogger("bima_core")

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
_OUTPUT_DIR.mkdir(exist_ok=True)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_VOICE_PYTHON = _PROJECT_ROOT / "services" / "voice" / ".venv" / "bin" / "python"


def _voice_worker_python() -> Path:
    """Return the isolated Python interpreter used by the F5 worker."""
    configured = os.environ.get("VOICE_WORKER_PYTHON", "").strip()
    return Path(configured) if configured else _DEFAULT_VOICE_PYTHON

# Smart filter — voice mode handling:
# - reply <= TTS_OPENER_MIN_CHARS (80) → 'full': voice baca lengkap, text gak dikirim duplicate
# - reply > TTS_OPENER_MIN_CHARS → 'opener': voice baca basa-basi singkat (LLM-generated context-aware
#   atau template fallback) + text full dikirim ke chat. Lebih natural buat reply panjang.
try:
    TTS_OPENER_MIN_CHARS = int(os.environ.get("TTS_OPENER_MIN_CHARS", "80"))
except ValueError:
    TTS_OPENER_MIN_CHARS = 80

# Fallback templates kalau LLM opener generation gagal — variasi biar gak monoton.
_OPENER_TEMPLATES_FALLBACK = [
    "Sip Bim, jawaban lengkap udah aku tulis di chat ya.",
    "Oke, semua detail udah aku siapin di teks.",
    "Bentar Bim, baca selengkapnya di chat ya.",
    "Aman, cek text aja ya buat detailnya.",
    "Nih jawabannya udah gua tulis lengkap.",
    "Beres Bim, semua udah aku jelasin di chat.",
    "Oke, scroll chat ya buat baca lengkapnya.",
    "Yes, jawaban full ada di teks.",
    "Sip, gua udah jawab. Cek chat ya.",
    "Anisa udah siapin di teks, langsung baca aja.",
    "Oke Bima, detail lengkap di chat ya.",
    "Mantap, jawaban udah ada di teks lengkap.",
]

_DEFAULT_HF_REPO = "Eempostor/F5-TTS-INDO-FINETUNE-V2"
_DEFAULT_CKPT_FILE = "f5_tts_indo_v2.pt"
_DEFAULT_VOCAB_FILE = "vocab.txt"
_DEFAULT_BASE_MODEL = "F5TTS_v1_Base"  # finetune di-train dari config base ini
_DEFAULT_REF_AUDIO = str(Path(__file__).resolve().parent.parent / "assets" / "tts_ref.wav")
_DEFAULT_REF_TEXT = "Halo, saya Anisa, asisten AI yang siap membantu kamu."

async def _synthesize_f5(text: str, wav_fp: Path) -> bool:
    """Spawn F5-TTS di subprocess terisolasi (anti-crash + clean VRAM tiap call).

    Subprocess strategy:
    - Crash / OOM / hang di F5-TTS subprocess GAK propagate ke anisa-v3 parent.
    - CUDA context isolated → VRAM auto-released saat subprocess exit (no leak).
    - Timeout 180s (handle long multi-batch reply); kill kalau lewat.
    - Non-zero exit → return False → parent fallback ke edge-tts.
    """
    py = _voice_worker_python()
    if not py.is_file():
        logger.error(f"[TTS] voice worker env belum siap: {py}")
        return False
    worker_module = "core.tts_worker"
    project_root = str(_PROJECT_ROOT)

    # Env passthrough — semua TTS_* + HF_HOME (cache HuggingFace)
    env = os.environ.copy()

    cmd = [str(py), "-m", worker_module, text, str(wav_fp)]
    timeout_sec = 180

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=project_root,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        logger.error(f"[TTS] F5-TTS subprocess spawn gagal: {e}", exc_info=True)
        return False

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
    except asyncio.TimeoutError:
        logger.error(f"[TTS] F5-TTS subprocess timeout (>{timeout_sec}s), kill")
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return False

    if proc.returncode == 0 and wav_fp.exists():
        return True

    err_tail = (stderr.decode("utf-8", errors="replace") or "")[-500:].strip()
    logger.error(f"[TTS] F5-TTS subprocess fail (exit={proc.returncode}): {err_tail}")
    return False


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
    if os.environ.get("ENABLE_TTS", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        logger.info("[TTS] Disabled (set ENABLE_TTS=true to enable)")
        return None

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
    """Voice mode dispatch:
    - 'full': reply pendek (<=80 chars) → voice baca lengkap, text gak duplicate
    - 'opener': reply panjang → voice basa-basi singkat + text full
    - 'skip': empty reply
    """
    text = (reply_text or "").strip()
    if not text:
        return "skip"
    if len(text) <= TTS_OPENER_MIN_CHARS:
        return "full"
    return "opener"


async def generate_opener(reply_text: str) -> str:
    """Generate basa-basi opener voice (5-15 kata) via LLM context-aware.
    Fallback ke template pool kalau LLM gagal / timeout / output invalid.

    LLM ngebaca first 400 chars reply buat detect topik, generate opener casual
    Anisa-style dengan ajakan baca chat. Variasi tone biar gak monoton."""
    if not reply_text or len(reply_text) < 20:
        return random.choice(_OPENER_TEMPLATES_FALLBACK)

    context = reply_text[:400]
    sys_prompt = (
        "Kamu Anisa, asisten AI casual yang akrab sama Bima. Generate opener voice note "
        "PENDEK (5-15 kata Bahasa Indonesia casual) buat reply yang bakal dikirim ke Bima. "
        "Format: greeting singkat + sebut topik dari reply secara casual + ajakan baca chat. "
        "Variasi tone tiap call — kadang akrab ('Oke Bim...'), kadang santai ('Sip, soal X aja...'), "
        "kadang konfirmasi ('Aman, detail X udah aku tulis...'). "
        "JANGAN pakai phrase monoton kayak 'baca dari teks ya'. JANGAN pakai emoji. "
        "Output HANYA opener-nya, satu baris, tanpa kutip atau prefix."
    )
    try:
        from core.langgraph_nodes.llm_config import get_langchain_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_langchain_llm("deepseek/deepseek-v4-flash")
        resp = await asyncio.to_thread(
            llm.invoke,
            [SystemMessage(content=sys_prompt), HumanMessage(content=f"Reply: {context}")],
        )
        opener = (resp.content or "").strip().strip('"').strip("'")
        # Sanity: opener harus reasonable length, gak boleh kosong, gak boleh paragraph
        if not opener or len(opener) > 200 or "\n" in opener:
            logger.warning(f"[TTS] Opener LLM output invalid, pakai template: '{opener[:80]}'")
            return random.choice(_OPENER_TEMPLATES_FALLBACK)
        logger.info(f"[TTS] Opener generated: '{opener}'")
        return opener
    except Exception as e:
        logger.warning(f"[TTS] Opener LLM gagal, pakai template: {e}")
        return random.choice(_OPENER_TEMPLATES_FALLBACK)
