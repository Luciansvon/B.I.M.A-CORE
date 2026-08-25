"""Observer node — Fase 3a observation-only.

2 entry points:
- observer_node(state): dipanggil dari LangGraph (response via state messages)
- analyze_screen(mode): dipanggil dari REST endpoint (response as plain text)

mode="observe"  → describe what's on screen (default)
mode="proactive" → offer specific help with "butuh bantuan apa?"

NO action execution di phase 3a. DESKTOP_EXECUTE_ENABLED hardcoded False.
"""
import logging
import os
import re
from typing import Literal, Optional

import httpx
import instructor
from openai import AsyncOpenAI
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from core.desktop_bridge_client import capture, ui_tree, BASE_URL as _BRIDGE_URL, health as bridge_health
from core.event_bus import emit
from core.langgraph_nodes.state import BimaState, notify_progress
from core.model_router import model_profile, openrouter_extra_body

logger = logging.getLogger('bima_core')
OBSERVER_MODEL = model_profile("observer").model

_last_phash: Optional[str] = None
_last_observation_text: Optional[str] = None

DESKTOP_EXECUTE_ENABLED = False

_client_singleton: Optional[instructor.AsyncInstructor] = None


class ScreenObservation(BaseModel):
    app: str = Field(description="Nama aplikasi atau judul window utama yang lagi aktif")
    summary: str = Field(description="1-2 kalimat ringkas apa yang lagi terjadi di screen")
    suggested_action: Optional[Literal["click", "type", "press", "scroll", "none"]] = Field(default=None)
    action_target: Optional[str] = Field(default=None)
    action_reasoning: Optional[str] = Field(default=None)
    confidence: float = Field(ge=0.0, le=1.0)


class ProactiveOffer(BaseModel):
    """Schema untuk mode proactive — Anisa nawarin bantuan kontekstual."""
    app: str = Field(description="Nama aplikasi/window yang lagi aktif")
    context: str = Field(description="Apa yang Bima keliatan lagi kerjain (1 kalimat)")
    help_offer: str = Field(
        description="Tawaran bantuan spesifik & relevan ke konteks. ENDING harus tanya konkret kayak "
                    "'butuh bantuan apa?' atau 'mau gue bantu X?'. Bahasa casual ala Anisa, max 3 kalimat."
    )
    confidence: float = Field(ge=0.0, le=1.0)


class ScreenQnA(BaseModel):
    """Schema untuk mode qna — Anisa jawab pertanyaan spesifik dengan konteks screen."""
    app: str = Field(description="Nama aplikasi/window yang lagi aktif")
    what_i_see: str = Field(description="1 kalimat konteks singkat apa yang keliatan di screen")
    answer: str = Field(
        description="JAWABAN actual ke pertanyaan Bima. Free-form, BOLEH panjang & detail. Bahasa casual ala Anisa. "
                    "Kalau pertanyaan butuh saran konkret (warna, design, code fix) → kasih saran spesifik. "
                    "ANTI-HALLU: jangan ngarang detail screen yang gak keliatan jelas."
    )
    suggested_followups: list[str] = Field(
        default_factory=list,
        description="Maksimal 3 follow-up question yang Bima mungkin pengen tanya selanjutnya, berhubungan dengan jawaban + screen context. "
                    "PENDEK (max ~8 kata), casual, Bahasa Indonesia. Contoh: 'kasih contoh kombinasi warnanya', 'gimana cara apply-nya'. "
                    "Kosong kalo gak ada follow-up logis.",
    )
    confidence: float = Field(ge=0.0, le=1.0)


# ============================================================
# Web search (Tavily primary, Serper fallback) — buat qna mode
# ============================================================
_SEARCH_INTENT_RE = re.compile(
    r"(\bcek\s+(di\s+)?(google|internet|web)\b"
    r"|\bcari(in|kan)?\s+(di\s+)?(google|internet|web)\b"
    r"|\bgoogle\s+(in|kan)?\b"
    r"|\btau\s*(g|nggak|ga)k?\s+(soal|tentang)?\b"
    r"|\bcari\s+(info|berita)\b"
    r"|\bberita\s+terbaru\b"
    r"|\bsearch\s+(for\s+)?\b)",
    re.IGNORECASE,
)


