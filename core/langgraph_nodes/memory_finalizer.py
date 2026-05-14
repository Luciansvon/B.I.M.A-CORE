"""Memory finalizer node — jalan sebelum END di LangGraph.

Tugas: ambil last AIMessage dari state.messages + state.user_request, kirim ke
agentmemory via /agentmemory/remember. Fire-and-forget; gagal tidak nge-block
response Discord.
"""
import logging

from langchain_core.messages import AIMessage

from core import agentmemory_client
from core.event_bus import emit
from core.langgraph_nodes.state import BimaState

logger = logging.getLogger('bima_core')


async def memory_finalizer_node(state: BimaState) -> dict:
    user_request = (state.get("user_request") or "").strip()
    messages = state.get("messages") or []

    # Ambil last AIMessage (output assistant terakhir). Skip kalau gak ada.
    reply_text = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            reply_text = (getattr(msg, "content", "") or "").strip()
            if reply_text:
                break

    if not user_request or not reply_text:
        # Gak ada konten yang layak disimpan (mis. error early-exit)
        return {}

    try:
        await agentmemory_client.save(user_request, reply_text)
        emit('agent_state', agent='memory', state='done', message='💾 Memory tersimpan')
    except Exception as e:
        # Defensive — agentmemory_client.save() udah swallow error sendiri,
        # tapi untuk jaga-jaga kalau import/network fail tak terduga.
        logger.warning(f"[MEMORY_FINALIZER] Save gagal: {e}")

    return {}
