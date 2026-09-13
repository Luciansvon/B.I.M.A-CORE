"""Model profiles and local request classification for BIMA_CORE agents."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Final
from dotenv import load_dotenv

load_dotenv()

COMBO_MODEL_NAME: Final = os.environ.get("NINEROUTER_MODEL", "Combowombo")
USE_9ROUTER: Final = True

# Urutan model dalam kombinasi 9Router "Combowombo":
COMBOWOMBO_MODELS: Final[tuple[str, ...]] = (
    "ag/gemini-3.8-flash-high",
    "openrouter/deepseek/deepseek-v4.1-flash",
    "openrouter/z-ai/glm-5.3-flash",
    "cx/gpt-5.6-luna",
    "openrouter/openai/gpt-5.6-luna-pro:batch",
    "openrouter/qwen/qwen3.8-flash",
    "ag/claude-opus-4-6-thinking",
    "openrouter/anthropic/claude-sonnet-5",
    "openrouter/deepseek/deepseek-v4-flash-0731",
    "openrouter/qwen/qwen3-embedding-8b",
)

# Model spesifik untuk masing-masing peran / tim:
DAILY_MODEL: Final = (
    "ag/gemini-3.8-flash-high"
    if USE_9ROUTER
    else os.environ.get("DAILY_MODEL", "deepseek/deepseek-v4-flash-0731")
)
HEAVY_MODEL: Final = (
    "ag/claude-opus-4-6-thinking"
    if USE_9ROUTER
    else os.environ.get("HEAVY_MODEL", "deepseek/deepseek-v4-pro-0813")
)
VISUAL_MODEL: Final = (
    "ag/gemini-3.8-flash-high"
    if USE_9ROUTER
    else "google/gemini-3.7-flash"
)
VISUAL_FALLBACK_MODEL: Final = (
    COMBO_MODEL_NAME
    if USE_9ROUTER
    else "google/gemini-3.1-flash-lite"
)
INTEL_MODEL: Final = (
    "ag/gemini-3.8-flash-high"
    if USE_9ROUTER
    else "qwen/qwen3.8-27b"
)
ADMIN_HEAVY_MODEL: Final = (
    "ag/claude-opus-4-6-thinking"
    if USE_9ROUTER
    else "anthropic/claude-sonnet-5"
)
ADMIN_MODEL: Final = ADMIN_HEAVY_MODEL
THREADS_MODEL: Final = (
    "ag/gemini-3.8-flash-high"
    if USE_9ROUTER
    else "ag/gemini-3.8-flash-high"
)
IMAGE_MODEL: Final = (
    "ag/gemini-3.1-flash-image"
    if USE_9ROUTER
    else "google/gemini-3.1-flash-image"
)
SECURITY_MODEL: Final = (
    "ag/claude-opus-4-6-thinking"
    if USE_9ROUTER
    else "openai/gpt-5.6-luna-pro"
)
SAHAM_MODEL: Final = (
    "openrouter/deepseek/deepseek-v4.1-flash"
    if USE_9ROUTER
    else HEAVY_MODEL
)
KODOK_MODEL: Final = (
    "openrouter/deepseek/deepseek-v4.1-flash"
    if USE_9ROUTER
    else HEAVY_MODEL
)
ARSIP_MODEL: Final = (
    "openrouter/deepseek/deepseek-v4-flash-0731"
    if USE_9ROUTER
    else DAILY_MODEL
)
LIFESTYLE_MODEL: Final = (
    "openrouter/z-ai/glm-5.3-flash"
    if USE_9ROUTER
    else DAILY_MODEL
)

MODEL_INPUT_COST_PER_M: Final[dict[str, float]] = {
    DAILY_MODEL: 0.035,
    HEAVY_MODEL: 0.66,
}


@dataclass(frozen=True, slots=True)
class ModelProfile:
    model: str
    fallbacks: tuple[str, ...] = ()
    reasoning_effort: str | None = None


_COMBO_FALLBACK: Final[tuple[str, ...]] = (COMBO_MODEL_NAME,) if USE_9ROUTER else (DAILY_MODEL,)

_DAILY = ModelProfile(DAILY_MODEL, _COMBO_FALLBACK)
_VISUAL = ModelProfile(VISUAL_MODEL, _COMBO_FALLBACK)
_INTEL = ModelProfile(INTEL_MODEL, ("openrouter/z-ai/glm-5.3-flash", COMBO_MODEL_NAME) if USE_9ROUTER else (DAILY_MODEL,))
_ADMIN = ModelProfile(ADMIN_HEAVY_MODEL, _COMBO_FALLBACK)
_HEAVY = ModelProfile(HEAVY_MODEL, _COMBO_FALLBACK)
_HEAVY_REASONING = ModelProfile(
    HEAVY_MODEL,
    _COMBO_FALLBACK,
    reasoning_effort="high",
)
_SAHAM = ModelProfile(SAHAM_MODEL, (HEAVY_MODEL, COMBO_MODEL_NAME) if USE_9ROUTER else (DAILY_MODEL,))
_KODOK = ModelProfile(KODOK_MODEL, (HEAVY_MODEL, COMBO_MODEL_NAME) if USE_9ROUTER else (DAILY_MODEL,))
_ARSIP = ModelProfile(ARSIP_MODEL, _COMBO_FALLBACK)
_LIFESTYLE = ModelProfile(LIFESTYLE_MODEL, (DAILY_MODEL, COMBO_MODEL_NAME) if USE_9ROUTER else (DAILY_MODEL,))


TEAM_MODEL_PROFILES: Final[dict[str, dict[str, ModelProfile]]] = {
    "manager": {"standard": _DAILY},
    "visual": {"standard": _VISUAL},
    "arsip": {"standard": _ARSIP, "heavy": _HEAVY},
    "admin": {
        "standard": _ADMIN,
        "heavy": ModelProfile(
            ADMIN_HEAVY_MODEL,
            _COMBO_FALLBACK,
            reasoning_effort="high",
        ),
    },
    "intel": {"standard": _INTEL},
    "lifestyle": {"standard": _LIFESTYLE},
    "seniman": {"standard": _VISUAL},
    "mekanik": {"standard": _KODOK, "heavy": _HEAVY_REASONING},
    "saham": {"standard": _SAHAM},
    "kodok": {"standard": _KODOK, "heavy": _HEAVY_REASONING},
    "observer": {"standard": _VISUAL},
    "canvas": {"standard": _VISUAL},
    "qc_consolidator": {"standard": _DAILY},
    "tts_opener": {"standard": _DAILY},
    "prompt_optimizer": {"standard": _HEAVY},
    "security": {"standard": ModelProfile(SECURITY_MODEL, _COMBO_FALLBACK)},
}


_HEAVY_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "arsip": re.compile(
        r"\b(sintesis|lintas\s+(?:dokumen|sumber)|seluruh\s+(?:vault|arsip|koleksi)|"
        r"semua\s+dokumen|bandingkan\s+banyak\s+dokumen)\b",
        re.IGNORECASE,
    ),
    "admin": re.compile(
        r"\b(copywriting|caption|headline|tagline|landing\s+page|broadcast|kampanye|"
        r"iklan|promosi|proposal|kontrak|skripsi|tesis|jurnal|akademik)\b",
        re.IGNORECASE,
    ),
    "mekanik": re.compile(
        r"\b(repo[-\s]?wide|multi[-\s]?file|seluruh\s+repo|banyak\s+file|arsitektur|"
        r"keamanan|security|refactor\s+besar|debug\w*\s+(?:ulang|berulang|lagi))\b",
        re.IGNORECASE,
    ),
    "kodok": re.compile(
        r"\b(repo[-\s]?wide|multi[-\s]?file|seluruh\s+repo|banyak\s+file|arsitektur|"
        r"dependency\s+graph|peta\s+dependency|analisis\s+repo)\b",
        re.IGNORECASE,
    ),
}


def model_profile(team: str, profile: str = "standard") -> ModelProfile:
    """Return a configured profile or fail loudly on an unknown mapping."""
    try:
        return TEAM_MODEL_PROFILES[team][profile]
    except KeyError as exc:
        raise ValueError(f"Unknown model profile: team={team!r} profile={profile!r}") from exc


def classify_profile(team: str, user_text: str) -> str:
    """Classify locally without an extra LLM call or logging prompt content."""
    pattern = _HEAVY_PATTERNS.get(team)
    if pattern and pattern.search(user_text or ""):
        return "heavy"
    return "standard"


def select_profile(team: str, user_text: str) -> str:
    """Apply the runtime kill switch before using the local classifier."""
    enabled = os.environ.get("ENABLE_MODEL_ROUTER", "true").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return "standard"
    return classify_profile(team, user_text)


def crewai_model_id(model: str) -> str:
    clean_model = model.removeprefix("openai/")
    return f"openai/{clean_model}"


def openrouter_extra_body(
    team: str,
    profile: str = "standard",
    *,
    primary_model: str | None = None,
) -> dict[str, list[str]]:
    """Di 9Router, routing dan fallback ditangani langsung oleh 9Router."""
    return {}


def clone_agent_with_llm(agent: Any, llm: Any) -> Any:
    """Copy a canonical agent so concurrent requests never mutate its LLM/tools."""
    return agent.model_copy(
        update={"llm": llm, "tools": list(agent.tools)},
        deep=False,
    )


def get_router_credentials() -> tuple[str, str]:
    """Return (api_key, base_url) untuk 9Router."""
    api_key = (
        os.environ.get("NINEROUTER_API_KEY")
        or os.environ.get("ROUTER_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
        or ""
    ).strip()

    base_url = (
        os.environ.get("NINEROUTER_BASE_URL")
        or os.environ.get("ROUTER_BASE_URL")
        or os.environ.get("OPENROUTER_BASE_URL")
        or "http://127.0.0.1:20128/v1"
    ).strip()

    return api_key, base_url

