"""WhatsApp Bridge Server — server HTTP khusus untuk WA bot.

Terpisah dari dashboard_server.py. Hanya punya 1 endpoint: POST /chat
Dijalankan sebagai bagian dari main.py (background thread), port 8001.
"""

import asyncio
import logging
import os
import re
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

logger = logging.getLogger('bima_core')

# Token sederhana — harus sama dengan yang di .env
_WA_TOKEN = os.environ.get("WA_BRIDGE_TOKEN", "").strip()

# Audio extensions yang ditranscribe via STT (faster-whisper).
# Voice note WA biasanya .ogg (Opus). Lainnya buat fleksibilitas user kirim file audio biasa.
_AUDIO_EXTS = {".ogg", ".oga", ".opus", ".mp3", ".m4a", ".wav", ".flac", ".aac"}

app = FastAPI(title="B.I.M.A WA Bridge")


class ChatRequest(BaseModel):
    message: str
    token: str = ""
    attachment_paths: list[str] = []


_lock = threading.Lock()
_busy = False


@app.post("/chat")
async def chat(req: ChatRequest):
    """Terima pesan dari WA bot, jalankan LangGraph, return hasilnya."""
    global _busy

    # Auth check
    global _WA_TOKEN
    if not _WA_TOKEN:
        import secrets
        _WA_TOKEN = secrets.token_urlsafe(32)
        logger.critical("[WA-BRIDGE] ⚠️ WA_BRIDGE_TOKEN tidak diset di .env! Menggunakan token acak sementara demi keamanan.")

    if req.token != _WA_TOKEN:
        raise HTTPException(status_code=401, detail="Token tidak valid")

    message = req.message.strip()
    # Voice-only flow: message boleh kosong asal ada audio attachment (bakal di-transcribe)
    has_audio = any(Path(p).suffix.lower() in _AUDIO_EXTS for p in req.attachment_paths)
    if not message and not has_audio:
        return JSONResponse({"error": "Pesan kosong"}, status_code=400)

    with _lock:
        if _busy:
            return JSONResponse(
                {"error": "Sedang memproses pesan lain. Tunggu sebentar."},
                status_code=429
            )
        _busy = True

    try:
        # === Pre-route: !qc / /qc — bypass LangGraph, panggil furniture_qc langsung ===
        lower_msg = message.lower()
        if lower_msg.startswith("!qc") or lower_msg.startswith("/qc"):
            from core.furniture_qc import handle_qc_wa
            logger.info(f"[WA-BRIDGE] !qc intercept ({len(req.attachment_paths)} attachment)")
            return await handle_qc_wa(message, req.attachment_paths)

        # === Pre-route: !cutlist / /cutlist — rectpack 2D bin packing ===
        if lower_msg.startswith("!cutlist") or lower_msg.startswith("/cutlist"):
            from core.cutlist import handle_cutlist_wa
            logger.info("[WA-BRIDGE] !cutlist intercept")
            return await handle_cutlist_wa(message)

        from core.utils import get_waktu, extract_output_files
        from core.langgraph_engine import run_langgraph_engine
        from memory.memory_engine import add_session
        from core.event_bus import emit

        waktu = get_waktu()
        konteks_waktu = f"""
=== KONTEKS WAKTU REAL-TIME ===
Sekarang: {waktu}
Gunakan info waktu ini saat menjawab.
================================"""

        # Pisahkan audio (untuk STT) dari attachment lain (untuk visual/canvas node)
        audio_paths = [p for p in req.attachment_paths if Path(p).suffix.lower() in _AUDIO_EXTS]
        other_paths = [p for p in req.attachment_paths if Path(p).suffix.lower() not in _AUDIO_EXTS]

        # Transcribe semua voice note via faster-whisper (lazy load)
        transcripts: list[str] = []
        if audio_paths:
            from core.stt import transcribe_audio
            for ap in audio_paths:
                text = await asyncio.to_thread(transcribe_audio, ap, "id")
                if text:
                    transcripts.append(text)
            logger.info(f"[WA-BRIDGE] STT: {len(transcripts)}/{len(audio_paths)} voice note ditranscribe")

        # Compose perintah: voice transcript dulu (jadi konteks utama), terus caption text
        perintah_parts: list[str] = []
        if transcripts:
            perintah_parts.append(f"[VOICE NOTE TRANSCRIPT]\n{chr(10).join(transcripts)}")
        if message:
            perintah_parts.append(message)
        perintah = "\n\n".join(perintah_parts) if perintah_parts else message

        if other_paths:
            perintah += f"\n\n[FILE_PATHS] File sudah didownload ke: {' | '.join(other_paths)}"

        emit("reset", message=f'Permintaan baru (WA): "{message[:80]}"')

        hasil = await run_langgraph_engine(
            user_request=perintah,
            konteks_waktu=konteks_waktu,
            attachment_paths=other_paths,
            progress_callback=None,
            source_channel="whatsapp",
        )

        # Simpan sesi
        try:
            add_session(perintah, hasil)
        except Exception as e:
            logger.warning(f"[WA-BRIDGE] Gagal simpan sesi: {e}")

        # Bersihkan metadata
        display = re.sub(r'\nSUCCESS\|[^\n]+', '', hasil).strip()

        # Ekstrak output files
        output_files = extract_output_files(hasil)
        file_list = [str(f) for f in output_files[:10]]

        # TTS auto-mirror: kalau input lewat voice (audio_paths kepass), reply pakai voice juga.
        # 'full' (reply <=80 chars): voice baca lengkap, text gak duplicate.
        # 'opener' (reply >80 chars): voice basa-basi LLM-generated + text full.
        voice_file = None
        voice_mode = None
        if audio_paths and display:
            from core.tts import synthesize_voice, decide_voice_mode, generate_opener
            voice_mode = decide_voice_mode(display)
            if voice_mode == "full":
                fp = await synthesize_voice(display, slug_hint="wa")
                if fp:
                    voice_file = str(fp)
            elif voice_mode == "opener":
                opener_text = await generate_opener(display)
                fp = await synthesize_voice(opener_text, slug_hint="wa_op")
                if fp:
                    voice_file = str(fp)

        emit("reset", message="Selesai (WA)")

        return {
            "status": "ok",
            "response": display,
            "output_files": file_list,
            "voice_file": voice_file,
            "voice_mode": voice_mode,
        }

    except Exception as e:
        logger.error(f"[WA-BRIDGE] Error: {e}", exc_info=True)
        return JSONResponse(
            {"error": f"Gagal memproses: {str(e)}"},
            status_code=500
        )
    finally:
        with _lock:
            _busy = False


@app.get("/health")
async def health():
    return {"status": "ok", "busy": _busy}


def _run(host: str, port: int):
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


def start_wa_bridge(host: str = "127.0.0.1", port: int = 8001):
    """Start WA bridge server di daemon thread. Tidak block caller."""
    if not _WA_TOKEN:
        logger.warning(
            "[WA-BRIDGE] ⚠️  WA_BRIDGE_TOKEN belum di-set di .env! "
            "Bridge tetap jalan tanpa auth (tidak aman untuk production)."
        )
    t = threading.Thread(target=_run, args=(host, port), daemon=True, name="wa-bridge")
    t.start()
    logger.info(f"[WA-BRIDGE] Server jalan di http://{host}:{port}/chat")
