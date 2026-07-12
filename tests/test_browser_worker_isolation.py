import json
import signal
import subprocess
from pathlib import Path

from tools import browser_use_tool


class FakeWorker:
    pid = 4321
    returncode = 0

    def __init__(self, *, timeout: bool = False, survives_term: bool = False) -> None:
        self.timeout = timeout
        self.survives_term = survives_term
        self.communicate_calls: list[tuple[str, int]] = []
        self.wait_calls: list[int] = []

    def communicate(self, payload: str, timeout: int) -> tuple[str, str]:
        self.communicate_calls.append((payload, timeout))
        if self.timeout:
            raise subprocess.TimeoutExpired("browser-worker", timeout)
        return json.dumps({"ok": True, "result": "isolated result"}), ""

    def wait(self, timeout: int) -> int:
        self.wait_calls.append(timeout)
        if self.survives_term and len(self.wait_calls) == 1:
            raise subprocess.TimeoutExpired("browser-worker", timeout)
        return 0


def _prepare_worker(monkeypatch, tmp_path: Path) -> Path:
    worker_python = tmp_path / "browser-python"
    worker_python.touch()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(browser_use_tool, "_browser_worker_python", lambda: worker_python)
    return worker_python


def test_browser_worker_default_timeout_is_21_minutes(monkeypatch) -> None:
    monkeypatch.delenv("BROWSER_WORKER_TIMEOUT", raising=False)
    assert browser_use_tool._worker_timeout() == 1260


def test_browser_tool_uses_isolated_process_group(
    monkeypatch,
    tmp_path: Path,
) -> None:
    worker_python = _prepare_worker(monkeypatch, tmp_path)
    captured: dict = {}
    worker = FakeWorker()

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return worker

    monkeypatch.setattr(browser_use_tool.subprocess, "Popen", fake_popen)

    result = browser_use_tool.BrowserUseTool()._run("Open example.com")

    assert captured["command"][0] == str(worker_python)
    assert captured["command"][1].endswith("services/browser/worker.py")
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["kwargs"]["stdin"] is subprocess.PIPE
    assert json.loads(worker.communicate_calls[0][0])["task"] == "Open example.com"
    assert result == "SUCCESS|browser_use|isolated result"


def test_timeout_terminates_worker_process_group(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _prepare_worker(monkeypatch, tmp_path)
    worker = FakeWorker(timeout=True)
    signals: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(browser_use_tool.subprocess, "Popen", lambda *a, **k: worker)
    monkeypatch.setattr(
        browser_use_tool.os,
        "killpg",
        lambda pid, sig: signals.append((pid, sig)),
    )

    result = browser_use_tool.BrowserUseTool()._run("Open example.com")

    assert result == "FAILED|browser worker timeout >1260s"
    assert signals == [(worker.pid, signal.SIGTERM)]


def test_timeout_escalates_stuck_group_to_sigkill(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _prepare_worker(monkeypatch, tmp_path)
    worker = FakeWorker(timeout=True, survives_term=True)
    signals: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(browser_use_tool.subprocess, "Popen", lambda *a, **k: worker)
    monkeypatch.setattr(
        browser_use_tool.os,
        "killpg",
        lambda pid, sig: signals.append((pid, sig)),
    )

    browser_use_tool.BrowserUseTool()._run("Open example.com")

    assert signals == [
        (worker.pid, signal.SIGTERM),
        (worker.pid, signal.SIGKILL),
    ]


def test_browser_worker_manifest_does_not_include_crewai() -> None:
    project_root = Path(__file__).resolve().parent.parent
    manifest = (
        project_root / "services" / "browser" / "pyproject.toml"
    ).read_text(encoding="utf-8")

    assert "crewai" not in manifest.lower()
