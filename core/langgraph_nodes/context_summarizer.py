"""Context summarizer node (T1-E).

Trigger via conditional edge dari START — kalau len(messages) > SUMMARIZE_THRESHOLD,
ringkas pesan-pesan lama jadi field `conversation_summary` di state.

Pesan tidak dihapus (avoid RemoveMessage complexity dengan operator.add reducer);
manager + agen yang baca summary cukup pakai field-nya, sisanya ignore.

Feature flag: ENABLE_SUMMARIZATION=true (default true).
"""
from __future__ import annotations

import os
import logging
from langchain_core.messages import SystemMessage, HumanMessage

from core.langgraph_nodes.state import BimaState
from core.langgraph_nodes.llm_config import default_llm

logger = logging.getLogger('bima_core')


def _threshold() -> int:
    try:
        return int(os.environ.get("SUMMARIZE_THRESHOLD", "20"))
    except ValueError:
        return 20


def _keep_last_n() -> int:
    try:
        return int(os.environ.get("SUMMARIZE_KEEP_LAST", "6"))
    except ValueError:
        return 6


async def context_summarizer_node(state: BimaState) -> dict:
    """Summarize older messages → conversation_summary. No-op kalau di bawah threshold."""
    messages = state.get("messages", [])
    threshold = _threshold()
    keep = _keep_last_n()

    if len(messages) <= threshold:
        return {}

    older = messages[:-keep]
    if not older:
        return {}

    existing_summary = state.get("conversation_summary", "") or ""

    convo_text = "\n".join(
        f"{type(m).__name__.replace('Message', '')}: {(getattr(m, 'content', '') or '')[:300]}"
        for m in older
    )

    system = (
        "Kamu summarizer percakapan. Ringkas percakapan ini jadi 4-6 baris bullet "
        "yang capture: topik utama, keputusan yang diambil, info kontekstual penting "
        "(nama, angka, tanggal, file, agent yang dipakai). "
        "Output bahasa Indonesia singkat, no markdown headers."
    )
    user_prompt_parts = []
    if existing_summary:
        user_prompt_parts.append(f"Ringkasan sebelumnya:\n{existing_summary}\n")
    user_prompt_parts.append(f"Percakapan baru untuk dirangkum:\n{convo_text}")
    user_text = "\n".join(user_prompt_parts)

    try:
        resp = default_llm.invoke([SystemMessage(content=system), HumanMessage(content=user_text)])
        new_summary = (resp.content or "").strip()
        if not new_summary:
            return {}
        logger.info(
            f"[SUMMARIZER] {len(messages)} msg, ringkas {len(older)} pesan lama "
            f"→ summary {len(new_summary)} chars"
        )
        return {"conversation_summary": new_summary}
    except Exception as e:
        logger.warning(f"[SUMMARIZER] LLM call gagal, skip summarization: {e}")
        return {}


def should_summarize(state: BimaState) -> str:
    """Conditional entry point router. Return next node name."""
    if os.environ.get("ENABLE_SUMMARIZATION", "true").lower() != "true":
        return "classifier_node"
    messages = state.get("messages", [])
    if len(messages) > _threshold():
        return "context_summarizer_node"
    return "classifier_node"
