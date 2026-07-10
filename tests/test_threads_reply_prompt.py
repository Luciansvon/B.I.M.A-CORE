from unittest import mock

import pytest

import core.threads_commands as tc


def test_threads_reply_prompt_contains_context_and_style_rules():
    prompt = tc._build_threads_reply_prompt(
        reply_username="user123",
        reply_text="wkwk relate bgt",
        post_text="laptop gua kipasnya udah kayak nyerah",
        viral_context="\n=== POLA VIRAL ===\npendek, punchy\n",
    )

    assert "@user123" in prompt
    assert "wkwk relate bgt" in prompt
    assert "laptop gua kipasnya udah kayak nyerah" in prompt
    assert "Balasan Buruk" in prompt
    assert "Balasan Baik" in prompt
    assert "Length matching" in prompt
    assert "No fluff" in prompt
    assert "Wah, menarik sekali" in prompt
    assert "Tentu" in prompt
    assert "lu" in prompt and "gua" in prompt


def test_threads_reply_prompt_short_comment_demands_short_reply():
    prompt = tc._build_threads_reply_prompt(
        reply_username="shortuser",
        reply_text="anjir wkwk",
        post_text="kopi dingin lebih jujur dari todo list gua",
    )

    assert "Komentar pendek" in prompt
    assert "maks 8 kata" in prompt
    assert "jangan jawab kayak customer service" in prompt
    assert "jangan bikin ceramah" in prompt


@pytest.mark.asyncio
async def test_generate_threads_reply_draft_enforces_180_char_limit(monkeypatch):
    captured_prompts = []

    async def fake_generate_bima_draft(prompt):
        captured_prompts.append(prompt)
        return "ini balasan panjang " * 20

    monkeypatch.setattr(tc, "generate_bima_draft", fake_generate_bima_draft)

    result = await tc.generate_threads_reply_draft("prompt balasan")

    assert captured_prompts == ["prompt balasan"]
    assert len(result) <= 180
    assert result == result.strip()


@pytest.mark.asyncio
async def test_reply_to_comment_flow_sends_human_like_prompt_to_generator(monkeypatch):
    captured_prompts = []

    async def fake_generate_bima_draft(prompt):
        captured_prompts.append(prompt)
        return "wkwk asli"

    monkeypatch.setattr(tc, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(tc, "evaluate_auto_reply", mock.AsyncMock(return_value=(False, "")))
    monkeypatch.setattr(tc, "generate_bima_draft", fake_generate_bima_draft)
    monkeypatch.setattr(tc, "_save_replied_comment", lambda rid: None)
    monkeypatch.setattr(tc, "request_permission", mock.AsyncMock(return_value=False))
    monkeypatch.setattr("core.agentmemory_client.recall", mock.AsyncMock(return_value=None), raising=False)

    result = await tc.reply_to_comment_flow(
        reply_id="comment_prompt_1",
        reply_text="anjir wkwk",
        reply_username="tester",
        post_text="file final_final_v9 lebih jujur dari hidup gua",
        user_id="42",
        client=None,
    )

    assert "dibatalkan" in result.lower()
    assert captured_prompts
    prompt = captured_prompts[0]
    assert "Length matching" in prompt
    assert "No fluff" in prompt
    assert "Balasan Buruk" in prompt
    assert "Komentar Dia: \"anjir wkwk\"" in prompt
