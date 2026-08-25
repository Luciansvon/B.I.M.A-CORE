"""Opt-in Strix runner that scans a sanitized local source snapshot."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from crewai.tools import BaseTool

from config import BASE_DIR, OUTPUT_DIR
from core.model_router import SECURITY_MODEL, crewai_model_id

STRIX_PACKAGE = "strix-agent==1.1.0"
STRIX_IMAGE = "ghcr.io/usestrix/strix-sandbox:1.0.0"
_ROOT_DIRS = {"core", "teams", "tools", "dashboard", "frontend", "whatsapp", "scripts", "tests"}
_ROOT_FILES = {
    "main.py",
    "config.py",
    "pyproject.toml",
    "requirements.txt",
    "ecosystem.config.js",
    "package.json",
    "package-lock.json",
}
_ALLOWED_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".rs",
    ".toml",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".css",
}
_SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".rs"}
_EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "bima_env",
    "node_modules",
    "outputs",
    "bima_vault",
    "vault_index",
    "repo_index",
    "search_index",
    "logs",
    "__pycache__",
    ".codex-remote-attachments",
    "databasement",
}
_SECRET_NAMES = {
    ".env",
    ".env.local",
    ".npmrc",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.json",
}
_SECRET_MARKERS = {"secret", "credential", "api_key", "api-token", "api_token"}
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _enabled() -> bool:
    return os.getenv("STRIX_ENABLED", "false").strip().lower() == "true"


def _api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY belum tersedia untuk Strix.")
    return key


def _preflight() -> tuple[str, str]:
    uvx = shutil.which("uvx")
    if uvx is None:
        raise RuntimeError("uvx tidak ditemukan di PATH.")
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI belum terpasang di WSL.")
    _api_key()
    try:
        result = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Docker daemon tidak bisa diperiksa: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError("Docker daemon belum aktif atau tidak dapat diakses dari WSL.")
    return uvx, docker


def _is_safe_file(relative: Path) -> bool:
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        return False
    lowered_parts = {part.casefold() for part in relative.parts}
    if lowered_parts & _EXCLUDED_PARTS:
        return False
    if len(relative.parts) == 1:
        if relative.name not in _ROOT_FILES:
            return False
    elif relative.parts[0] not in _ROOT_DIRS:
        return False
    suffix = relative.suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        return False
    lowered_name = relative.name.casefold()
    if lowered_name in _SECRET_NAMES:
        return False
    if suffix not in _SOURCE_SUFFIXES and any(
        marker in lowered_name for marker in _SECRET_MARKERS
    ):
        return False
    return True


def _create_snapshot(repo: Path, snapshot: Path) -> list[str]:
    root = repo.resolve()
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        check=True,
    )
    tracked = sorted(
        entry.decode("utf-8", errors="surrogateescape")
        for entry in result.stdout.split(b"\0")
        if entry
    )
    copied: list[str] = []
    for raw_relative in tracked:
        relative = Path(raw_relative)
        if not _is_safe_file(relative):
            continue
        source = root / relative
        if source.is_symlink() or not source.is_file():
            continue
        resolved = source.resolve()
        if resolved != root and root not in resolved.parents:
            continue
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative.as_posix())
    if not copied:
        raise RuntimeError("Snapshot Strix kosong setelah filter keamanan.")
    return copied


def _configured_budget() -> float:
    try:
        budget = float(os.getenv("STRIX_MAX_BUDGET_USD", "0.5"))
    except ValueError as exc:
        raise ValueError("STRIX_MAX_BUDGET_USD harus angka.") from exc
    if not math.isfinite(budget) or not 0 < budget <= 5:
        raise ValueError("STRIX_MAX_BUDGET_USD harus lebih dari 0 dan maksimal 5.")
    return budget


def _configured_timeout() -> int:
    try:
        timeout = int(os.getenv("STRIX_TIMEOUT_SECONDS", "3600"))
    except ValueError as exc:
        raise ValueError("STRIX_TIMEOUT_SECONDS harus bilangan bulat.") from exc
    if not 60 <= timeout <= 7200:
        raise ValueError("STRIX_TIMEOUT_SECONDS harus 60-7200.")
    return timeout


def _build_command(uvx: str, snapshot: Path, budget: float) -> list[str]:
    return [
        uvx,
        "--from",
        STRIX_PACKAGE,
        "strix",
        "-n",
        "-t",
        str(snapshot),
        "--scan-mode",
        "quick",
        "--scope-mode",
        "full",
        "--max-budget-usd",
        str(budget),
    ]


def _child_env(home: Path, key: str) -> dict[str, str]:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "TMPDIR": str(home / "tmp"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "NO_COLOR": "1",
        "STRIX_LLM": os.getenv("STRIX_LLM", crewai_model_id(SECURITY_MODEL)),
        "LLM_API_KEY": key,
        "STRIX_IMAGE": STRIX_IMAGE,
        "STRIX_RUNTIME_BACKEND": "docker",
        "STRIX_TELEMETRY": "false",
        "STRIX_REASONING_EFFORT": "medium",
    }
    for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "XDG_RUNTIME_DIR", "UV_CACHE_DIR"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    return environment


def _execute_scan(
    command: list[str], env: dict[str, str], cwd: Path, timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd),
        env=env,
        check=False,
        shell=False,
    )


def _clean_output(result: subprocess.CompletedProcess[str], secret: str) -> str:
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    cleaned = _ANSI_ESCAPE.sub("", combined).replace(secret, "[REDACTED]")
    return cleaned.strip()[-4000:]


def _latest_report(runs_root: Path, before: set[Path]) -> str:
    if not runs_root.is_dir():
        return str(runs_root)
    new_runs = [path for path in runs_root.iterdir() if path.is_dir() and path not in before]
    if not new_runs:
        return str(runs_root)
    return str(max(new_runs, key=lambda path: path.stat().st_mtime))


class StrixScannerTool(BaseTool):
    name: str = "Isolated Strix Security Scanner"
    description: str = (
        "Jalankan Strix quick scan report-only pada snapshot aman BIMA_CORE. "
        'Hanya panggil jika Bima eksplisit meminta scan Strix. Input: {"mode":"quick"}. '
        "Memerlukan STRIX_ENABLED=true, uvx, Docker aktif, dan OPENROUTER_API_KEY."
    )

    def _run(self, input_str: str) -> str:
        if not _enabled():
            return "FAILED|Strix dinonaktifkan. Set STRIX_ENABLED=true untuk opt-in."
        try:
            payload: Any = json.loads(input_str or "{}")
            if not isinstance(payload, dict) or set(payload) - {"mode"}:
                raise ValueError("Input hanya menerima JSON object dengan field mode.")
            if payload.get("mode", "quick") != "quick":
                raise ValueError("Pilot Strix hanya mengizinkan mode quick.")

            uvx, _docker = _preflight()
            key = _api_key()
            budget = _configured_budget()
            timeout = _configured_timeout()
            security_dir = Path(OUTPUT_DIR).resolve() / "security"
            runs_root = security_dir / "strix_runs"
            security_dir.mkdir(parents=True, exist_ok=True)
            before = set(runs_root.iterdir()) if runs_root.is_dir() else set()

            with tempfile.TemporaryDirectory(prefix="bima-strix-") as temp_dir:
                temp_root = Path(temp_dir)
                snapshot = temp_root / "snapshot"
                home = temp_root / "home"
                (home / "tmp").mkdir(parents=True)
                files = _create_snapshot(Path(BASE_DIR), snapshot)
                command = _build_command(uvx, snapshot, budget)
                environment = _child_env(home, key)
                result = _execute_scan(command, environment, security_dir, timeout)
                output = _clean_output(result, key)

            response = {
                "files_scanned": len(files),
                "report": _latest_report(runs_root, before),
                "output": output,
            }
            serialized = json.dumps(response, ensure_ascii=False)
            if result.returncode == 0:
                return f"SUCCESS|{serialized}"
            if result.returncode == 2:
                return f"FINDINGS|{serialized}"
            return f"FAILED|Strix exit {result.returncode}|{serialized}"
        except subprocess.TimeoutExpired:
            return "FAILED|Strix melewati batas waktu dan dihentikan."
        except (json.JSONDecodeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return f"FAILED|{exc}"
