from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

import core.langgraph_nodes.context_summarizer as context_summarizer
import core.langgraph_nodes.manager as manager


def test_lightweight_chat_classifier_only_accepts_safe_small_talk() -> None:
    classify = getattr(manager, "_is_lightweight_chat", None)

    assert callable(classify), "manager belum punya classifier chat ringan"
    assert classify("tes") is True
    assert classify("tes lagi") is True
    assert classify("ping") is True
    assert classify("oke") is True
    assert classify("cek RAM Anisa sekarang") is False
    assert classify("buat PDF") is False


class _FakeStreamingLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[list[object]] = []

    async def astream(self, messages: list[object]):
        self.calls.append(messages)
        yield SimpleNamespace(content=self.response)


@pytest.mark.asyncio
async def test_lightweight_chat_skips_memory_and_uses_compact_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recall = AsyncMock(return_value="riwayat lama yang tidak diperlukan")
    llm = _FakeStreamingLLM("[ROUTE: santai]\nAman, Bim. Tesnya masuk.")

    monkeypatch.setattr(manager.agentmemory_client, "recall", recall)
    monkeypatch.setattr(
        manager,
        "get_recent_context",
        lambda *_args: pytest.fail("chat ringan tidak boleh membaca histori"),
    )
    monkeypatch.setattr(manager, "default_llm", llm)

    result = await manager.manager_node(
        {
            "messages": [],
            "user_request": "tes",
            "realtime_context": "konteks waktu panjang",
            "attachment_paths": [],
            "current_plan": "",
            "active_teams": [],
            "temp_data": {},
            "is_finished": False,
            "source_channel": "whatsapp",
        }
    )

    recall.assert_not_awaited()
    assert result["is_finished"] is True
    assert result["messages"][0].content == "Aman, Bim. Tesnya masuk."
    prompt = llm.calls[0][0].content
    assert len(prompt) < 2_000
    assert "maksimal 1 kalimat pendek" in prompt
    assert "Jangan ceritakan ulang histori" in prompt
    assert "kata ulang" in prompt
    assert "INGATAN AGENTMEMORY" not in prompt
    assert "Jangan balas tes atau ping dengan pertanyaan" in prompt
    assert "Aman, Bim. Tesnya masuk." in prompt


@pytest.mark.asyncio
async def test_normal_manager_prompt_keeps_compact_natural_slang_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = _FakeStreamingLLM("[ROUTE: santai]\nGua cek dulu bagian yang bikin lambat.")

    monkeypatch.setattr(
        manager.agentmemory_client,
        "recall",
        AsyncMock(return_value=""),
    )
    monkeypatch.setattr(manager, "get_recent_context", lambda *_args: "")
    monkeypatch.setattr(manager, "default_llm", llm)

    await manager.manager_node(
        {
            "messages": [],
            "user_request": "kenapa Anisa agak lambat sekarang?",
            "realtime_context": "",
            "attachment_paths": [],
            "current_plan": "",
            "active_teams": [],
            "temp_data": {},
            "is_finished": False,
            "source_channel": "whatsapp",
        }
    )

    prompt = llm.calls[0][0].content
    assert "Chat biasa cukup 1 sampai 3 kalimat pendek" in prompt
    assert "Pakai gua untuk diri sendiri" in prompt
    assert "Jangan kasih penutup generik" in prompt
    assert "code, command, URL, path, nama file, dan angka negatif" in prompt


@pytest.mark.asyncio
async def test_lightweight_empty_model_response_uses_compact_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = _FakeStreamingLLM("[ROUTE: santai]")
    monkeypatch.setattr(manager, "default_llm", llm)
    monkeypatch.setattr(
        manager.agentmemory_client,
        "recall",
        AsyncMock(side_effect=AssertionError("memory tidak boleh dipanggil")),
    )

    result = await manager.manager_node(
        {
            "messages": [],
            "user_request": "ping",
            "realtime_context": "",
            "attachment_paths": [],
            "current_plan": "",
            "active_teams": [],
            "temp_data": {},
            "is_finished": False,
            "source_channel": "whatsapp",
        }
    )

    assert result["messages"][0].content == "Gua nangkep, Bim."


def test_lightweight_chat_skips_context_summarizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_SUMMARIZATION", "true")
    monkeypatch.setenv("SUMMARIZE_THRESHOLD", "2")
    state = {
        "messages": [AIMessage(content="lama")] * 5,
        "user_request": "tes",
    }

    assert context_summarizer.should_summarize(state) == "classifier_node"
