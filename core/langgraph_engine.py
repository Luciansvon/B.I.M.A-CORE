import logging
import os
from pathlib import Path
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
from core.langgraph_nodes.context_summarizer import context_summarizer_node, should_summarize
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
workflow.add_node("observer_node", make_resilient(observer_node, "observer_node", timeout=90))
workflow.add_node("kodok_node", make_resilient(kodok_node, "kodok_node", timeout=120))
workflow.add_node("canvas_node", make_resilient(canvas_node, "canvas_node", timeout=180))
workflow.add_node("memory_finalizer_node", make_resilient(memory_finalizer_node, "memory_finalizer_node", timeout=10))
workflow.add_node("context_summarizer_node", make_resilient(context_summarizer_node, "context_summarizer_node", timeout=30))

# 3. Edges
# T1-E: Conditional entry — summarize older messages kalau > threshold, baru ke classifier
workflow.set_conditional_entry_point(
    should_summarize,
    {
        "context_summarizer_node": "context_summarizer_node",
        "classifier_node": "classifier_node",
    },
)
workflow.add_edge("context_summarizer_node", "classifier_node")

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

# 4. Compile Graph (fallback: no checkpointing — overridden per-loop oleh _ensure_app())
bima_app = workflow.compile()

# === Async checkpointing state (T1-A) ===
# Per-event-loop cache: WA bridge (uvicorn port 8001) + Discord bot + dashboard
# semua jalan di event loop berbeda. AsyncSqliteSaver pakai asyncio.Lock yang
# bound ke loop tempat dia di-instantiate — kalau dipakai di loop lain → RuntimeError.
# Solusi: tiap event loop punya compiled app + aiosqlite connection sendiri.
_CHECKPOINT_DB = Path(__file__).parent.parent / "memory" / "checkpoints.db"
_app_by_loop: dict[int, object] = {}
_conn_by_loop: dict[int, object] = {}


async def _ensure_app():
    """Get atau create compiled app untuk event loop aktif. Idempotent + loop-safe."""
    global bima_app
    loop_id = id(asyncio.get_running_loop())
    if loop_id in _app_by_loop:
        return _app_by_loop[loop_id]

    if os.environ.get("ENABLE_CHECKPOINTING", "true").lower() != "true":
        app = workflow.compile()
        _app_by_loop[loop_id] = app
        bima_app = app
        return app

    try:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        _CHECKPOINT_DB.parent.mkdir(exist_ok=True)
        conn = await aiosqlite.connect(str(_CHECKPOINT_DB))
        saver = AsyncSqliteSaver(conn)
        app = workflow.compile(checkpointer=saver)
        _conn_by_loop[loop_id] = conn
        _app_by_loop[loop_id] = app
        bima_app = app
        logger.info(f"[LANGGRAPH] ✅ Per-loop checkpointing aktif (loop_id={loop_id}) → {_CHECKPOINT_DB.name}")
        return app
    except Exception as e:
        logger.error(f"[LANGGRAPH] Init checkpointer gagal (loop_id={loop_id}), fallback non-checkpoint: {e}", exc_info=True)
        app = workflow.compile()
        _app_by_loop[loop_id] = app
        bima_app = app
        return app


async def init_engine():
    """Backward-compat — ensure app untuk Discord on_ready loop."""
    await _ensure_app()


async def shutdown_engine():
    """Close SEMUA per-loop checkpoint connections."""
    for loop_id, conn in list(_conn_by_loop.items()):
        try:
            await conn.close()
            logger.info(f"[LANGGRAPH] Closed checkpoint connection (loop_id={loop_id})")
        except Exception as e:
            logger.warning(f"[LANGGRAPH] Close conn error (loop_id={loop_id}): {e}")
    _conn_by_loop.clear()
    _app_by_loop.clear()


_STREAM_DEBOUNCE_S = 0.6
_DISCORD_MAX = 1900


async def run_langgraph_engine(user_request: str, konteks_waktu: str, attachment_paths: list = None, progress_callback=None, discord_user_id: str = "", source_channel: str = ""):
    # T1-A: progress_callback TIDAK masuk state — function gak msgpack-serializable,
    # akan crash checkpointer aput(). Register ke module dict, lookup di notify_progress.
    initial_state = {
        "messages": [],
        "user_request": user_request,
        "realtime_context": konteks_waktu,
        "attachment_paths": attachment_paths or [],
        "current_plan": "",
        "active_teams": [],
        "temp_data": {},
        "is_finished": False,
        "discord_user_id": discord_user_id,
        "source_channel": source_channel,
    }
    _engine_thread_id = f"{discord_user_id or 'anon'}_{source_channel or 'unknown'}"
    if progress_callback:
        from core.langgraph_nodes.state import register_progress_callback
        register_progress_callback(_engine_thread_id, progress_callback)
    if source_channel:
        logger.info(f"[LANGGRAPH] source_channel={source_channel}")

    logger.info("[LANGGRAPH] Memulai Orkestrasi...")
    emit('reset', message=f'Permintaan baru: "{user_request[:80]}"')
    emit('agent_state', agent='manager', state='thinking', message='Menganalisis permintaan Bima...')

    final_state = None
    stream_buffer = ""
    last_emit_t = 0.0

    # T1-A: thread_id buat checkpoint continuity (per user + channel)
    # Kalau checkpointer aktif, state percakapan persist antar restart bot.
    thread_id = f"{discord_user_id or 'anon'}_{source_channel or 'unknown'}"
    config: dict = {"configurable": {"thread_id": thread_id}}

    # T1-D: attach CostTracker callback kalau cost guardrails aktif
    if os.environ.get("ENABLE_COST_GUARDRAILS", "false").lower() == "true" and discord_user_id:
        try:
            from core.langgraph_nodes.llm_config import CostTracker
            config["callbacks"] = [CostTracker(discord_user_id)]
        except Exception as e:
            logger.warning(f"[LANGGRAPH] CostTracker attach gagal (non-fatal): {e}")

    # T1-A fix: ensure app untuk event loop aktif (WA/Dashboard/Discord punya loop terpisah)
    app = await _ensure_app()

    try:
        async for event in app.astream_events(initial_state, version="v2", config=config):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                token = getattr(chunk, "content", "") or ""
                if token:
                    stream_buffer += token
                    emit('llm_token', token=token)
                    # T2-C: gate Discord streaming behind flag (default true)
                    streaming_enabled = os.environ.get("ENABLE_STREAMING_DISCORD", "true").lower() == "true"
                    if progress_callback and streaming_enabled and len(stream_buffer) > 100:
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
            final_state = await app.ainvoke(initial_state, config=config)
        except Exception as e2:
            logger.error(f"[LANGGRAPH] ainvoke fallback juga gagal: {e2}", exc_info=True)
    finally:
        logger.info("[LANGGRAPH] Orkestrasi Selesai!")
        emit('reset', message='Orkestrasi selesai, semua agent kembali idle')
        try:
            from core.langgraph_nodes.state import unregister_progress_callback
            unregister_progress_callback(_engine_thread_id)
        except Exception:
            pass

    if final_state is None:
        if stream_buffer:
            return stream_buffer  # at least kasih hasil stream parsial
        return "Maaf, Anisa bingung memproses permintaan ini."

    messages = final_state.get("messages", [])
    if messages:
        return messages[-1].content
    return "Maaf, Anisa bingung memproses permintaan ini."
