import sys
from contextlib import contextmanager
from types import ModuleType

import pytest

from services.browser import worker


class FakeHistory:
    def __init__(self, *, done: bool, successful: bool | None, result: str) -> None:
        self._done = done
        self._successful = successful
        self._result = result

    def final_result(self) -> str:
        return self._result

    def is_done(self) -> bool:
        return self._done

    def is_successful(self) -> bool | None:
        return self._successful


def _install_fake_browser_use(
    monkeypatch: pytest.MonkeyPatch,
    history: FakeHistory,
    events: list[str] | None = None,
) -> None:
    browser_use = ModuleType("browser_use")
    llm_module = ModuleType("browser_use.llm")
    openai_module = ModuleType("browser_use.llm.openai")
    chat_module = ModuleType("browser_use.llm.openai.chat")

    class FakeBrowserProfile:
        def __init__(self, **kwargs: object) -> None:
            if events is not None:
                events.append("profile")

    class FakeAgent:
        def __init__(self, **kwargs: object) -> None:
            if events is not None:
                events.append("agent")

        async def run(self, max_steps: int) -> FakeHistory:
            if events is not None:
                events.append("run")
            return history

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            pass

    browser_use.Agent = FakeAgent
    browser_use.BrowserProfile = FakeBrowserProfile
    chat_module.ChatOpenAI = FakeChatOpenAI
    monkeypatch.setitem(sys.modules, "browser_use", browser_use)
    monkeypatch.setitem(sys.modules, "browser_use.llm", llm_module)
    monkeypatch.setitem(sys.modules, "browser_use.llm.openai", openai_module)
    monkeypatch.setitem(sys.modules, "browser_use.llm.openai.chat", chat_module)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("BROWSER_USE_RECORD", raising=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("done", "successful"),
    [(False, None), (True, False), (True, None)],
)
async def test_non_successful_history_is_not_reported_as_success(
    monkeypatch: pytest.MonkeyPatch,
    done: bool,
    successful: bool | None,
) -> None:
    _install_fake_browser_use(
        monkeypatch,
        FakeHistory(done=done, successful=successful, result="partial output"),
    )

    result = await worker.run_task("buka example.com")

    assert result == {"ok": False, "error": "browser task incomplete"}


@pytest.mark.asyncio
async def test_done_successful_history_is_reported_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_browser_use(
        monkeypatch,
        FakeHistory(done=True, successful=True, result="task complete"),
    )

    result = await worker.run_task("buka example.com")

    assert result["ok"] is True
    assert result["result"] == "task complete"


@pytest.mark.asyncio
async def test_marketplace_profile_lifecycle_is_inside_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    _install_fake_browser_use(
        monkeypatch,
        FakeHistory(done=True, successful=True, result="task complete"),
        events,
    )

    @contextmanager
    def fake_lock():
        events.append("enter")
        try:
            yield
        finally:
            events.append("exit")

    monkeypatch.setattr(worker, "_marketplace_profile_lock", fake_lock, raising=False)

    result = await worker.run_task("cek harga kursi di shopee")

    assert result["ok"] is True
    assert events == ["enter", "profile", "agent", "run", "exit"]
