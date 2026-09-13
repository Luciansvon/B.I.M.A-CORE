from datetime import datetime, timezone
import time
from types import SimpleNamespace

from teams import t5_intel


def _disable_search_cache(monkeypatch) -> None:
    monkeypatch.setattr(t5_intel, "get_search_cache", lambda _query: None)
    monkeypatch.setattr(t5_intel, "set_search_cache", lambda _query, _result: None)
    monkeypatch.setattr(t5_intel, "TAVILY_API_KEY", "")


def _replace_search_tools(monkeypatch, tool) -> None:
    monkeypatch.setattr(t5_intel, "search_tool", tool)
    monkeypatch.setattr(t5_intel, "news_search_tool", tool)


def test_smart_search_removes_llm_wrapping_quotes(monkeypatch) -> None:
    _disable_search_cache(monkeypatch)
    serper_queries: list[str] = []
    _replace_search_tools(
        monkeypatch,
        SimpleNamespace(
            run=lambda *, search_query, **_kwargs: (
                serper_queries.append(search_query)
                or {
                    "news": [
                        {
                            "title": "Berita ditemukan",
                            "link": "https://example.com/berita",
                            "date": "1 jam yang lalu",
                        }
                    ]
                }
            )
        ),
    )

    result = t5_intel.SmartSearchTool()._run(
        '"berita indonesia 20 juli 2026"'
    )

    assert serper_queries == ["berita indonesia 20 juli 2026"]
    assert "Berita ditemukan" in result


def test_smart_search_uses_tavily_when_serper_results_are_empty(
    monkeypatch,
) -> None:
    _disable_search_cache(monkeypatch)
    _replace_search_tools(
        monkeypatch,
        SimpleNamespace(
            run=lambda **_kwargs: (
                "{'searchParameters': {'q': 'berita indonesia'}, "
                "'organic': [], 'credits': 1}"
            )
        ),
    )
    monkeypatch.setattr(t5_intel, "TAVILY_API_KEY", "dummy-key")
    tavily_queries: list[str] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> dict:
            return {
                "results": [
                        {
                            "title": "Berita dari Tavily",
                            "content": "Ringkasan berita Indonesia terbaru.",
                        "url": "https://example.com/tavily",
                        "published_date": "1 jam yang lalu",
                    }
                ]
            }

    def fake_post(_url: str, *, json: dict, timeout: int) -> FakeResponse:
        tavily_queries.append(json["query"])
        return FakeResponse()

    monkeypatch.setattr(t5_intel.httpx, "post", fake_post)

    result = t5_intel.SmartSearchTool()._run("berita indonesia")

    assert tavily_queries == ["berita indonesia"]
    assert "Berita dari Tavily" in result


def test_news_query_uses_serper_news_mode(monkeypatch) -> None:
    _disable_search_cache(monkeypatch)
    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return {
            "news": [
                {
                    "title": "Berita Indonesia terbaru",
                    "link": "https://example.com/terbaru",
                    "date": "2 jam yang lalu",
                }
            ]
        }

    _replace_search_tools(
        monkeypatch,
        SimpleNamespace(run=fake_run),
    )

    t5_intel.SmartSearchTool()._run("berita Indonesia hari ini")

    assert calls == [
        {
            "search_query": "berita Indonesia hari ini",
            "search_type": "news",
        }
    ]


def test_news_query_drops_results_older_than_24_hours(monkeypatch) -> None:
    _disable_search_cache(monkeypatch)
    _replace_search_tools(
        monkeypatch,
        SimpleNamespace(
            run=lambda **_kwargs: {
                "news": [
                    {
                        "title": "Berita segar",
                        "link": "https://example.com/segar",
                        "date": "8 jam yang lalu",
                    },
                    {
                        "title": "Berita basi",
                        "link": "https://example.com/basi",
                        "date": "2 hari yang lalu",
                    },
                ]
            }
        ),
    )

    result = t5_intel.SmartSearchTool()._run("berita Indonesia terbaru")

    assert "Berita segar" in result
    assert "Berita basi" not in result


def test_news_query_drops_preview_when_matching_result_exists(
    monkeypatch,
) -> None:
    _disable_search_cache(monkeypatch)
    _replace_search_tools(
        monkeypatch,
        SimpleNamespace(
            run=lambda **_kwargs: {
                "news": [
                    {
                        "title": (
                            "LIVE Jadwal Final Piala Dunia 2026, "
                            "Spanyol Vs Argentina"
                        ),
                        "link": "https://example.com/jadwal",
                        "date": "12 jam yang lalu",
                    },
                    {
                        "title": (
                            "Hasil Spanyol vs Argentina: "
                            "Spanyol Juara Piala Dunia 2026"
                        ),
                        "link": "https://example.com/hasil",
                        "date": "8 jam yang lalu",
                    },
                ]
            }
        ),
    )

    result = t5_intel.SmartSearchTool()._run("berita Indonesia hari ini")

    assert "Spanyol Juara" in result
    assert "LIVE Jadwal" not in result


