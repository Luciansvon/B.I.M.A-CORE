import logging
from langgraph.graph import StateGraph, END
from core.langgraph_nodes.state import BimaState
from core.langgraph_nodes.manager import manager_node
from core.langgraph_nodes.intent_classifier import intent_classifier_node, route_from_classifier as _route_from_classifier_raw
from core.langgraph_nodes.intel import intel_node
from core.langgraph_nodes.seniman import seniman_node
from core.langgraph_nodes.admin import admin_node
from core.langgraph_nodes.arsip import arsip_node
from core.langgraph_nodes.visual import visual_node
from core.langgraph_nodes.lifestyle import lifestyle_node
from core.langgraph_nodes.mekanik import mekanik_node
from core.langgraph_nodes.saham import saham_node
from core.langgraph_nodes.observer import observer_node
from core.langgraph_nodes.kodok import kodok_node
from core.langgraph_nodes.canvas import canvas_node
from core.langgraph_nodes.memory_finalizer import memory_finalizer_node
from core.event_bus import emit
import asyncio
from langchain_core.messages import AIMessage

logger = logging.getLogger('bima_core')

def make_resilient(node_fn, node_name: str, max_retries: int = 2, timeout: int = 300):
    async def wrapper(state: BimaState):
        for attempt in range(max_retries):
            try:
                return await asyncio.wait_for(node_fn(state), timeout=timeout)
            except asyncio.TimeoutError:
                err_msg = f"Timeout {timeout}s"
                logger.error(f"[{node_name}] {err_msg}")
                emit('agent_state', agent=node_name.replace('_node', ''), state='error', message=err_msg)
            except Exception as e:
                err_msg = str(e)
                logger.error(f"[{node_name}] Error: {err_msg}")
                emit('agent_state', agent=node_name.replace('_node', ''), state='error', message=err_msg)
                
            if attempt == max_retries - 1:
                return {
                    "messages": [AIMessage(content=f"❌ Maaf Bima, tim {node_name.replace('_node', '').title()} mengalami kendala internal dan tidak bisa menyelesaikan tugasnya.")],
                    "is_finished": True
                }
            await asyncio.sleep(2)
    return wrapper

def _delegate(from_agent: str, to_agent: str, reason: str = ""):
    """Emit pasangan event: from_agent talking + delegation arrow + to_agent working."""
    emit('agent_state', agent=from_agent, state='talking', message=f'Selesai, oper ke {to_agent}')
    emit('delegation', **{'from': from_agent, 'to': to_agent, 'reason': reason})
    emit('agent_state', agent=to_agent, state='working', message='')

# Urutan eksekusi tim: intel → arsip → seniman → admin
# Setiap router hanya maju ke tim berikutnya dalam urutan ini.

def route_from_manager(state: BimaState) -> str:
    if state.get("is_finished"):
        logger.info("[LANGGRAPH ROUTER] Manager memutuskan: Selesai (Langsung Balas)")
        emit('agent_state', agent='manager', state='talking', message='Selesai, langsung balas Bima')
        return END

    active_teams = state.get("active_teams", [])
    if "intel" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Manager → Node Intel")
        _delegate('manager', 'intel', reason=', '.join(active_teams))
        return "intel_node"
    if "arsip" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Manager → Node Arsip")
        _delegate('manager', 'arsip', reason=', '.join(active_teams))
        return "arsip_node"
    if "seniman" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Manager → Node Seniman")
        _delegate('manager', 'seniman', reason=', '.join(active_teams))
        return "seniman_node"
    if "admin" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Manager → Node Admin")
        _delegate('manager', 'admin', reason=', '.join(active_teams))
        return "admin_node"
    if "visual" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Manager → Node Visual")
        _delegate('manager', 'visual', reason=', '.join(active_teams))
        return "visual_node"
    if "lifestyle" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Manager → Node Lifestyle")
        _delegate('manager', 'lifestyle', reason=', '.join(active_teams))
        return "lifestyle_node"
    if "mekanik" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Manager → Node Mekanik")
        _delegate('manager', 'mekanik', reason=', '.join(active_teams))
        return "mekanik_node"
    if "saham" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Manager → Node Saham")
        _delegate('manager', 'saham', reason=', '.join(active_teams))
        return "saham_node"
    if "kodok" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Manager → Node Kodok")
        _delegate('manager', 'kodok', reason=', '.join(active_teams))
        return "kodok_node"
    if "canvas" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Manager → Node Canvas")
        _delegate('manager', 'canvas', reason=', '.join(active_teams))
        return "canvas_node"

    logger.info("[LANGGRAPH ROUTER] Fallback: END")
    return END

