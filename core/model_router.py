"""Model profiles and local request classification for BIMA_CORE agents."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Final


DAILY_MODEL: Final = "deepseek/deepseek-v4-flash-0731"
HEAVY_MODEL: Final = "deepseek/deepseek-v4-pro-0813"
VISUAL_MODEL: Final = "google/gemini-3.7-flash"
VISUAL_FALLBACK_MODEL: Final = "google/gemini-3.1-flash-lite"
INTEL_MODEL: Final = "qwen/qwen3.8-27b"
ADMIN_HEAVY_MODEL: Final = "anthropic/claude-sonnet-5"
THREADS_MODEL: Final = ADMIN_HEAVY_MODEL
IMAGE_MODEL: Final = "google/gemini-3.1-flash-image"
SECURITY_MODEL: Final = "openai/gpt-5.6-luna-pro"
MODEL_INPUT_COST_PER_M: Final[dict[str, float]] = {
    DAILY_MODEL: 0.035,
    HEAVY_MODEL: 0.66,
}


@dataclass(frozen=True, slots=True)
class ModelProfile:
    model: str
    fallbacks: tuple[str, ...] = ()
    reasoning_effort: str | None = None


_DAILY = ModelProfile(DAILY_MODEL)
_VISUAL = ModelProfile(VISUAL_MODEL, (VISUAL_FALLBACK_MODEL,))
_INTEL = ModelProfile(INTEL_MODEL, (DAILY_MODEL,))
_HEAVY = ModelProfile(HEAVY_MODEL, (DAILY_MODEL,))
_HEAVY_REASONING = ModelProfile(
    HEAVY_MODEL,
    (DAILY_MODEL,),
    reasoning_effort="high",
)


TEAM_MODEL_PROFILES: Final[dict[str, dict[str, ModelProfile]]] = {
    "manager": {"standard": _DAILY},
    "visual": {"standard": _VISUAL},
    "arsip": {"standard": _DAILY, "heavy": _INTEL},
    "admin": {
        "standard": _DAILY,
        "heavy": ModelProfile(
            ADMIN_HEAVY_MODEL,
            (DAILY_MODEL,),
            reasoning_effort="high",
        ),
    },
    "intel": {"standard": _INTEL},
    "lifestyle": {"standard": _DAILY},
    "seniman": {"standard": _VISUAL},
    "mekanik": {"standard": _HEAVY, "heavy": _HEAVY_REASONING},
    "saham": {"standard": _HEAVY},
    "kodok": {"standard": _HEAVY, "heavy": _HEAVY_REASONING},
    "observer": {"standard": _VISUAL},
    "canvas": {"standard": _VISUAL},
    "qc_consolidator": {"standard": _DAILY},
    "tts_opener": {"standard": _DAILY},
    "prompt_optimizer": {"standard": _HEAVY},
    "security": {"standard": ModelProfile(SECURITY_MODEL)},
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
    return model if model.startswith("openrouter/") else f"openrouter/{model}"


def openrouter_extra_body(
    team: str,
    profile: str = "standard",
    *,
    primary_model: str | None = None,
) -> dict[str, list[str]]:
    """Build OpenRouter fallback payload for direct OpenAI-compatible callers."""
    selected = model_profile(team, profile)
    if not selected.fallbacks:
        return {}
    return {"models": [primary_model or selected.model, *selected.fallbacks]}


def clone_agent_with_llm(agent: Any, llm: Any) -> Any:
    """Copy a canonical agent so concurrent requests never mutate its LLM/tools."""
    return agent.model_copy(
        update={"llm": llm, "tools": list(agent.tools)},
        deep=False,
    )
