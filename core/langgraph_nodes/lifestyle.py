import logging
import asyncio
from langchain_core.messages import AIMessage
from core.langgraph_nodes.state import BimaState, notify_progress
from teams.t6_lifestyle import lifestyle_agent
from crewai import Task, Crew

logger = logging.getLogger('bima_core')


async def lifestyle_node(state: BimaState) -> dict:
    """
    Node untuk menangani permintaan lifestyle: cuaca, jadwal, YouTube,
    jarak tempuh, dan kebutuhan personal Bima.
    """
    await notify_progress(state, "🎮 *Tim Lifestyle lagi cariin info buat Bima...*")
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")

    logger.info("[LANGGRAPH LIFESTYLE] Memproses permintaan lifestyle...")

    task = Task(
        description=f"""{realtime_context}

        Bima minta: '{user_request}'

        Tugasmu:
        1. Jika minta info cuaca → pakai CuacaTool (input: nama kota).
        2. Jika minta cari video/tutorial → pakai YouTubeSearchTool.
        3. Jika minta atur jadwal → pakai ScheduleManagerTool:
           - Tambah: 'add|tanggal waktu, kegiatan'
           - Lihat: 'list|'
           - Hapus semua: 'clear|'
        4. Jika minta estimasi jarak → pakai MapsDistanceTool (format: 'asal|tujuan').
        5. Jika minta rekomendasi umum (kafe, parfum, game build, dll) → pakai SerperDevTool.

        Berikan jawaban yang santai tapi informatif, kayak teman yang tau segalanya.""",
        expected_output="Jawaban informatif dan ramah sesuai permintaan lifestyle Bima.",
        agent=lifestyle_agent
    )

    crew = Crew(
        agents=[lifestyle_agent],
        tasks=[task],
        verbose=True
    )

    hasil_raw = await asyncio.to_thread(crew.kickoff)
    hasil_str = str(hasil_raw)

    logger.info(f"[LANGGRAPH LIFESTYLE] Tugas selesai: {hasil_str[:100]}...")

    return {
        "messages": [AIMessage(content=hasil_str)],
        "is_finished": True
    }
