import inspect
import json
from unittest import mock

import pytest

import core.threads_commands as tc
import core.threads_scheduler as ts


def test_trend_cache_is_consumed_once_and_expires():
    store_trends = getattr(tc, "_store_trends", None)
    consume_trends = getattr(tc, "_consume_trends", None)
    assert store_trends is not None
    assert consume_trends is not None

    items = [{"title": "Topik baru", "snippet": "Konteks baru"}]
    store_trends("user-a", items, now=100.0)
    assert consume_trends("user-a", now=399.0) == items
    assert consume_trends("user-a", now=399.5) is None

    store_trends("user-b", items, now=100.0)
    assert consume_trends("user-b", now=401.0) is None


class _FakeResponse:
    status_code = 200

    def json(self):
        return {
            "news": [
                {
                    "title": "Berita segar",
                    "snippet": "Kejadian baru",
                    "date": "2 hours ago",
                    "link": "https://example.com/fresh",
                    "source": "Example",
                },
                {
                    "title": "Berita lama",
                    "snippet": "Kejadian lama",
                    "date": "2 days ago",
                    "link": "https://example.com/old",
                    "source": "Example",
                },
                {
                    "title": "Tanpa tanggal",
                    "snippet": "Tidak bisa diverifikasi",
                    "link": "https://example.com/undated",
                    "source": "Example",
                },
            ]
        }


class _FakeAsyncClient:
    calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, json, headers, timeout):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return _FakeResponse()


