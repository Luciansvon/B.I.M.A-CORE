"""Dashboard server: FastAPI + WebSocket. Jalan di thread terpisah dari Discord bot."""

import asyncio
import json
import logging
import os
import random
import re
import secrets
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from core.event_bus import subscribe, unsubscribe, get_metrics, get_recent_events, emit
from memory.memory_engine import get_facts_list, get_sessions_count

logger = logging.getLogger('bima_core')

# ============================================================
# AUTH — Bearer token untuk proteksi endpoint sensitif
# ============================================================
def _token_status_message(*, configured: bool) -> str:
    """Return dashboard auth status without exposing token material."""
    if configured:
        return "[DASHBOARD] API token loaded from environment"
    return "[DASHBOARD] temporary token generated; set DASHBOARD_API_TOKEN for stable access"


_API_TOKEN = os.environ.get("DASHBOARD_API_TOKEN", "").strip()
_TOKEN_CONFIGURED = bool(_API_TOKEN)
if not _TOKEN_CONFIGURED:
    _API_TOKEN = secrets.token_urlsafe(32)
    logger.warning(
        f"[DASHBOARD] ⚠️  DASHBOARD_API_TOKEN tidak di-set di .env! "
        f"Auto-generated token (akan berubah setiap restart):\n"
        "  Temporary token is not written to logs.\n"
        f"  Set DASHBOARD_API_TOKEN di .env supaya token permanen."
    )
else:
    logger.info(_token_status_message(configured=True))

_security = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str:
    """Dependency: validasi Bearer token. Raise 401 jika gagal."""
    if credentials is None or credentials.credentials != _API_TOKEN:
        raise HTTPException(status_code=401, detail="Token tidak valid atau tidak diberikan.")
    return credentials.credentials


app = FastAPI(title="B.I.M.A Core Dashboard")
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
GUILD_DIR = Path(__file__).parent.parent / "dashboard"


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "B.I.M.A Core Dashboard",
        "ui": "/dashboard",
    }


@app.get("/dashboard")
async def dashboard():
    html_file = FRONTEND_DIR / "dashboard.html"
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse("<h1>Dashboard belum ter-deploy</h1>", status_code=404)


_GUILD_ALLOWED_EXT = {".html", ".jsx", ".css", ".js", ".json", ".svg", ".png"}


@app.get("/dashboard/v3/")
async def dashboard_v3():
    """Pixel-themed Guild Hall dashboard (alternate skin di folder `dashboard/`).

    Trailing slash penting — FastAPI auto-redirect dari `/dashboard/v3` ke
    `/dashboard/v3/` lewat default redirect_slashes=True. Tanpa slash, browser
    resolve relative `<script src="...">` ke `/dashboard/...` (404).
    no-store cache header biar dev-loop nggak ke-stuck di browser cache."""
    html_file = GUILD_DIR / "guild.html"
    if html_file.exists():
        return FileResponse(html_file, headers={"Cache-Control": "no-store"})
    return HTMLResponse("<h1>Guild dashboard belum ter-deploy</h1>", status_code=404)


@app.get("/dashboard/v3/{filename}")
async def serve_guild_asset(filename: str):
    """Serve sibling assets (jsx/css/dst) untuk dashboard v3."""
    safe_name = Path(filename).name
    if Path(safe_name).suffix.lower() not in _GUILD_ALLOWED_EXT:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    fpath = GUILD_DIR / safe_name
    if not fpath.exists() or not fpath.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(fpath, headers={"Cache-Control": "no-store"})


_FAVICON_SVG = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" fill="#0f2818"/>'
    '<rect x="6" y="6" width="20" height="20" fill="#4ade80" stroke="#000" stroke-width="2"/>'
    '<rect x="11" y="11" width="3" height="3" fill="#000"/>'
    '<rect x="18" y="11" width="3" height="3" fill="#000"/>'
    '<rect x="11" y="19" width="10" height="2" fill="#000"/>'
    '</svg>'
)


@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    return Response(content=_FAVICON_SVG, media_type="image/svg+xml")


@app.get("/api/metrics")
async def metrics():
    return get_metrics()


# ============================================================
# API endpoints buat dashboard V2 (corporate-clean)
# ============================================================

