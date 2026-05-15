import asyncio
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from core.langgraph_nodes.state import BimaState, notify_progress
from core.langgraph_nodes.llm_config import default_llm
from teams.t5_intel import SmartSearchTool
from tools.browser_use_tool import BrowserUseTool
from memory.memory_engine import get_recent_context

logger = logging.getLogger('bima_core')

search_tool = SmartSearchTool()
browser_tool = BrowserUseTool()

# Trigger short-circuit ke BrowserUseTool: pesan punya URL https?:// PLUS verb interaktif.
# Pattern: cek URL eksplisit AND minimal salah satu verb di list.
_URL_PATTERN = re.compile(r'https?://[^\s\'"<>]+', re.IGNORECASE)
_INTERACTIVE_VERBS = re.compile(
    r'\b(brows\w*|buka|navigasi\w*|masuk\s+ke|login(?:\s+ke)?|klik\w*|isi\s+form|scrape|scrap\w+|extract\s+isi|scroll\w*|interact\w*|fetch|live\s+brows\w*)\b',
    re.IGNORECASE,
)


async def intel_node(state: BimaState) -> dict:
    await notify_progress(state, "🔍 *Tim Intel lagi cari info di internet...*")
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")

    # === Short-circuit ke BrowserUseTool ===
    # Kalau pesan punya URL eksplisit + verb interaktif, langsung pakai
    # BrowserUseTool. Skip Serper search yang bikin LLM hallucinate.
    url_match = _URL_PATTERN.search(user_request)
    verb_match = _INTERACTIVE_VERBS.search(user_request)
    if url_match and verb_match:
        await notify_progress(state, "🌐 *Anisa nge-buka browser (Chromium) buat fetch isi...*")
        logger.info(f"[LANGGRAPH INTEL] Short-circuit BrowserUseTool — URL={url_match.group(0)[:60]} verb={verb_match.group(0)}")
        try:
            browser_result = await asyncio.to_thread(browser_tool._run, user_request)
            logger.info(f"[LANGGRAPH INTEL] Browser selesai. Data: {len(str(browser_result))} karakter")
        except Exception as e:
            logger.error(f"[LANGGRAPH INTEL] BrowserUseTool gagal: {e}", exc_info=True)
            browser_result = f"FAILED|{e}"

        # Format jawaban — kalau SUCCESS, parse + rangkum; kalau FAILED, fallback ke Serper.
        if str(browser_result).startswith("SUCCESS|"):
            parts = str(browser_result).split("|", 2)
            body = parts[2] if len(parts) >= 3 else str(browser_result)
            sys_prompt = (
                f"{realtime_context}\n\nKamu adalah Anisa, asisten B.I.M.A Core. Rangkum hasil browser-use ini "
                f"buat Bima dengan jelas, casual Bahasa Indonesia. Sebutin URL sumber + waktu fetch.\n\n"
                f"Data:\n{body}"
            )
            final_response = await asyncio.to_thread(
                default_llm.invoke,
                [SystemMessage(content=sys_prompt), HumanMessage(content=user_request)]
            )
            temp_data = dict(state.get("temp_data", {}))
            temp_data["last_browser_result"] = body
            active_teams = state.get("active_teams", [])
            has_downstream = any(t in active_teams for t in ["seniman", "admin", "arsip"])
            return {
                "messages": [final_response],
                "is_finished": not has_downstream,
                "temp_data": temp_data,
            }
        else:
            # Browser gagal — log + fallback ke search path biasa
            logger.warning(f"[LANGGRAPH INTEL] Browser fail, fallback ke search: {browser_result[:120]}")
            await notify_progress(state, "⚠️ *Browser gagal, fallback ke search engine...*")

    prompt_search = f"""{realtime_context}

=== HISTORI PERCAKAPAN TERAKHIR ===
{get_recent_context(3)}
===================================

Permintaan terbaru Bima: '{user_request}'

Tugasmu: rumuskan 1 kata kunci pencarian Google yang paling tepat.
- WAJIB pakai konteks histori di atas. Kalau permintaan terbaru cuma jawaban singkat / preferensi (misal "kamera", "yang baru", "5-10jt"), itu LANJUTAN dari pertanyaan sebelumnya — pahami subjek aslinya dari histori.
- Sertakan tahun/bulan terkini kalau permintaan sensitif waktu (harga, tren, berita).
- Contoh: kalau histori bahas "rekomendasi HP gaming kamera bagus" dan jawaban Bima "kamera, baru" → keyword: "HP kamera bagus 2026" — BUKAN "kamera baru".

HANYA TULIS KATA KUNCINYA SAJA."""

    keyword_response = await asyncio.to_thread(
        default_llm.invoke, [HumanMessage(content=prompt_search)]
    )
    keyword = keyword_response.content.strip()

    logger.info(f"[LANGGRAPH INTEL] Mencari: '{keyword}'")
    try:
        search_result = await asyncio.to_thread(search_tool._run, keyword)
        logger.info(f"[LANGGRAPH INTEL] Selesai. Data: {len(str(search_result))} karakter")
    except Exception as e:
        logger.error(f"[LANGGRAPH INTEL] Gagal: {e}")
        search_result = f"Pencarian gagal: {e}"

    system_prompt = f"""Kamu adalah Agen Intel B.I.M.A Core.

{realtime_context}

Berikan rangkuman dan analisis dari data mentah hasil pencarian ini kepada Bima.
Tegaskan kapan data ini di-fetch (sesuai waktu di atas). Kalau ada angka/harga, sebutkan tanggalnya.

Data Mentah:
{search_result}

Jawab dengan gaya asisten (Anisa) yang profesional namun hangat."""

    final_response = await asyncio.to_thread(
        default_llm.invoke,
        [SystemMessage(content=system_prompt), HumanMessage(content=user_request)]
    )

    temp_data = dict(state.get("temp_data", {}))
    temp_data["last_search_result"] = search_result

    active_teams = state.get("active_teams", [])
    has_downstream = any(t in active_teams for t in ["seniman", "admin", "arsip"])

    return {
        "messages": [final_response],
        "is_finished": not has_downstream,
        "temp_data": temp_data
    }
