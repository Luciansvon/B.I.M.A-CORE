import json
import subprocess
from pathlib import Path

from tools import browser_use_tool


def test_browser_tool_uses_isolated_worker(monkeypatch, tmp_path: Path) -> None:
    worker_python = tmp_path / "browser-python"
    worker_python.touch()
    captured: dict = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"ok": True, "result": "isolated result"}),
            stderr="",
        )

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(browser_use_tool, "_browser_worker_python", lambda: worker_python)
    monkeypatch.setattr(browser_use_tool.subprocess, "run", fake_run)

    result = browser_use_tool.BrowserUseTool()._run("Open example.com")

    assert captured["command"][0] == str(worker_python)
    assert captured["command"][1].endswith("services/browser/worker.py")
    assert json.loads(captured["kwargs"]["input"])["task"] == "Open example.com"
    assert result == "SUCCESS|browser_use|isolated result"


def test_browser_worker_manifest_does_not_include_crewai() -> None:
    project_root = Path(__file__).resolve().parent.parent
    manifest = (
        project_root / "services" / "browser" / "pyproject.toml"
    ).read_text(encoding="utf-8")

    assert "crewai" not in manifest.lower()
