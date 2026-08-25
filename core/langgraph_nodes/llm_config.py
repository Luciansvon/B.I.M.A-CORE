import asyncio
import os
import logging
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import AsyncCallbackHandler
from dotenv import load_dotenv
from core.model_router import DAILY_MODEL, model_profile

load_dotenv()

logger = logging.getLogger('bima_core')


# === Headroom Context Compression ===
# Compress tool output / memory recall / long context sebelum masuk LLM.
# Gate di balik ENABLE_HEADROOM=true. No-op kalau disabled atau headroom gak terinstall.
def compress_context(text: str, target_ratio: float = 0.4) -> str:
    """Compress context via Headroom CCR. Return text as-is kalau disabled/error.

    Args:
        text: raw context string (bisa panjang — agentmemory recall, recent history, dll)
        target_ratio: target compression ratio (0.4 = compress ke ~40% panjang asli)

    Returns:
        Compressed text kalau headroom aktif, original text kalau tidak.
    """
    if not text or len(text) < 200:
        return text  # gak perlu compress teks pendek
    if os.environ.get("ENABLE_HEADROOM", "false").lower() != "true":
        return text
    try:
        from headroom import compress
        compressed = compress(text, target_ratio=target_ratio)
        if compressed and len(compressed) < len(text):
            saved_pct = (1 - len(compressed) / len(text)) * 100
            logger.debug(f"[HEADROOM] Compressed {len(text)}→{len(compressed)} chars ({saved_pct:.0f}% saved)")
            return compressed
        return text
    except ImportError:
        logger.debug("[HEADROOM] headroom not installed, skip compression")
        return text
    except Exception as e:
        logger.debug(f"[HEADROOM] Compression failed (non-fatal): {e}")
        return text

# Menggunakan OpenRouter API (sesuai config.py Anda yang lama)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")


def get_langchain_llm(
    model_name: str = DAILY_MODEL,
    max_tokens: int | None = None,
    *,
    fallbacks: tuple[str, ...] = (),
    reasoning_effort: str | None = None,
) -> ChatOpenAI:
    # LangChain ChatOpenAI kirim model_name apa adanya ke OpenRouter,
    # JANGAN pakai prefix "openrouter/" (itu khusus CrewAI/LiteLLM).
    if model_name.startswith("openrouter/"):
        model_name = model_name.split("/", 1)[1]

    # T1-D: opt-in OpenRouter usage tracking — cost muncul di response.usage.cost
    kwargs = {
        "model": model_name,
        "openai_api_key": OPENROUTER_API_KEY,
        "openai_api_base": "https://openrouter.ai/api/v1",
        "max_retries": 2,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    extra_body: dict[str, object] = {}
    if fallbacks:
        extra_body["models"] = [model_name, *fallbacks]
    if os.environ.get("ENABLE_COST_GUARDRAILS", "false").lower() == "true":
        extra_body["usage"] = {"include": True}
    if extra_body:
        kwargs["extra_body"] = extra_body
    return ChatOpenAI(**kwargs)


def get_team_langchain_llm(team: str, profile: str = "standard") -> ChatOpenAI:
    selected = model_profile(team, profile)
    return get_langchain_llm(
        selected.model,
        fallbacks=selected.fallbacks,
        reasoning_effort=selected.reasoning_effort,
    )


# T1-C: Model Complexity Router — pilih model berdasarkan kompleksitas tugas
_COMPLEXITY_MAP = {
    "routing": model_profile("manager"),
    "standard": model_profile("manager"),
    "heavy": model_profile("mekanik", "heavy"),
}


def get_llm_for_task(complexity: str = "standard") -> ChatOpenAI:
    """Return LLM yang cocok untuk kompleksitas tugas. Default fallback ke default_llm
    kalau ENABLE_MODEL_ROUTER=false.
    """
    if os.environ.get("ENABLE_MODEL_ROUTER", "true").lower() != "true":
        return default_llm
    selected = _COMPLEXITY_MAP.get(complexity, _COMPLEXITY_MAP["standard"])
    return get_langchain_llm(
        selected.model,
        fallbacks=selected.fallbacks,
        reasoning_effort=selected.reasoning_effort,
    )


# Kita inisialisasi LLM utama untuk percobaan ini
default_llm = get_team_langchain_llm("manager")
# Convenience exports (T1-C) — supaya node-node bisa import langsung tanpa router call
fast_llm = get_team_langchain_llm("manager")
heavy_llm = get_team_langchain_llm("mekanik", "heavy")
intel_llm = get_team_langchain_llm("intel")
seniman_llm = get_team_langchain_llm("seniman")


# T1-D: CostTracker callback — capture OpenRouter cost dari response metadata
class CostTracker(AsyncCallbackHandler):
    """Async-safe callback. Parse cost dari response.usage.cost (OpenRouter extra_body
    usage feature) dan akumulasi ke persistent SQLite per user per hari.
    """

    def __init__(self, user_id: str):
        self.user_id = str(user_id)

    async def on_llm_end(self, response, **kwargs):
        try:
            for gen in response.generations:
                for g in gen:
                    msg = getattr(g, "message", None)
                    rmeta = getattr(msg, "response_metadata", {}) if msg else {}
                    if not rmeta:
                        rmeta = getattr(g, "generation_info", {}) or {}
                    usage = (rmeta or {}).get("usage") or {}
                    cost = usage.get("cost") or usage.get("total_cost")
                    if cost is None:
                        # OpenAI ChatOpenAI kadang nest usage di message.usage_metadata
                        umeta = getattr(msg, "usage_metadata", {}) if msg else {}
                        cost = (umeta or {}).get("cost")
                    if cost:
                        from core.gen_rate_limit import add_actual_cost
                        await asyncio.to_thread(
                            add_actual_cost,
                            self.user_id,
                            float(cost),
                        )
                        return
        except Exception as e:
            logger.debug(f"[CostTracker] Parse cost gagal (non-fatal): {e}")