def _detect_search_query(text: str) -> Optional[str]:
    """Return cleaned query kalau search intent detected, else None."""
    if not text or not _SEARCH_INTENT_RE.search(text):
        return None
    cleaned = re.sub(
        r"\b(cek|cariin|cariin|cari|google|googling|tau\s*g?(ak|nggak)?|search\s+for|search|di\s+(google|internet|web))\b",
        " ", text, flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.?!:;-")
    return cleaned if len(cleaned) >= 3 else text


async def _tavily_search(query: str, max_results: int = 5) -> Optional[dict]:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "max_results": max_results,
                },
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning(f"[tavily] search fail: {e}")
        return None


async def _serper_search(query: str, max_results: int = 5) -> Optional[dict]:
    key = os.environ.get("SERPER_API_KEY", "").strip()
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": key, "Content-Type": "application/json"},
                json={"q": query, "num": max_results},
            )
            r.raise_for_status()
            data = r.json()
        # Normalize ke format mirip tavily
        organic = data.get("organic", [])[:max_results]
        return {
            "answer": None,
            "results": [
                {"title": x.get("title", ""), "url": x.get("link", ""), "content": x.get("snippet", ""), "score": 0.5}
                for x in organic
            ],
        }
    except Exception as e:
        logger.warning(f"[serper] search fail: {e}")
        return None


async def web_search(query: str) -> Optional[dict]:
    """Try Tavily first, fallback ke Serper. Return dict {answer, results} atau None."""
    res = await _tavily_search(query)
    if res and res.get("results"):
        return res
    logger.info("[web_search] tavily kosong/error, fallback ke serper")
    return await _serper_search(query)


def _format_search_for_llm(search: dict) -> str:
    """Format hasil search jadi text yang LLM-readable. Max ~800 chars."""
    if not search:
        return ""
    lines = []
    answer = (search.get("answer") or "").strip()
    if answer:
        lines.append(f"Quick answer (Tavily): {answer}")
    for i, r in enumerate(search.get("results", [])[:5], 1):
        title = (r.get("title") or "").strip()[:80]
        snippet = (r.get("content") or "").strip()[:200]
        url = (r.get("url") or "").strip()
        lines.append(f"[{i}] {title}\n    {snippet}\n    Source: {url}")
    return "\n\n".join(lines)


# ============================================================


def _get_instructor_client() -> instructor.AsyncInstructor:
    global _client_singleton
    if _client_singleton is None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY missing di env")
        raw = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        _client_singleton = instructor.from_openai(raw, mode=instructor.Mode.JSON)
    return _client_singleton


async def _capture_with_cache():
    """Common helper: capture + (optional) ui_tree. Returns (cap, ui_data, formatted_ui_text)."""
    cap = await capture()
    if cap is None:
        return None, None, None
    ui_data = await ui_tree(limit=30)
    ui_text = ""
    if ui_data and ui_data.get("elements"):
        lines = [
            f"- [{e.get('control_type','?')}] {(e.get('name') or '')[:70]}"
            for e in ui_data["elements"][:15]
        ]
        ui_text = "\n\nUI elements (top 15):\n" + "\n".join(lines)
    return cap, ui_data, ui_text


