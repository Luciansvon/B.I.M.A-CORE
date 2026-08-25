import logging
import asyncio
import json
from langchain_core.messages import AIMessage
from core.langgraph_nodes.state import BimaState, notify_progress
from teams.t3_arsip import VaultSaveTool, arsip_agent
from crewai import Task, Crew
from config import arsip_llm, arsip_heavy_llm
from core.model_router import clone_agent_with_llm, select_profile

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


def _get_upstream_source(state: BimaState) -> str:
    temp_data = state.get("temp_data", {}) or {}
    if str(temp_data.get("last_search_result", "")).strip():
        return "Intel"
    if str(temp_data.get("last_browser_result", "")).strip():
        return "Browser"
    return "Bima"


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
        payload = {
            "title": user_request.strip() or "Hasil Riset",
            "content": upstream_text,
            "category": "Riset",
            "tags": [],
            "source": _get_upstream_source(state),
        }
        hasil_raw = await asyncio.to_thread(
            VaultSaveTool()._run,
            json.dumps(payload, ensure_ascii=False),
        )
        hasil_str = str(hasil_raw)
        logger.info(f"[LANGGRAPH ARSIP] Save upstream selesai: {hasil_str[:100]}...")
        return {
            "messages": [AIMessage(content=hasil_str)],
            "is_finished": True,
        }

    instruksi = """
Tugasmu:
1. Jika diminta menyimpan: gunakan VaultSaveTool dengan JSON {"title":"...","content":"...","category":"Inbox|Riset|Proyek|Personal|Saham","tags":["..."],"source":"..."}.
2. Jika diminta mencari: gunakan VaultSearchTool.
3. Jika diminta update indeks: gunakan VaultIndexTool."""

    profile = select_profile("arsip", user_request)
    request_agent = clone_agent_with_llm(
        arsip_agent,
        arsip_heavy_llm if profile == "heavy" else arsip_llm,
    )
    logger.info("[MODEL_ROUTER] team=arsip profile=%s", profile)

    task = Task(
        description=f"""{realtime_context}

Bima minta: '{user_request}'
{instruksi}

Berikan jawaban yang ramah dan konfirmasi aksi yang sudah dilakukan.""",
        expected_output="Konfirmasi aksi penyimpanan atau hasil pencarian dari vault.",
        agent=request_agent
    )

    crew = Crew(
        agents=[request_agent],
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
