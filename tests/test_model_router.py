from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_current_stable_model_contract() -> None:
    from core.model_router import (
        IMAGE_MODEL,
        SECURITY_MODEL,
        THREADS_MODEL,
        VISUAL_MODEL,
        VISUAL_FALLBACK_MODEL,
        model_profile,
    )

    assert model_profile("manager").model == "deepseek/deepseek-v4-flash-0731"
    assert model_profile("mekanik").model == "deepseek/deepseek-v4-pro-0813"
    assert model_profile("intel").model == "qwen/qwen3.8-27b"
    assert VISUAL_MODEL == "google/gemini-3.7-flash"
    assert VISUAL_FALLBACK_MODEL == "google/gemini-3.1-flash-lite"
    assert IMAGE_MODEL == "google/gemini-3.1-flash-image"
    assert SECURITY_MODEL == "openai/gpt-5.6-luna-pro"
    assert THREADS_MODEL == "anthropic/claude-sonnet-5"


def test_llm_config_uses_valid_callback_handler() -> None:
    from langchain_core.callbacks import BaseCallbackHandler

    from core.langgraph_nodes.llm_config import CostTracker

    assert issubclass(CostTracker, BaseCallbackHandler)


@pytest.mark.parametrize(
    ("team", "user_text", "expected"),
    [
        ("arsip", "cari catatan meja kerja", "standard"),
        ("arsip", "sintesis lintas dokumen seluruh vault", "heavy"),
        ("admin", "rapihin tabel Excel ini", "standard"),
        ("admin", "buat proposal akademik lengkap", "heavy"),
        ("mekanik", "cek error satu fungsi", "standard"),
        ("mekanik", "refactor repo-wide multi-file", "heavy"),
        ("kodok", "jelasin fungsi ini", "standard"),
        ("kodok", "analisis arsitektur seluruh repo", "heavy"),
    ],
)


def test_team_profile_classifier(team: str, user_text: str, expected: str) -> None:
    from core.model_router import classify_profile

    assert classify_profile(team, user_text) == expected


def test_model_router_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.model_router import select_profile

    monkeypatch.setenv("ENABLE_MODEL_ROUTER", "false")

    assert select_profile("mekanik", "refactor repo-wide multi-file") == "standard"


def test_agent_clone_keeps_canonical_agent_unchanged() -> None:
    from core.model_router import clone_agent_with_llm

    class FakeAgent:
        def __init__(self, llm: str, tools: list[str]) -> None:
            self.llm = llm
            self.tools = tools

        def model_copy(self, *, update: dict, deep: bool) -> "FakeAgent":
            assert deep is False
            return FakeAgent(update["llm"], update["tools"])

    canonical = FakeAgent("daily", ["search", "write"])
    request_agent = clone_agent_with_llm(canonical, "heavy")

    assert canonical.llm == "daily"
    assert canonical.tools == ["search", "write"]
    assert request_agent.llm == "heavy"
    assert request_agent.tools == canonical.tools
    assert request_agent.tools is not canonical.tools


def test_heavy_profiles_keep_stable_fallbacks() -> None:
    from core.model_router import model_profile

    arsip = model_profile("arsip", "heavy")
    admin = model_profile("admin", "heavy")
    mekanik = model_profile("mekanik", "heavy")

    assert arsip.fallbacks == ("deepseek/deepseek-v4-flash-0731",)
    assert admin.fallbacks == ("deepseek/deepseek-v4-flash-0731",)
    assert admin.reasoning_effort == "high"
    assert mekanik.reasoning_effort == "high"
    assert all(
        marker not in profile.model
        for profile in (arsip, admin, mekanik)
        for marker in ("preview", "experimental", ":beta", "/latest")
    )


def test_direct_visual_fallback_keeps_multimodal_model() -> None:
    from core.model_router import openrouter_extra_body

    assert openrouter_extra_body("visual") == {
        "models": [
            "google/gemini-3.7-flash",
            "google/gemini-3.1-flash-lite",
        ]
    }


def test_production_defaults_do_not_keep_retired_model_ids() -> None:
    retired = {
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4-pro",
        "google/gemini-3.5-flash",
        "google/gemini-3.1-flash-image-preview",
        "openai/gpt-5.4",
    }
    roots = [
        PROJECT_ROOT / "config.py",
        PROJECT_ROOT / "core",
        PROJECT_ROOT / "teams",
        PROJECT_ROOT / "tools",
        PROJECT_ROOT / "services" / "browser",
        PROJECT_ROOT / ".env.example",
    ]

    offenders: list[str] = []
    for root in roots:
        files = [root] if root.is_file() else root.rglob("*.py")
        for path in files:
            if "last30days-skill" in path.parts or ".venv" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for model_id in retired:
                literals = (
                    f'"{model_id}"',
                    f"'{model_id}'",
                    f'"openrouter/{model_id}"',
                    f"'openrouter/{model_id}'",
                )
                if any(literal in text for literal in literals):
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {model_id}")

    assert offenders == []