async def analyze_screen(
    mode: Literal["observe", "proactive", "qna"] = "observe",
    user_request: str = "",
    return_structured: bool = False,
):
    """Returns markdown str by default. Kalau return_structured=True AND mode=qna,
    return dict {response, followups, confidence, app} buat frontend yang butuh struktur."""
    """Shared pipeline: capture → Vision LLM. Return plain text (markdown-formatted)."""
    global _last_phash, _last_observation_text

    cap, _, ui_text = await _capture_with_cache()
    if cap is None:
        # Bedain: bridge unreachable (process mati / IP shift) vs bridge alive tapi capture fail
        from core.desktop_bridge_client import BASE_URL as current_url
        alive = await bridge_health()
        if alive:
            emit('agent_state', agent='observer', state='error', message='Capture fail (bridge alive)')
            return (
                "Bridge desktop nyala tapi gagal capture screen — biasanya screen di-lock, "
                "session locked, atau Windows lagi sibuk. Coba unlock screen + ulang ya 😅"
            )
        emit('agent_state', agent='observer', state='error', message=f'Bridge unreachable @ {current_url}')
        return (
            f"Maaf Bima, gue gak bisa lihat screen lo sekarang — desktop bridge `{current_url}` gak respond.\n"
            f"Cek: (1) service `C:\\Users\\shint\\bima-desktop-bridge\\main.py` udah jalan? "
            f"(2) port 9100 listening? `Get-NetTCPConnection -LocalPort 9100`\n"
            f"(3) Windows Firewall allow inbound? 😅"
        )

    phash = cap.get("perceptual_hash")
    title = cap.get("foreground_title") or "Unknown"
    process = cap.get("foreground_process") or ""
    b64 = cap.get("screenshot_b64")

    # Cache hit (mode=observe only; proactive selalu fresh LLM)
    if mode == "observe" and phash and phash == _last_phash and _last_observation_text:
        emit('agent_state', agent='observer', state='done', message='cached')
        return f"Screen lo sama kayak terakhir gue cek ✨ Cached observation:\n\n{_last_observation_text}"

    if not b64:
        return "Capture berhasil tapi screenshot kosong, aneh nih. Coba lagi?"

    try:
        client = _get_instructor_client()

        if mode == "observe":
            sys_prompt = (
                "Kamu Anisa observer. Analisa screenshot dari Bima, jawab Bahasa Indonesia casual.\n"
                "ATURAN ANTI-HALLU (KETAT):\n"
                "1. JANGAN quote angka spesifik (timer, durasi, persentase, harga) kecuali ANGKA TERSEBUT JELAS terbaca di screenshot. Kalau samar/blur/gak yakin → deskripsi umum aja ('ada timer', 'progress bar', dll), JANGAN ngarang angkanya.\n"
                "2. JANGAN quote text label spesifik (nama tombol, judul, pesan error) kecuali yakin terbaca. Kalau ragu → 'kayaknya ada notifikasi/pesan' tanpa quote isinya.\n"
                "3. JANGAN ngarang nama aplikasi/fitur yang gak keliatan jelas.\n"
                "4. Kalau detail apapun samar → confidence < 0.5, summary lebih general.\n"
                "5. Foreground window title (dari OS metadata) BOLEH dipakai sebagai ground truth, tapi text di screenshot itu sendiri butuh visual confirmation."
            )
            response_model = ScreenObservation
            user_text = (
                f"Foreground window: {title!r} (process: {process or 'unknown'})\n"
                f"{ui_text}\n\nUser request: {user_request or 'lihat screen gue'}"
            )
        elif mode == "proactive":
            sys_prompt = (
                "Kamu Anisa proactive assistant. Bima baru aktifin hotkey buat minta bantuan. "
                "Liat screen Bima, identify konteks dia lagi ngerjain apa, terus tawarin bantuan KONKRET & RELEVAN. "
                "ATURAN: tawaran HARUS spesifik ke konteks screen (bukan generik). Ending wajib tanya konkret "
                "kayak 'butuh bantuan apa?' atau 'mau gue bantu X?'. Bahasa casual, max 3 kalimat. "
                "Jangan ngarang fitur/aplikasi yang gak keliatan di screenshot."
            )
            response_model = ProactiveOffer
            user_text = (
                f"Foreground window: {title!r} (process: {process or 'unknown'})\n"
                f"{ui_text}\n\nBima keliatan lagi ngerjain sesuatu — kasih offer bantuan spesifik."
            )
        else:  # qna
            # Auto-detect search intent → call web search → inject context
            search_query = _detect_search_query(user_request)
            web_block = ""
            if search_query:
                emit('agent_state', agent='observer', state='working', message=f'🔎 search "{search_query[:40]}"')
                logger.info(f"[observer] qna search intent detected: {search_query!r}")
                search_results = await web_search(search_query)
                if search_results:
                    formatted = _format_search_for_llm(search_results)
                    if formatted:
                        web_block = (
                            f"\n\n=== HASIL WEB SEARCH (Tavily/Serper) untuk query \"{search_query}\" ===\n"
                            f"{formatted}\n"
                            f"=== AKHIR WEB SEARCH ===\n"
                            f"Pake info di atas untuk jawab Bima, dan SEBUTKAN sumber-nya (kasih nomor [1], [2], dll) di jawaban.\n"
                        )
                    # Simpan URLs buat ditampilkan di response (server-side, gak via LLM = anti-hallu URL)
                    nonlocal_sources = [r.get("url", "") for r in search_results.get("results", [])[:5] if r.get("url")]
                else:
                    nonlocal_sources = []
            else:
                nonlocal_sources = []

            sys_prompt = (
                "Kamu Anisa Q&A. Bima nanya sesuatu sambil minta lo liat screen-nya. "
                "Liat screenshot + UI context, terus JAWAB pertanyaan dia dengan SPESIFIK & RELEVAN. "
                "Bahasa Indonesia casual, hangat, ✨. Boleh detail kalau pertanyaan butuh.\n"
                "ATURAN ANTI-HALLU (KETAT):\n"
                "1. JANGAN quote angka/text spesifik dari screen kecuali jelas terbaca. Kalau samar → general aja.\n"
                "2. JANGAN ngarang nama fitur/aplikasi yang gak keliatan.\n"
                "3. Foreground window title dari OS BOLEH dipake sebagai ground truth.\n"
                "4. Kalau pertanyaan gak related ke screen sama sekali → tetap jawab apa adanya berdasarkan pengetahuan umum, tapi flag di awal 'screen lo gak nunjukin info ini, tapi based on pengetahuan umum...'\n"
                "5. Kalau ada section HASIL WEB SEARCH di context, PAKE info itu sebagai fakta utama. Cite dengan [1], [2], dll. JANGAN ngarang fakta yang gak ada di search results."
            )
            response_model = ScreenQnA
            user_text = (
                f"Foreground window: {title!r} (process: {process or 'unknown'})\n"
                f"{ui_text}{web_block}\n\nPertanyaan Bima: {user_request or 'kasih saran berdasarkan apa yang lo liat'}"
            )

        result = await client.chat.completions.create(
            model=OBSERVER_MODEL,
            extra_body=openrouter_extra_body("observer"),
            response_model=response_model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                },
            ],
            # max_retries=1 bound total wall time. instructor retry sebelumnya 2x → 3 LLM call
            # sequential, kalau Gemini lambat (cold start / region throttle) bisa >30s.
            max_retries=1,
        )
    except Exception as e:
        logger.error(f"[observer] vision LLM gagal: {e}")
        emit('agent_state', agent='observer', state='error', message=str(e)[:80])
        return f"Gue capture screen-nya tapi gagal analisa pake vision LLM 😅\nError: `{str(e)[:200]}`"

    if mode == "observe":
        obs: ScreenObservation = result
        lines = [
            "👀 *Screen check ✨*",
            f"**App:** {obs.app}",
            f"**Yang gue liat:** {obs.summary}",
        ]
        if obs.suggested_action and obs.suggested_action != "none":
            lines.append("")
            lines.append("💡 *Saran action (Phase 3a observation-only — gue belum bisa eksekusi):*")
            lines.append(f"- Action: `{obs.suggested_action}`")
            if obs.action_target:
                lines.append(f"- Target: `{obs.action_target}`")
            if obs.action_reasoning:
                lines.append(f"- Alasan: {obs.action_reasoning}")
        lines.append("")
        lines.append(f"*(confidence: {obs.confidence:.0%}{', execute disabled' if not DESKTOP_EXECUTE_ENABLED else ''})*")
        response_text = "\n".join(lines)
        _last_phash = phash
        _last_observation_text = response_text
        emit('agent_state', agent='observer', state='done', message=f'Observed {obs.app[:30]}')
    elif mode == "proactive":
        offer: ProactiveOffer = result
        lines = [
            "🙋 *Anisa proactive ✨*",
            f"**App:** {offer.app}",
            f"**Konteks:** {offer.context}",
            "",
            offer.help_offer,
            "",
            f"*(confidence: {offer.confidence:.0%})*",
        ]
        response_text = "\n".join(lines)
        emit('agent_state', agent='observer', state='done', message=f'Proactive offer for {offer.app[:30]}')
    else:  # qna
        qna: ScreenQnA = result
        lines = [
            "💬 *Anisa Q&A ✨*",
            f"**App:** {qna.app}",
            f"**Konteks:** {qna.what_i_see}",
            "",
            qna.answer,
        ]
        # Tampilkan sources kalau ada (dari web search)
        sources = locals().get("nonlocal_sources", []) or []
        if sources:
            lines.append("")
            lines.append("**Sumber:**")
            for i, url in enumerate(sources[:5], 1):
                lines.append(f"[{i}] {url}")
        lines.append("")
        lines.append(f"*(confidence: {qna.confidence:.0%})*")
        response_text = "\n".join(lines)
        emit('agent_state', agent='observer', state='done', message=f'Q&A answered ({qna.app[:30]})')

        if return_structured:
            return {
                "response": response_text,
                "followups": list(qna.suggested_followups or [])[:3],
                "sources": sources,
                "confidence": qna.confidence,
                "app": qna.app,
            }

    return response_text


async def observer_node(state: BimaState) -> dict:
    """LangGraph node entry point. Default mode=observe."""
    await notify_progress(state, "👀 *Anisa lagi ngintip screen...*")
    emit('agent_state', agent='observer', state='working', message='Capturing screen')

    user_request = state.get("user_request") or ""
    text = await analyze_screen(mode="observe", user_request=user_request)

    return {
        "messages": [AIMessage(content=text)],
        "is_finished": True,
    }
