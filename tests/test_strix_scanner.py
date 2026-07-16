import importlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


def _module():
    assert importlib.util.find_spec("tools.strix_scanner") is not None
    return importlib.import_module("tools.strix_scanner")


def _git_repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_strix_is_opt_in(monkeypatch):
    module = _module()
    monkeypatch.setenv("STRIX_ENABLED", "false")

    assert module.StrixScannerTool()._run("{}").startswith("FAILED|Strix dinonaktifkan")


def test_preflight_reports_missing_uvx_or_docker(monkeypatch):
    module = _module()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="uvx"):
        module._preflight()

    monkeypatch.setattr(
        module.shutil, "which", lambda name: "/usr/bin/uvx" if name == "uvx" else None
    )
    with pytest.raises(RuntimeError, match="Docker CLI"):
        module._preflight()


def test_preflight_reports_stopped_docker_daemon(monkeypatch):
    module = _module()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(module.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, stdout="", stderr="daemon unavailable"
        ),
    )

    with pytest.raises(RuntimeError, match="daemon"):
        module._preflight()


def test_snapshot_includes_source_and_excludes_secrets_and_runtime_data(tmp_path):
    module = _module()
    repo = _git_repo(tmp_path / "repo")
    files = {
        "main.py": "print('safe')\n",
        "teams/good.py": "VALUE = 1\n",
        "teams/api_token.txt": "secret\n",
        ".env": "OPENROUTER_API_KEY=secret\n",
        "outputs/result.json": "{}\n",
        "Bima_Vault/private.md": "secret\n",
        "bima_env/bin/tool.py": "pass\n",
        "docs/prompt.md": "ignore\n",
    }
    for relative, content in files.items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    symlink = repo / "teams" / "linked.py"
    symlink.symlink_to(repo / ".env")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)

    snapshot = tmp_path / "snapshot"
    copied = module._create_snapshot(repo, snapshot)

    assert copied == ["main.py", "teams/good.py"]
    assert (snapshot / "main.py").exists()
    assert (snapshot / "teams" / "good.py").exists()
    assert not (snapshot / ".env").exists()
    assert not (snapshot / "teams" / "api_token.txt").exists()
    assert not (snapshot / "teams" / "linked.py").exists()
    assert not (snapshot / "outputs").exists()
    assert not (snapshot / "Bima_Vault").exists()


def test_command_is_pinned_and_uses_full_local_scope():
    module = _module()
    snapshot = Path("/tmp/snapshot")

    command = module._build_command("/usr/bin/uvx", snapshot, 0.5)

    assert command == [
        "/usr/bin/uvx",
        "--from",
        "strix-agent==1.1.0",
        "strix",
        "-n",
        "-t",
        str(snapshot),
        "--scan-mode",
        "quick",
        "--scope-mode",
        "full",
        "--max-budget-usd",
        "0.5",
    ]


def test_findings_exit_sanitizes_key_and_removes_temporary_home(
    tmp_path, monkeypatch
):
    module = _module()
    repo = _git_repo(tmp_path / "repo")
    (repo / "main.py").write_text("print('safe')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "main.py"], check=True)
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    key = "sk-sensitive-value"
    captured = {}

    monkeypatch.setattr(module, "BASE_DIR", repo)
    monkeypatch.setattr(module, "OUTPUT_DIR", outputs)
    monkeypatch.setenv("STRIX_ENABLED", "true")
    monkeypatch.setenv("OPENROUTER_API_KEY", key)
    monkeypatch.setenv("STRIX_LLM", "openrouter/openai/gpt-5.4")
    monkeypatch.setenv("STRIX_MAX_BUDGET_USD", "0.5")
    monkeypatch.setattr(module, "_preflight", lambda: ("/usr/bin/uvx", "/usr/bin/docker"))

    def fake_execute(command, env, cwd, timeout):
        captured.update(command=command, env=env, cwd=cwd, timeout=timeout)
        return subprocess.CompletedProcess(
            command, 2, stdout=f"finding created with {key}", stderr=""
        )

    monkeypatch.setattr(module, "_execute_scan", fake_execute)

    result = module.StrixScannerTool()._run(json.dumps({"mode": "quick"}))

    assert result.startswith("FINDINGS|")
    assert key not in result
    assert "[REDACTED]" in result
    assert captured["env"]["STRIX_TELEMETRY"] == "false"
    assert captured["env"]["STRIX_IMAGE"] == "ghcr.io/usestrix/strix-sandbox:1.0.0"
    assert captured["env"]["LLM_API_KEY"] == key
    assert captured["cwd"] == outputs / "security"
    assert not Path(captured["env"]["HOME"]).exists()
    assert not any(".env" in argument for argument in captured["command"])


def test_strix_rejects_non_quick_mode(monkeypatch):
    module = _module()
    monkeypatch.setenv("STRIX_ENABLED", "true")

    result = module.StrixScannerTool()._run(json.dumps({"mode": "deep"}))

    assert result.startswith("FAILED|")