def route_from_intel(state: BimaState) -> str:
    active_teams = state.get("active_teams", [])
    if "arsip" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Intel selesai → Node Arsip")
        _delegate('intel', 'arsip')
        return "arsip_node"
    if "seniman" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Intel selesai → Node Seniman")
        _delegate('intel', 'seniman')
        return "seniman_node"
    if "admin" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Intel selesai → Node Admin")
        _delegate('intel', 'admin')
        return "admin_node"
    emit('agent_state', agent='intel', state='talking', message='Riset selesai')
    return END

def route_from_arsip(state: BimaState) -> str:
    active_teams = state.get("active_teams", [])
    if "seniman" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Arsip selesai → Node Seniman")
        _delegate('arsip', 'seniman')
        return "seniman_node"
    if "admin" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Arsip selesai → Node Admin")
        _delegate('arsip', 'admin')
        return "admin_node"
    emit('agent_state', agent='arsip', state='talking', message='Vault selesai')
    return END

def route_from_classifier(state: BimaState) -> str:
    target = _route_from_classifier_raw(state)
    if target != "manager_node":
        agent = target.replace("_node", "")
        logger.info(f"[LANGGRAPH ROUTER] Classifier fast-path → {agent}")
        emit('agent_state', agent='manager', state='talking', message=f'Fast-path → {agent}')
        emit('delegation', **{'from': 'manager', 'to': agent, 'reason': 'fast-path classifier'})
        emit('agent_state', agent=agent, state='working', message='')
    return target


def route_from_seniman(state: BimaState) -> str:
    active_teams = state.get("active_teams", [])
    if "admin" in active_teams:
        logger.info("[LANGGRAPH ROUTER] Seniman selesai → Node Admin")
        _delegate('seniman', 'admin')
        return "admin_node"
    emit('agent_state', agent='seniman', state='talking', message='Visual selesai')
    return END

# 1. Inisialisasi Graph
workflow = StateGraph(BimaState)

# 2. Nodes
workflow.add_node("classifier_node", intent_classifier_node)
workflow.add_node("manager_node", make_resilient(manager_node, "manager_node", timeout=60))
workflow.add_node("intel_node", make_resilient(intel_node, "intel_node"))
workflow.add_node("seniman_node", make_resilient(seniman_node, "seniman_node"))
workflow.add_node("admin_node", make_resilient(admin_node, "admin_node"))
workflow.add_node("arsip_node", make_resilient(arsip_node, "arsip_node"))
workflow.add_node("visual_node", make_resilient(visual_node, "visual_node"))
workflow.add_node("lifestyle_node", make_resilient(lifestyle_node, "lifestyle_node"))
workflow.add_node("mekanik_node", make_resilient(mekanik_node, "mekanik_node"))
workflow.add_node("saham_node", make_resilient(saham_node, "saham_node"))
workflow.add_node("observer_node", make_resilient(observer_node, "observer_node", timeout=30))
workflow.add_node("kodok_node", make_resilient(kodok_node, "kodok_node", timeout=120))
workflow.add_node("canvas_node", make_resilient(canvas_node, "canvas_node", timeout=180))
workflow.add_node("memory_finalizer_node", make_resilient(memory_finalizer_node, "memory_finalizer_node", timeout=10))

# 3. Edges
workflow.set_entry_point("classifier_node")

workflow.add_conditional_edges(
    "classifier_node",
    route_from_classifier,
    {
        "manager_node": "manager_node",
        "intel_node": "intel_node",
        "arsip_node": "arsip_node",
        "seniman_node": "seniman_node",
        "admin_node": "admin_node",
        "visual_node": "visual_node",
        "lifestyle_node": "lifestyle_node",
        "mekanik_node": "mekanik_node",
        "saham_node": "saham_node",
        "observer_node": "observer_node",
        "kodok_node": "kodok_node",
        "canvas_node": "canvas_node",
    }
)

