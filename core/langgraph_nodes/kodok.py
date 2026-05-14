"""Kodok node — handler buat permintaan code understanding di repo BIMA_CORE."""
import asyncio
import logging

from crewai import Crew, Task
from langchain_core.messages import AIMessage

from core.langgraph_nodes.state import BimaState, notify_progress
from teams.t10_kodok import kodok_agent

logger = logging.getLogger("bima_core")


async def kodok_node(state: BimaState) -> dict:
    """Handle pertanyaan soal codebase BIMA_CORE (jelasin file, cari symbol, summary modul)."""
    await notify_progress(state, "🔍 *Kodok lagi baca repo buat lo...*")

    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")

    logger.info("[LANGGRAPH KODOK] Memproses permintaan code understanding...")

    task = Task(
        description=f"""{realtime_context}

        Bima minta: '{user_request}'

        Tugasmu:
        1. Identifikasi tipe permintaan:
           - Penjelasan file spesifik? → RepoExplainTool(path)
           - Cari fungsi/class/symbol? → RepoSearchSymbolTool(query)
           - Overview folder/modul? → RepoSummarizeTool(dir)
           - Cek status index? → RepoIndexStatsTool()
        2. Panggil tool yang sesuai. Boleh chain (mis. summarize dulu, baru explain file paling relevan).
        3. BACA hasil tool, lalu jelasin dengan Bahasa Indonesia casual.
        4. Selalu sebutin file:line untuk referensi konkret.
        5. Kalo gak ketemu, jujur bilang "gak ke-index" — jangan ngarang.

        Output: jawaban informatif, max 1500 kata.""",
        expected_output="Penjelasan codebase yang akurat (didukung output tool), pakai Bahasa Indonesia casual.",
        agent=kodok_agent,
    )

    crew = Crew(agents=[kodok_agent], tasks=[task], verbose=True)
    hasil_raw = await asyncio.to_thread(crew.kickoff)
    hasil_str = str(hasil_raw)

    logger.info(f"[LANGGRAPH KODOK] Tugas selesai: {hasil_str[:100]}...")

    return {
        "messages": [AIMessage(content=hasil_str)],
        "is_finished": True,
    }
