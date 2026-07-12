import logging
import asyncio
from langchain_core.messages import AIMessage
from core.langgraph_nodes.state import BimaState, notify_progress
from teams.t3_arsip import arsip_agent
from crewai import Task, Crew

logger = logging.getLogger('bima_core')


def _get_upstream_data(state: BimaState, limit: int = 3000) -> str:
    temp_data = state.get("temp_data", {}) or {}
    for key in ("last_search_result", "last_browser_result"):
        raw = temp_data.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text[:limit]
    return ""


async def arsip_node(state: BimaState) -> dict:
    """
    Node untuk menangani penyimpanan dan pencarian data di Vault Obsidian menggunakan Arsip Agent.
    """
    await notify_progress(state, "💾 *Tim Arsip lagi simpan ke vault Obsidian...*")
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")

    logger.info("[LANGGRAPH ARSIP] Mengakses vault Obsidian...")

    upstream_text = _get_upstream_data(state)
    has_upstream = bool(upstream_text)

    if has_upstream:
        instruksi = f"""
=== DATA DARI TIM SEBELUMNYA ===
{upstream_text}
================================

PRIORITAS WAJIB:
- Karena tim sebelumnya sudah kasih data di atas, tugasmu **LANGSUNG SIMPAN** ke vault pakai VaultSaveTool.
- JANGAN panggil VaultSearchTool dulu — datanya sudah lengkap di atas.
- Format input VaultSaveTool HARUS JSON: {{"title": "judul ringkas berdasar permintaan Bima", "content": "rangkum data dari tim sebelumnya"}}
- Setelah save berhasil, balas dengan konfirmasi ramah ke Bima."""
    else:
        instruksi = """
Tugasmu:
1. Jika diminta menyimpan: gunakan VaultSaveTool.
2. Jika diminta mencari: gunakan VaultSearchTool.
3. Jika diminta update indeks: gunakan VaultIndexTool."""

    task = Task(
        description=f"""{realtime_context}

Bima minta: '{user_request}'
{instruksi}

Berikan jawaban yang ramah dan konfirmasi aksi yang sudah dilakukan.""",
        expected_output="Konfirmasi aksi penyimpanan atau hasil pencarian dari vault.",
        agent=arsip_agent
    )

    crew = Crew(
        agents=[arsip_agent],
        tasks=[task],
        verbose=True
    )

    # Eksekusi CrewAI secara asynchronous
    hasil_raw = await asyncio.to_thread(crew.kickoff)
    hasil_str = str(hasil_raw)
    
    logger.info(f"[LANGGRAPH ARSIP] Tugas selesai: {hasil_str[:100]}...")

    return {
        "messages": [AIMessage(content=hasil_str)],
        "is_finished": True
    }