workflow.add_conditional_edges(
    "manager_node",
    route_from_manager,
    {
        "intel_node": "intel_node",
        "arsip_node": "arsip_node",
        "seniman_node": "seniman_node",
        "admin_node": "admin_node",
        "visual_node": "visual_node",
        "lifestyle_node": "lifestyle_node",
        "mekanik_node": "mekanik_node",
        "saham_node": "saham_node",
        "kodok_node": "kodok_node",
        "canvas_node": "canvas_node",
        END: "memory_finalizer_node"
    }
)

workflow.add_conditional_edges(
    "intel_node",
    route_from_intel,
    {"arsip_node": "arsip_node", "seniman_node": "seniman_node", "admin_node": "admin_node", END: "memory_finalizer_node"}
)

workflow.add_conditional_edges(
    "arsip_node",
    route_from_arsip,
    {"seniman_node": "seniman_node", "admin_node": "admin_node", END: "memory_finalizer_node"}
)

workflow.add_conditional_edges(
    "seniman_node",
    route_from_seniman,
    {"admin_node": "admin_node", END: "memory_finalizer_node"}
)

workflow.add_edge("admin_node", "memory_finalizer_node")
workflow.add_edge("visual_node", "memory_finalizer_node")
workflow.add_edge("lifestyle_node", "memory_finalizer_node")
workflow.add_edge("kodok_node", "memory_finalizer_node")
workflow.add_edge("canvas_node", "memory_finalizer_node")
workflow.add_edge("mekanik_node", "memory_finalizer_node")
workflow.add_edge("saham_node", "memory_finalizer_node")
workflow.add_edge("observer_node", "memory_finalizer_node")
workflow.add_edge("memory_finalizer_node", END)

# 4. Compile Graph
bima_app = workflow.compile()

_STREAM_DEBOUNCE_S = 0.6
_DISCORD_MAX = 1900


async def run_langgraph_engine(user_request: str, konteks_waktu: str, attachment_paths: list = None, progress_callback=None, discord_user_id: str = "", source_channel: str = ""):
    initial_state = {
        "messages": [],
        "user_request": user_request,
        "realtime_context": konteks_waktu,
        "attachment_paths": attachment_paths or [],
        "current_plan": "",
        "active_teams": [],
        "temp_data": {},
        "is_finished": False,
        "progress_callback": progress_callback,
        "discord_user_id": discord_user_id,
        "source_channel": source_channel,
    }
    if source_channel:
        logger.info(f"[LANGGRAPH] source_channel={source_channel}")

    logger.info("[LANGGRAPH] Memulai Orkestrasi...")
    emit('reset', message=f'Permintaan baru: "{user_request[:80]}"')
    emit('agent_state', agent='manager', state='thinking', message='Menganalisis permintaan Bima...')

    final_state = None
    stream_buffer = ""
    last_emit_t = 0.0

    try:
        async for event in bima_app.astream_events(initial_state, version="v2"):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                token = getattr(chunk, "content", "") or ""
                if token:
                    stream_buffer += token
                    emit('llm_token', token=token)
                    if progress_callback:
                        now = asyncio.get_event_loop().time()
                        if now - last_emit_t > _STREAM_DEBOUNCE_S:
                            last_emit_t = now
                            body = stream_buffer[:_DISCORD_MAX]
                            if len(stream_buffer) > _DISCORD_MAX:
                                body += "..."
                            try:
                                await progress_callback(body)
                            except Exception as e:
                                logger.warning(f"[STREAM] progress_callback gagal: {e}")
            elif kind == "on_chain_end":
                out = event.get("data", {}).get("output")
                if isinstance(out, dict) and "messages" in out:
                    final_state = out
    except Exception as e:
        logger.error(f"[LANGGRAPH] astream_events error, fallback ke ainvoke: {e}", exc_info=True)
        try:
            final_state = await bima_app.ainvoke(initial_state)
        except Exception as e2:
            logger.error(f"[LANGGRAPH] ainvoke fallback juga gagal: {e2}", exc_info=True)
    finally:
        logger.info("[LANGGRAPH] Orkestrasi Selesai!")
        emit('reset', message='Orkestrasi selesai, semua agent kembali idle')

    if final_state is None:
        if stream_buffer:
            return stream_buffer  # at least kasih hasil stream parsial
        return "Maaf, Anisa bingung memproses permintaan ini."

    messages = final_state.get("messages", [])
    if messages:
        return messages[-1].content
    return "Maaf, Anisa bingung memproses permintaan ini."
