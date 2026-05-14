import asyncio
import logging
from langchain_core.messages import AIMessage
from crewai import Task, Crew, Process
from core.langgraph_nodes.state import BimaState, notify_progress
from teams.t9_saham import saham_agent

logger = logging.getLogger('bima_core')


async def saham_node(state: BimaState) -> dict:
    await notify_progress(state, "📈 *Tim Saham lagi analisis market...*")
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")

    task_description = f"""{realtime_context}

Permintaan dari Bima: {user_request}

Lakukan analisis sesuai workflow standar (StockQuote → TechnicalAnalysis → FundamentalAnalysis → DecisionEngine).
Kalau Bima cuma minta harga, cukup StockQuoteTool. Kalau minta sentimen, tambah StockNewsTool.
Akhiri dengan ringkasan eksekutif singkat dan disclaimer DYOR."""

    task = Task(
        description=task_description,
        expected_output="Laporan saham lengkap dalam Bahasa Indonesia, rapi pakai emoji, sertakan disclaimer.",
        agent=saham_agent,
    )

    crew = Crew(
        agents=[saham_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    logger.info("[LANGGRAPH SAHAM] Memulai analisis saham...")
    try:
        result = await asyncio.to_thread(crew.kickoff)
        result_str = str(result)
        logger.info(f"[LANGGRAPH SAHAM] Selesai. Output {len(result_str)} karakter")
    except Exception as e:
        logger.error(f"[LANGGRAPH SAHAM] Gagal: {e}")
        result_str = f"❌ Maaf Bima, analisis saham gagal: {e}"

    return {
        "messages": [AIMessage(content=result_str)],
        "is_finished": True,
    }