def test_news_query_crosschecks_with_tavily_day_filter(monkeypatch) -> None:
    _disable_search_cache(monkeypatch)
    monkeypatch.setattr(t5_intel, "TAVILY_API_KEY", "dummy-key")
    _replace_search_tools(
        monkeypatch,
        SimpleNamespace(
            run=lambda **_kwargs: {
                "news": [
                    {
                        "title": "Berita Serper",
                        "link": "https://example.com/serper",
                        "date": "1 jam yang lalu",
                    }
                ]
            }
        ),
    )
    tavily_payloads: list[dict] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> dict:
            published = datetime.now(timezone.utc).isoformat()
            return {
                "results": [
                    {
                        "title": "Berita Tavily",
                        "content": "Hasil pembanding terbaru dari Indonesia.",
                        "url": "https://example.com/tavily",
                        "published_date": published,
                    },
                    {
                        "title": "Berita luar negeri tidak relevan",
                        "content": "Tidak membahas negara yang dicari.",
                        "url": "https://example.com/tidak-relevan",
                        "published_date": published,
                    },
                ]
            }

    def fake_post(_url: str, *, json: dict, timeout: int) -> FakeResponse:
        tavily_payloads.append(json)
        return FakeResponse()

    monkeypatch.setattr(t5_intel.httpx, "post", fake_post)

    result = t5_intel.SmartSearchTool()._run("berita Indonesia hari ini")

    assert tavily_payloads[0]["topic"] == "news"
    assert tavily_payloads[0]["time_range"] == "day"
    assert tavily_payloads[0]["country"] == "indonesia"
    assert "Berita Serper" in result
    assert "Berita Tavily" in result
    assert "Berita luar negeri tidak relevan" not in result


def test_news_query_does_not_reuse_legacy_general_search_cache(
    monkeypatch,
) -> None:
    cache_keys: list[str] = []

    def fake_get_cache(key: str):
        cache_keys.append(key)
        if key == "berita indonesia hari ini":
            return (
                time.time(),
                "{'organic': [{'title': 'Respons cache lama'}]}",
            )
        return None

    monkeypatch.setattr(t5_intel, "get_search_cache", fake_get_cache)
    monkeypatch.setattr(t5_intel, "set_search_cache", lambda *_args: None)
    monkeypatch.setattr(t5_intel, "TAVILY_API_KEY", "")
    _replace_search_tools(
        monkeypatch,
        SimpleNamespace(
            run=lambda **_kwargs: {
                "news": [
                    {
                        "title": "Respons berita baru",
                        "link": "https://example.com/baru",
                        "date": "1 jam yang lalu",
                    }
                ]
            }
        ),
    )

    result = t5_intel.SmartSearchTool()._run("berita Indonesia hari ini")

    assert cache_keys == ["news:v2:berita indonesia hari ini"]
    assert "Respons berita baru" in result
    assert "Respons cache lama" not in result


def test_news_and_general_search_use_separate_serper_tools(
    monkeypatch,
) -> None:
    _disable_search_cache(monkeypatch)
    general_calls: list[dict] = []
    news_calls: list[dict] = []
    monkeypatch.setattr(
        t5_intel,
        "search_tool",
        SimpleNamespace(
            run=lambda **kwargs: (
                general_calls.append(kwargs)
                or {
                    "organic": [
                        {
                            "title": "Hasil umum",
                            "link": "https://example.com/umum",
                        }
                    ]
                }
            )
        ),
    )
    monkeypatch.setattr(
        t5_intel,
        "news_search_tool",
        SimpleNamespace(
            run=lambda **kwargs: (
                news_calls.append(kwargs)
                or {
                    "news": [
                        {
                            "title": "Hasil berita",
                            "link": "https://example.com/berita",
                            "date": "1 jam yang lalu",
                        }
                    ]
                }
            )
        ),
        raising=False,
    )

    news_result = t5_intel.SmartSearchTool()._run(
        "berita Indonesia hari ini"
    )
    general_result = t5_intel.SmartSearchTool()._run(
        "dokumentasi Python asyncio"
    )

    assert news_calls == [
        {
            "search_query": "berita Indonesia hari ini",
            "search_type": "news",
        }
    ]
    assert general_calls == [
        {"search_query": "dokumentasi Python asyncio"}
    ]
    assert "Hasil berita" in news_result
    assert "Hasil umum" in general_result