@pytest.fixture
def fake_serper(monkeypatch):
    _FakeAsyncClient.calls = []
    monkeypatch.setenv("SERPER_API_KEY", "dummy")
    monkeypatch.setattr(tc.httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient.calls


@pytest.mark.asyncio
async def test_fetch_trends_uses_news_endpoint_and_drops_old_or_undated(fake_serper):
    trends = await tc.fetch_indonesian_trends()

    assert [item["title"] for item in trends] == ["Berita segar"]
    assert fake_serper
    assert all(call["url"] == "https://google.serper.dev/news" for call in fake_serper)


@pytest.mark.asyncio
async def test_search_context_contains_only_fresh_dated_news(fake_serper):
    context = await tc.search_context("topik hari ini")

    assert "Berita segar" in context
    assert "2 hours ago" in context
    assert "Berita lama" not in context
    assert "Tanpa tanggal" not in context
    assert fake_serper[0]["url"] == "https://google.serper.dev/news"


@pytest.mark.parametrize(
    "date_text",
    [
        "yesterday",
        "kemarin",
        "1 day ago",
        "1 hari lalu",
        "24 hours ago",
        "24 jam lalu",
        "1440 minutes ago",
    ],
)
def test_ambiguous_day_relative_news_is_rejected(date_text):
    item = {"title": "Ambigu", "snippet": "Bisa lebih dari 24 jam", "date": date_text}

    assert tc._news_age_hours(date_text) is None
    assert tc._filter_fresh_news([item]) == []


@pytest.mark.asyncio
async def test_draft_flow_does_not_inject_old_viral_memory(monkeypatch):
    captured_prompts = []

    async def generate(prompt, **_kwargs):
        captured_prompts.append(prompt)
        return "draf baru"

    old_memory = mock.AsyncMock(return_value=["KONTEN VIRAL REQUEST LAMA"])
    monkeypatch.setattr(tc, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(tc, "search_context", mock.AsyncMock(return_value="KONTEKS LIVE"))
    monkeypatch.setattr(tc, "generate_bima_draft", generate)
    permission = mock.AsyncMock(return_value=(False, None))
    monkeypatch.setattr(tc, "request_permission_with_revision", permission)
    monkeypatch.setattr("core.agentmemory_client.recall", old_memory, raising=False)

    result = await tc.draft_and_post_flow("topik baru", "42")

    assert "dibatalkan" in result.lower()
    assert captured_prompts
    assert "KONTEN VIRAL REQUEST LAMA" not in captured_prompts[0]
    assert old_memory.await_count == 0
    assert permission.await_args.kwargs["revision_base"] == "draf baru"


@pytest.mark.asyncio
async def test_fact_generator_uses_old_database_only_as_topic_denylist(tmp_path, monkeypatch):
    signature = inspect.signature(ts.generate_random_interesting_fact_topic)
    assert "facts_path" in signature.parameters

    facts_path = tmp_path / "scientific_facts.json"
    old_data = [{"topic": "TOPIK LAMA", "context": "KONTEKS LAMA RAHASIA"}]
    facts_path.write_text(json.dumps(old_data), encoding="utf-8")

    class FakeResponse:
        content = '{"topic": "TOPIK BARU", "context": "KONTEKS MODEL"}'

    class FakeLLM:
        def __init__(self):
            self.prompts = []

        def invoke(self, messages):
            self.prompts.append(messages[-1].content)
            return FakeResponse()

    fake_llm = FakeLLM()
    monkeypatch.setattr("core.langgraph_nodes.llm_config.default_llm", fake_llm)
    monkeypatch.setattr(ts, "search_context", mock.AsyncMock(return_value="KONTEKS LIVE BARU"))
    monkeypatch.setattr(ts, "_record_recent_topic", lambda _topic: None)

    topic, context = await ts.generate_random_interesting_fact_topic(str(facts_path))

    assert (topic, context) == ("TOPIK BARU", "KONTEKS LIVE BARU")
    assert "TOPIK LAMA" in fake_llm.prompts[0]
    assert "KONTEKS LAMA RAHASIA" not in fake_llm.prompts[0]
    assert json.loads(facts_path.read_text(encoding="utf-8")) == old_data


@pytest.mark.asyncio
async def test_fact_generator_retries_if_model_returns_old_topic(tmp_path, monkeypatch):
    facts_path = tmp_path / "scientific_facts.json"
    facts_path.write_text(
        json.dumps([{"topic": "TOPIK LAMA", "context": "JANGAN DIPAKAI"}]),
        encoding="utf-8",
    )

    class FakeResponse:
        def __init__(self, content):
            self.content = content

    class FakeLLM:
        def __init__(self):
            self.responses = iter(
                [
                    '{"topic": "TOPIK LAMA", "context": "MODEL LAMA"}',
                    '{"topic": "TOPIK BENAR-BENAR BARU", "context": "MODEL BARU"}',
                ]
            )
            self.calls = 0

        def invoke(self, _messages):
            self.calls += 1
            return FakeResponse(next(self.responses))

    fake_llm = FakeLLM()
    monkeypatch.setattr("core.langgraph_nodes.llm_config.default_llm", fake_llm)
    search = mock.AsyncMock(return_value="KONTEKS LIVE")
    monkeypatch.setattr(ts, "search_context", search)
    monkeypatch.setattr(ts, "_record_recent_topic", lambda _topic: None)

    assert await ts.generate_random_interesting_fact_topic(str(facts_path)) == (
        "TOPIK BENAR-BENAR BARU",
        "KONTEKS LIVE",
    )
    assert fake_llm.calls == 2
    search.assert_awaited_once_with("TOPIK BENAR-BENAR BARU")


@pytest.mark.asyncio
async def test_fact_generator_skips_if_current_search_has_no_fresh_context(tmp_path, monkeypatch):
    facts_path = tmp_path / "scientific_facts.json"
    facts_path.write_text("[]", encoding="utf-8")

    class FakeResponse:
        content = '{"topic": "MATERIAL BARU HARI INI", "context": "MODEL"}'

    class FakeLLM:
        def invoke(self, _messages):
            return FakeResponse()

    record_topic = mock.Mock()
    monkeypatch.setattr("core.langgraph_nodes.llm_config.default_llm", FakeLLM())
    monkeypatch.setattr(
        ts,
        "search_context",
        mock.AsyncMock(return_value="Tidak ada konteks baru terverifikasi dalam 24 jam terakhir."),
    )
    monkeypatch.setattr(ts, "_record_recent_topic", record_topic)

    assert await ts.generate_random_interesting_fact_topic(str(facts_path)) == ("", "")
    record_topic.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("verdict", "expected"), [("SAFE", True), ("UNSAFE", False)])
async def test_autopost_safety_verdict_must_match_exactly(monkeypatch, verdict, expected):
    class FakeResponse:
        content = verdict

    class FakeLLM:
        def invoke(self, _messages):
            return FakeResponse()

    monkeypatch.setattr("core.langgraph_nodes.llm_config.default_llm", FakeLLM())

    assert await ts.is_topic_safe_for_autopost("draf", "topik") is expected


@pytest.mark.asyncio
async def test_scheduler_does_not_inject_old_viral_memory(monkeypatch):
    captured_prompts = []

    async def generate(prompt, **_kwargs):
        captured_prompts.append(prompt)
        return "draf baru"

    random_values = iter([0.9])
    old_memory = mock.AsyncMock(return_value=["KONTEN VIRAL SCHEDULER LAMA"])
    monkeypatch.setattr(ts, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(ts.random, "random", lambda: next(random_values))
    monkeypatch.setattr(
        ts,
        "generate_random_interesting_fact_topic",
        mock.AsyncMock(return_value=("TOPIK LIVE", "KONTEKS LIVE")),
    )
    monkeypatch.setattr(ts, "generate_bima_draft", generate)
    monkeypatch.setattr(ts, "get_bot_owner_id", mock.AsyncMock(return_value="42"))
    permission = mock.AsyncMock(return_value=(False, None))
    monkeypatch.setattr(ts, "request_permission_with_revision", permission)
    monkeypatch.setattr("core.agentmemory_client.recall", old_memory, raising=False)

    await ts.auto_post_threads(object())

    assert captured_prompts
    assert "KONTEN VIRAL SCHEDULER LAMA" not in captured_prompts[0]
    assert old_memory.await_count == 0
    assert permission.await_args.kwargs["revision_base"] == "draf baru"


@pytest.mark.asyncio
async def test_scheduler_skips_when_no_fresh_topic_can_be_generated(monkeypatch):
    generate_draft = mock.AsyncMock(return_value="harusnya tidak dipanggil")
    monkeypatch.setattr(ts, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(ts.random, "random", lambda: 0.0)
    monkeypatch.setattr(
        ts,
        "generate_random_interesting_fact_topic",
        mock.AsyncMock(return_value=("", "")),
    )
    monkeypatch.setattr(ts, "generate_bima_draft", generate_draft)

    await ts.auto_post_threads(object())

    generate_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_reply_flow_does_not_inject_old_viral_memory(monkeypatch):
    captured_prompts = []

    async def generate(prompt, **_kwargs):
        captured_prompts.append(prompt)
        return "balasan baru"

    old_memory = mock.AsyncMock(return_value=["KONTEN VIRAL REPLY LAMA"])
    monkeypatch.setattr(tc, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(tc, "evaluate_auto_reply", mock.AsyncMock(return_value=(False, "")))
    monkeypatch.setattr(tc, "generate_threads_reply_draft", generate)
    monkeypatch.setattr(tc, "_save_replied_comment", lambda _reply_id: None)
    permission = mock.AsyncMock(return_value=(False, None))
    monkeypatch.setattr(tc, "request_permission_with_revision", permission)
    monkeypatch.setattr("core.agentmemory_client.recall", old_memory, raising=False)

    result = await tc.reply_to_comment_flow(
        reply_id="reply-fresh",
        reply_text="komentar sekarang",
        reply_username="user-sekarang",
        post_text="post sekarang",
        user_id="42",
    )

    assert "dibatalkan" in result.lower()
    assert captured_prompts
    assert "KONTEN VIRAL REPLY LAMA" not in captured_prompts[0]
    assert old_memory.await_count == 0
    assert permission.await_args.kwargs["revision_base"] == "balasan baru"
