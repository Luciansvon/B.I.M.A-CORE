"""WhatsApp Bridge Server — server HTTP khusus untuk WA bot.

Terpisah dari dashboard_server.py. Hanya punya 1 endpoint: POST /chat
Dijalankan sebagai bagian dari main.py (background thread), port 8001.
"""

import asyncio
import logging
import os
import re
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

logger = logging.getLogger('bima_core')

# Token sederhana — harus sama dengan yang di .env
_WA_TOKEN = os.environ.get("WA_BRIDGE_TOKEN", "").strip()

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
    if _WA_TOKEN and req.token != _WA_TOKEN:
        raise HTTPException(status_code=401, detail="Token tidak valid")

    message = req.message.strip()
    if not message:
        return JSONResponse({"error": "Pesan kosong"}, status_code=400)

    with _lock:
        if _busy:
            return JSONResponse(
                {"error": "Sedang memproses pesan lain. Tunggu sebentar."},
                status_code=429
            )
        _busy = True

    try:
        from core.utils import get_waktu, extract_output_files
        from core.langgraph_engine import run_langgraph_engine
        from teams.t1_manager import simpan_sesi
        from core.event_bus import emit

        waktu = get_waktu()
        konteks_waktu = f"""
=== KONTEKS WAKTU REAL-TIME ===
Sekarang: {waktu}
Gunakan info waktu ini saat menjawab.
================================"""

        perintah = message
        if req.attachment_paths:
            perintah += f"\n\n[FILE_PATHS] File sudah didownload ke: {' | '.join(req.attachment_paths)}"

        emit("reset", message=f'Permintaan baru (WA): "{message[:80]}"')

        hasil = await run_langgraph_engine(
            user_request=perintah,
            konteks_waktu=konteks_waktu,
            attachment_paths=req.attachment_paths,
            progress_callback=None,
            source_channel="whatsapp",
        )

        # Simpan sesi
        try:
            simpan_sesi(perintah, hasil)
        except Exception as e:
            logger.warning(f"[WA-BRIDGE] Gagal simpan sesi: {e}")

        # Bersihkan metadata
        display = re.sub(r'\nSUCCESS\|[^\n]+', '', hasil).strip()

        # Ekstrak output files
        output_files = extract_output_files(hasil)
        file_list = [str(f) for f in output_files[:10]]

        emit("reset", message="Selesai (WA)")

        return {
            "status": "ok",
            "response": display,
            "output_files": file_list,
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
