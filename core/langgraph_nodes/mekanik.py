import logging
import asyncio
import re
from pathlib import Path
from langchain_core.messages import AIMessage
from core.langgraph_nodes.state import BimaState, notify_progress
from teams.t8_mekanik import mekanik_agent
from crewai import Task, Crew
from config import mekanik_heavy_llm, mekanik_llm
from core.model_router import clone_agent_with_llm, select_profile

logger = logging.getLogger('bima_core')


async def mekanik_node(state: BimaState) -> dict:
    """
    Node untuk menangani eksekusi kode, debugging otomatis,
    operasi Git, dan security scanning.
    """
    await notify_progress(state, "🔧 *Tim Mekanik lagi eksekusi kode & debug...*")
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")
    temp_data = state.get("temp_data", {})

    # Ambil data dari node sebelumnya (jika ada kode dari seniman/admin)
    prev_data = temp_data.get("last_search_result", "")
    data_context = f"\n\n=== DATA/KODE DARI TIM SEBELUMNYA ===\n{prev_data}\n=== AKHIR DATA ===" if prev_data else ""

    logger.info("[LANGGRAPH MEKANIK] Memproses permintaan coding/debug...")

    profile = select_profile("mekanik", user_request)
    request_agent = clone_agent_with_llm(
        mekanik_agent,
        mekanik_heavy_llm if profile == "heavy" else mekanik_llm,
    )
    logger.info("[MODEL_ROUTER] team=mekanik profile=%s", profile)

    task = Task(
        description=f"""{realtime_context}{data_context}

        Bima minta: '{user_request}'

        Tugasmu:
        1. Jika diminta jalankan/test kode Python → pakai CodeExecutorTool.
        2. Jika kode error dan perlu di-debug → pakai AutoRetryTool (auto-fix hingga 5x).
        3. Jika diminta simpan file hasil → pakai FileSaverTool (format: 'namafile.ext|konten').
        4. Jika diminta operasi Git:
           - Status → 'status'
           - Commit → 'commit|pesan commit'
           - Push → 'push'
        5. Jika diminta scan keamanan kode → pakai SecurityScannerTool.

        Workflow ideal:
        a. Scan dulu (SecurityScannerTool) jika kode dari luar/berisiko
        b. Eksekusi (CodeExecutorTool)
        c. Jika error → AutoRetryTool
        d. Jika sukses → simpan (FileSaverTool)
        e. Laporkan hasil lengkap: apa yang error, berapa retry, hasil akhir.

        WAJIB: Jangan menyerah sebelum 5x percobaan!""",
        expected_output="Hasil eksekusi kode beserta status berhasil/gagal dan path file jika disimpan.",
        agent=request_agent
    )

    crew = Crew(
        agents=[request_agent],
        tasks=[task],
        verbose=True
    )

    from core.permission_gate import current_user_id
    user_id = state.get("discord_user_id", "anon")
    current_user_id.set(user_id)

    hasil_raw = await asyncio.to_thread(crew.kickoff)
    hasil_str = str(hasil_raw)

    logger.info(f"[LANGGRAPH MEKANIK] Output: {hasil_str[:200]}...")

    # Parse output untuk format yang lebih bersih
    success_match = re.search(r'SUCCESS\|([^\|\n\r]+)\|([^\n\r]+)', hasil_str)
    if success_match:
        file_path = success_match.group(1).strip()
        keterangan = success_match.group(2).strip()
        filename = Path(file_path).name
        response_content = f"""✅ Kode berhasil dieksekusi, Bima!

🔧 **{filename}**
{keterangan}

SUCCESS|{file_path}|{keterangan}"""
    else:
        response_content = hasil_str

    return {
        "messages": [AIMessage(content=response_content)],
        "is_finished": True
    }