_OUTPUT_ICONS = {
    ".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx",
    ".html": "html", ".png": "img", ".jpg": "img", ".jpeg": "img",
    ".svg": "svg", ".txt": "txt", ".py": "code",
    ".json": "json", ".csv": "csv",
}


def _humanize_size(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


@app.get("/api/outputs")
async def list_outputs(limit: int = 30, kind: str = "", _auth: str = Depends(require_auth)):
    """List file di outputs/ urut berdasar mtime desc.
    Query param `kind`: filter by ekstensi family (pdf/docx/xlsx/html/img/svg).
    """
    if not OUTPUTS_DIR.exists():
        return {"items": [], "total": 0}

    files = []
    for p in OUTPUTS_DIR.iterdir():
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        ext = p.suffix.lower()
        icon = _OUTPUT_ICONS.get(ext, "file")
        if kind and kind != icon:
            continue
        try:
            stat = p.stat()
        except OSError:
            continue
        files.append({
            "name": p.name,
            "ext": ext.lstrip("."),
            "icon": icon,
            "size": stat.st_size,
            "size_human": _humanize_size(stat.st_size),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "modified_human": datetime.fromtimestamp(stat.st_mtime).strftime("%d %b %Y, %H:%M"),
            "url": f"/outputs/{p.name}",
        })

    files.sort(key=lambda x: x["modified"], reverse=True)
    return {"items": files[:limit], "total": len(files)}


@app.get("/outputs/{filename}")
async def serve_output(filename: str, credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security)):
    """Serve file dari outputs/ (untuk preview HTML/PDF/img di dashboard).
    PENTING: File gambar untuk postingan media sosial (anisa_img_* / threads_*)
    bisa diakses publik tanpa auth agar Threads API bisa download gambarnya.
    """
    # Sanitasi: cegah path traversal
    safe_name = Path(filename).name
    
    # Cek apakah file ini gambar publik untuk postingan Threads
    is_public_img = safe_name.startswith("anisa_img_") or safe_name.startswith("threads_")
    
    if not is_public_img:
        # Validasi Bearer token untuk file dokumen sensitif lainnya
        if credentials is None or credentials.credentials != _API_TOKEN:
            raise HTTPException(status_code=401, detail="Token tidak valid atau tidak diberikan.")
            
    fpath = OUTPUTS_DIR / safe_name
    if not fpath.exists() or not fpath.is_file():
        # Fallback ke gallery_cache
        gallery_fpath = OUTPUTS_DIR / "gallery_cache" / safe_name
        if gallery_fpath.exists() and gallery_fpath.is_file():
            fpath = gallery_fpath
        else:
            return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(fpath)


@app.api_route("/static/{filename}", methods=["GET", "HEAD"])
async def serve_static(filename: str):
    """Serve file dari frontend/ (theme song mp3, sfx, gif, dst).
    Support HEAD biar browser bisa probe ada/nggak file-nya."""
    safe_name = Path(filename).name
    fpath = FRONTEND_DIR / safe_name
    if not fpath.exists() or not fpath.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(fpath)


@app.get("/api/memory")
async def memory_snapshot(_auth: str = Depends(require_auth)):
    """Snapshot fakta + jumlah sesi dari memory.db (SQLite)."""
    facts_list = get_facts_list()
    sessions_count = get_sessions_count()
    fact_of_day = random.choice(facts_list) if facts_list else None
    return {
        "facts": facts_list,
        "sessions_count": sessions_count,
        "fact_of_day": fact_of_day,
    }


@app.get("/api/sprints")
async def active_sprints():
    """Active sprints = agen yang state-nya bukan 'idle'.
    Mengambil dari event_bus.get_metrics() + format ringkas untuk UI."""
    snapshot = get_metrics()
    sprints = []
    for agent, info in snapshot.get("agents", {}).items():
        state = info.get("current_state", "idle")
        if state == "idle":
            continue
        sprints.append({
            "agent": agent,
            "state": state,
            "task_count": info.get("task_count", 0),
            "error_count": info.get("error_count", 0),
            "avg_duration_ms": info.get("avg_duration_ms", 0),
            "last_active": info.get("last_active"),
        })
    return {
        "sprints": sprints,
        "uptime_seconds": snapshot.get("uptime_seconds", 0),
        "total_agents_seen": len(snapshot.get("agents", {})),
    }


