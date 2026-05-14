import logging
import asyncio
from langchain_core.messages import AIMessage
from core.langgraph_nodes.state import BimaState, notify_progress
from teams.t2_visual import visual_agent
from crewai import Task, Crew

logger = logging.getLogger('bima_core')

async def visual_node(state: BimaState) -> dict:
    await notify_progress(state, "👁️ *Tim Visual lagi analisis file/gambar...*")
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")
    attachment_paths = state.get("attachment_paths", [])

    attachment_info = ""
    if attachment_paths:
        attachment_info = f"\n\nFile sudah didownload ke lokal:\n" + "\n".join(attachment_paths)

    logger.info("[LANGGRAPH VISUAL] Menganalisis file/gambar...")

    task = Task(
        description=f"""{realtime_context}{attachment_info}

        Bima minta: '{user_request}'

        Tugasmu:
        1. Jika ada path file di atas, LANGSUNG baca dengan tool yang sesuai (jangan download ulang).
           - PDF → PDFReader
           - Excel (.xlsx) → ExcelReader
           - Word (.docx) → WordReader
           - TXT/CSV/MD → TextFileReader
           - Gambar (.png/.jpg) → ImageAnalyzerTool
        2. Jika diminta konversi gambar ke HTML → ImageToCodeTool.
        3. Jika ada URL (bukan path lokal) → FileDownloader dulu, lalu baca.
        4. Ekstrak semua data penting dan laporkan lengkap ke Bima.""",
        expected_output="Laporan lengkap isi file atau hasil analisis gambar/dokumen.",
        agent=visual_agent
    )

    crew = Crew(agents=[visual_agent], tasks=[task], verbose=True)
    hasil_raw = await asyncio.to_thread(crew.kickoff)
    hasil_str = str(hasil_raw)

    logger.info(f"[LANGGRAPH VISUAL] Selesai: {hasil_str[:100]}...")

    return {
        "messages": [AIMessage(content=hasil_str)],
        "is_finished": True
    }