# ============================================================
# FURNITURE LAYOUT SYNC — shared across all devices
# ============================================================

LAYOUT_FILE = Path(__file__).parent.parent / "frontend" / "furniture_layout.json"


class LayoutData(BaseModel):
    layout: dict


@app.get("/api/layout")
async def get_layout():
    """Load saved furniture layout (shared across all devices)."""
    if not LAYOUT_FILE.exists():
        return {"layout": {}}
    try:
        with open(LAYOUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"layout": data}
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[DASHBOARD] layout file gagal dibaca: {e}")
        return {"layout": {}}


@app.post("/api/layout")
async def save_layout(req: LayoutData, _auth: str = Depends(require_auth)):
    """Save furniture layout to server (accessible from any device)."""
    try:
        with open(LAYOUT_FILE, "w", encoding="utf-8") as f:
            json.dump(req.layout, f, indent=2)
        return {"status": "ok", "items_saved": len(req.layout)}
    except OSError as e:
        logger.error(f"[DASHBOARD] Gagal simpan layout: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================
# COMMAND ENDPOINT — kirim perintah langsung dari dashboard
# ============================================================

class CommandRequest(BaseModel):
    command: str

_command_running = False
_command_lock = threading.Lock()


@app.post("/api/command")
async def post_command(req: CommandRequest, _auth: str = Depends(require_auth)):
    """Terima perintah dari dashboard, jalankan via LangGraph engine."""
    global _command_running
    
    command = req.command.strip()
    if not command:
        return JSONResponse({"error": "Perintah kosong"}, status_code=400)
    
    with _command_lock:
        if _command_running:
            return JSONResponse(
                {"error": "Ada perintah yang sedang diproses. Tunggu selesai."},
                status_code=429
            )
        _command_running = True
    
    # Broadcast reset + new request via event bus
    emit("reset", message=f"Permintaan baru: {command[:100]}")
    
    # Run in background thread supaya tidak block server
    thread = threading.Thread(
        target=_run_command_sync,
        args=(command,),
        daemon=True,
        name="dashboard-command"
    )
    thread.start()
    
    return {"status": "accepted", "command": command[:100]}


def _run_command_sync(command: str):
    """Jalankan LangGraph engine di thread terpisah."""
    global _command_running
    try:
        from core.utils import get_waktu
        from core.langgraph_engine import run_langgraph_engine
        from teams.t1_manager import simpan_sesi
        
        waktu = get_waktu()
        konteks_waktu = f"""
=== KONTEKS WAKTU REAL-TIME ===
Sekarang: {waktu}
Gunakan info waktu ini saat menjawab.
================================"""
        
        # Buat event loop baru untuk thread ini
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def _progress(content: str):
            logger.info(f"[DASHBOARD CMD] Progress: {content[:80]}")
            # Broadcast progress ke chat
            emit("command_progress", message=content, command=command[:100])
        
        hasil = loop.run_until_complete(
            run_langgraph_engine(
                user_request=command,
                konteks_waktu=konteks_waktu,
                attachment_paths=[],
                progress_callback=_progress,
            )
        )
        
        # Simpan sesi
        try:
            simpan_sesi(command, hasil)
        except Exception as e:
            logger.warning(f"[DASHBOARD CMD] Gagal simpan sesi: {e}")
        
        # Broadcast response ke chat + reset
        display = re.sub(r'\nSUCCESS\|[^\n]+', '', hasil).strip()
        preview = display[:200] + ('...' if len(display) > 200 else '')
        emit("command_response", message=display, command=command[:100], error=False)
        emit("reset", message=f"Selesai: {preview}")
        
        logger.info(f"[DASHBOARD CMD] Selesai: {command[:60]}")
        loop.close()
        
    except Exception as e:
        logger.error(f"[DASHBOARD CMD] Error: {e}", exc_info=True)
        emit("command_response", message=f"Error: {str(e)}", command=command[:100], error=True)
        emit("reset", message=f"Error: {str(e)[:100]}")
    finally:
        with _command_lock:
            _command_running = False


@app.get("/api/command/status")
async def command_status(_auth: str = Depends(require_auth)):
    """Cek apakah ada command yang sedang berjalan."""
    return {"running": _command_running}


# ============================================================
# Observer triggers (Fase 3a) — dipanggil dari macro keyboard / external trigger
# ============================================================
_OBSERVER_CHANNEL_ID = int(os.environ.get("OBSERVER_CHANNEL_ID", "1504100849134338098"))


def _post_to_observer_channel_sync(text: str) -> None:
    """Schedule channel.send() ke discord client loop dari thread lain. Safe-fail."""
    if not text:
        return
    try:
        from core.discord_bot import client
        if not client or not client.loop or client.is_closed():
            logger.warning("[OBSERVER TRIGGER] Discord client not ready, skip post")
            return
        channel = client.get_channel(_OBSERVER_CHANNEL_ID)
        if channel is None:
            logger.warning(f"[OBSERVER TRIGGER] Channel {_OBSERVER_CHANNEL_ID} not found")
            return
        # Discord 2000 char limit per message — chunk kalau perlu
        chunks = [text[i:i+1900] for i in range(0, len(text), 1900)] or [text]
        for chunk in chunks:
            fut = asyncio.run_coroutine_threadsafe(channel.send(chunk), client.loop)
            fut.result(timeout=10)
    except Exception as e:
        logger.error(f"[OBSERVER TRIGGER] post fail: {e}")


def _run_observer_trigger_sync(mode: str):
    """Thread worker: jalankan analyze_screen + post ke Discord channel."""
    try:
        from core.langgraph_nodes.observer import analyze_screen
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            text = loop.run_until_complete(analyze_screen(mode=mode, user_request=""))
        finally:
            loop.close()
        _post_to_observer_channel_sync(text)
        logger.info(f"[OBSERVER TRIGGER] mode={mode} posted ({len(text)} chars)")
    except Exception as e:
        logger.error(f"[OBSERVER TRIGGER] mode={mode} error: {e}", exc_info=True)


@app.post("/trigger/observe")
async def trigger_observe(_auth: str = Depends(require_auth)):
    """Trigger #1: observe screen + post ke observer channel."""
    threading.Thread(
        target=_run_observer_trigger_sync,
        args=("observe",),
        daemon=True,
        name="observer-trigger-observe",
    ).start()
    return {"status": "accepted", "mode": "observe", "channel_id": _OBSERVER_CHANNEL_ID}


@app.post("/trigger/proactive")
async def trigger_proactive(_auth: str = Depends(require_auth)):
    """Trigger #2: proactive help offer berdasarkan konteks screen."""
    threading.Thread(
        target=_run_observer_trigger_sync,
        args=("proactive",),
        daemon=True,
        name="observer-trigger-proactive",
    ).start()
    return {"status": "accepted", "mode": "proactive", "channel_id": _OBSERVER_CHANNEL_ID}


class QnARequest(BaseModel):
    question: str


class ChatRequest(BaseModel):
    message: str
    include_screen: Optional[bool] = None  # None = auto-detect
    history: Optional[list[dict]] = None    # [{"role": "user"|"assistant", "content": "..."}, ...]


@app.post("/trigger/qna")
async def trigger_qna(req: QnARequest, _auth: str = Depends(require_auth)):
    """Trigger #3 (Q&A overlay) — SYNC endpoint, return response setelah vision LLM selesai (~10s).

    Pipeline:
      1. Capture screen via bridge
      2. Vision LLM (ScreenQnA schema) — jawab pertanyaan dengan konteks screen
      3. Forward response ke Discord observer channel (background)
      4. Save Q&A pair ke agentmemory (background)
      5. Return response text ke caller (overlay UI)

    Body: {"question": "string"}
    Response: {"response": "string", "elapsed_ms": int}
    """
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question kosong")

    import time
    from core.langgraph_nodes.observer import analyze_screen

    t0 = time.time()
    try:
        structured = await analyze_screen(mode="qna", user_request=question, return_structured=True)
    except Exception as e:
        logger.error(f"[QNA TRIGGER] analyze_screen fail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"qna pipeline fail: {str(e)[:200]}")
    elapsed_ms = int((time.time() - t0) * 1000)

    text = structured["response"] if isinstance(structured, dict) else structured
    followups = structured.get("followups", []) if isinstance(structured, dict) else []
    sources = structured.get("sources", []) if isinstance(structured, dict) else []

    # Forward to Discord channel + save to agentmemory (fire-and-forget background)
    def _bg_forward():
        try:
            _post_to_observer_channel_sync(f"**❓ {question}**\n\n{text}")
        except Exception as e:
            logger.warning(f"[QNA TRIGGER] discord forward fail: {e}")

        try:
            import httpx
            with httpx.Client(timeout=3.0) as c:
                c.post(
                    "http://127.0.0.1:3111/agentmemory/remember",
                    json={"content": f"[QNA {datetime.now().strftime('%Y-%m-%d %H:%M')}] User: {question}\nAnisa: {text}"},
                )
        except Exception as e:
            logger.warning(f"[QNA TRIGGER] agentmemory save fail: {e}")

    threading.Thread(target=_bg_forward, daemon=True, name="qna-forward").start()

    return {"response": text, "followups": followups, "sources": sources, "elapsed_ms": elapsed_ms}


# ============================================================
# Universal chat endpoint — smart auto-route screen QnA vs general chat
# ============================================================
import re as _re

# Detect intent yang BUTUH screen capture
_SCREEN_INTENT_RE = _re.compile(
    r"(\blihat(?:in|lah|kan)?\s+(screen|layar|ini|monitor|gambar)?\b"
    r"|\blihat?in\b"
    r"|/lihat\b|/screen\b|/observe\b"
    r"|\bcek\s+(screen|layar|gambar|ini)\b"
    r"|\bngintip\s+(layar|screen)\b"
    r"|\bapa\s+(yang|sih)?\s*(lagi|ada)?\s*(di\s+)?(screen|layar|monitor|sini)\b"
    r"|\bini\s+(apa|kode\s+apa|gambar\s+apa|error\s+apa)\b"
    r"|\byang\s+lagi\s+gue\s+(buka|liat)\b"
    r"|\bdi\s+screen\s+(ini|gue)\b"
    r"|\b(screenshot|screen\s+shot)\b)",
    _re.IGNORECASE,
)


def _detect_screen_intent(msg: str) -> bool:
    return bool(msg and _SCREEN_INTENT_RE.search(msg))


def _bg_forward_chat(question: str, text: str, mode: str):
    """Fire-and-forget: Discord channel + agentmemory save."""
    try:
        prefix = "👀 " if mode == "screen_qna" else "💬 "
        _post_to_observer_channel_sync(f"**{prefix}❓ {question}**\n\n{text}")
    except Exception as e:
        logger.warning(f"[CHAT TRIGGER] discord forward fail: {e}")
    try:
        import httpx as _httpx
        with _httpx.Client(timeout=3.0) as c:
            c.post(
                "http://127.0.0.1:3111/agentmemory/remember",
                json={"content": f"[CHAT {datetime.now().strftime('%Y-%m-%d %H:%M')} {mode}] User: {question}\nAnisa: {text}"},
            )
    except Exception as e:
        logger.warning(f"[CHAT TRIGGER] agentmemory save fail: {e}")


@app.post("/trigger/chat")
async def trigger_chat(req: ChatRequest, _auth: str = Depends(require_auth)):
    """Universal endpoint — overlay panggil ini untuk semua chat.

    Smart routing:
    - include_screen=True  → force screen QnA
    - include_screen=False → force general chat (skip screen)
    - include_screen=None  → auto-detect dari message (default)

    Screen mode → analyze_screen(qna) (vision LLM + UI tree + optional web search)
    General chat → run_langgraph_engine (manager → 9 specialist teams)
    """
    msg = (req.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message kosong")

    # Decide mode
    if req.include_screen is True:
        use_screen = True
    elif req.include_screen is False:
        use_screen = False
    else:
        use_screen = _detect_screen_intent(msg)

    import time as _time
    t0 = _time.time()

    # Format conversation history sebagai context block kalau ada
    history_block = ""
    if req.history:
        lines = []
        for h in req.history[-6:]:  # last 6 turns max
            role = h.get("role") or "user"
            content = (h.get("content") or "").strip()
            if not content:
                continue
            label = "Bima" if role == "user" else "Anisa"
            lines.append(f"{label}: {content[:600]}")
        if lines:
            history_block = (
                "=== HISTORI PERCAKAPAN OVERLAY (paling relevan, prioritas tertinggi) ===\n"
                + "\n".join(lines)
                + "\n=== AKHIR HISTORI ===\n\n"
            )

    effective_msg = (history_block + "Pesan baru dari Bima: " + msg) if history_block else msg

    if use_screen:
        # Screen QnA pipeline
        from core.langgraph_nodes.observer import analyze_screen
        try:
            structured = await analyze_screen(mode="qna", user_request=effective_msg, return_structured=True)
        except Exception as e:
            logger.error(f"[CHAT TRIGGER] qna fail: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"qna pipeline fail: {str(e)[:200]}")
        text = structured["response"] if isinstance(structured, dict) else structured
        followups = structured.get("followups", []) if isinstance(structured, dict) else []
        sources = structured.get("sources", []) if isinstance(structured, dict) else []
        elapsed_ms = int((_time.time() - t0) * 1000)
        threading.Thread(target=_bg_forward_chat, args=(msg, text, "screen_qna"), daemon=True).start()
        return {"response": text, "mode": "screen_qna", "followups": followups, "sources": sources, "elapsed_ms": elapsed_ms}

    # General chat via LangGraph (manager → specialist teams)
    from core.langgraph_engine import run_langgraph_engine
    from core.utils import get_waktu

    konteks_waktu = f"=== KONTEKS WAKTU REAL-TIME ===\nSekarang: {get_waktu()}\n==============================="

    result_holder: dict = {}

    def _worker():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                hasil = loop.run_until_complete(
                    run_langgraph_engine(
                        user_request=effective_msg,
                        konteks_waktu=konteks_waktu,
                        attachment_paths=[],
                        progress_callback=None,
                    )
                )
                result_holder['hasil'] = hasil
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"[CHAT TRIGGER] LangGraph error: {e}", exc_info=True)
            result_holder['error'] = str(e)

    t = threading.Thread(target=_worker, daemon=True, name="chat-langgraph")
    t.start()
    t.join(timeout=180)  # 3 menit max

    if 'error' in result_holder:
        raise HTTPException(status_code=500, detail=f"langgraph fail: {result_holder['error'][:200]}")
    if 'hasil' not in result_holder:
        raise HTTPException(status_code=504, detail="langgraph timeout (>180s)")

    text = result_holder['hasil'] or ""
    # Strip SUCCESS|... metadata yang langgraph_engine append buat Discord chunking
    text = re.sub(r'\nSUCCESS\|[^\n]+', '', text).strip()
    elapsed_ms = int((_time.time() - t0) * 1000)

    threading.Thread(target=_bg_forward_chat, args=(msg, text, "general_chat"), daemon=True).start()

    return {"response": text, "mode": "general_chat", "followups": [], "sources": [], "elapsed_ms": elapsed_ms}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(default="")):
    # WebSocket tidak bisa pakai Authorization header dari browser,
    # jadi validasi via query param: ws://host/ws?token=xxx
    if token != _API_TOKEN:
        await ws.close(code=4001, reason="Token tidak valid")
        return
    await ws.accept()
    try:
        loop = asyncio.get_running_loop()
    except Exception:
        loop = asyncio.get_event_loop()
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    subscribe(loop, q)
    try:
        await ws.send_json({"type": "connected", "message": "Live"})
        await ws.send_json({"type": "history", "events": get_recent_events()})
        while True:
            msg = await q.get()
            await ws.send_json(msg)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"[DASHBOARD] WS error: {e}")
    finally:
        unsubscribe(loop, q)


def _run(host: str, port: int):
    """Blocking. Dipanggil di thread baru."""
    config = uvicorn.Config(app, host=host, port=port, log_level="info", access_log=True)
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


def start_in_background(host: str = "0.0.0.0", port: int = 8000):
    """Start dashboard server di daemon thread. Tidak block caller."""
    t = threading.Thread(target=_run, args=(host, port), daemon=True, name="dashboard-server")
    t.start()
    logger.info(f"[DASHBOARD] Server jalan di http://{host}:{port}/dashboard")
