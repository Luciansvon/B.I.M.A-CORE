"""CrewAI wrapper for the dependency-isolated Browser Use worker."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess

from crewai.tools import BaseTool


logger = logging.getLogger("bima_core.browser_use")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WORKER_PATH = _PROJECT_ROOT / "services" / "browser" / "worker.py"
_DEFAULT_WORKER_PYTHON = (
    _PROJECT_ROOT / "services" / "browser" / ".venv" / "bin" / "python"
)
_OUTPUT_TRUNCATE = 4000


def _browser_worker_python() -> Path:
    configured = os.environ.get("BROWSER_WORKER_PYTHON", "").strip()
    return Path(configured) if configured else _DEFAULT_WORKER_PYTHON


def _worker_timeout() -> int:
    try:
        return max(30, int(os.environ.get("BROWSER_WORKER_TIMEOUT", "900")))
    except ValueError:
        return 900


def _parse_worker_response(stdout: str) -> dict:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("worker tidak mengembalikan output")
    return json.loads(lines[-1])


class BrowserUseTool(BaseTool):
    name: str = "Browser Use Tool"
    description: str = """Interactive browser automation for login, click, forms, and JS-heavy sites.
    Use static fetch tools for read-only URLs. Input is a natural-language browser task."""

    def _run(self, task: str) -> str:
        task = (task or "").strip()
        if not task:
            return "FAILED|task kosong"
        if not os.environ.get("OPENROUTER_API_KEY"):
            return "FAILED|OPENROUTER_API_KEY gak diset"

        worker_python = _browser_worker_python()
        if not worker_python.is_file():
            return f"FAILED|browser worker env belum siap: {worker_python}"
        if not _WORKER_PATH.is_file():
            return f"FAILED|browser worker script gak ada: {_WORKER_PATH}"

        payload = json.dumps({"task": task}, ensure_ascii=False)
        try:
            completed = subprocess.run(
                [str(worker_python), str(_WORKER_PATH)],
                input=payload,
                text=True,
                capture_output=True,
                cwd=str(_PROJECT_ROOT),
                env=os.environ.copy(),
                timeout=_worker_timeout(),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"FAILED|browser worker timeout >{_worker_timeout()}s"
        except OSError as exc:
            logger.exception("browser worker spawn error")
            return f"FAILED|browser worker spawn: {exc}"

        if completed.returncode != 0:
            error = (completed.stderr or completed.stdout or "unknown error")[-500:].strip()
            return f"FAILED|browser worker exit={completed.returncode}: {error}"

        try:
            response = _parse_worker_response(completed.stdout)
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("browser worker output invalid: %s", exc)
            return f"FAILED|browser worker output invalid: {exc}"

        if not response.get("ok"):
            return f"FAILED|{response.get('error') or 'browser worker gagal'}"

        result = str(response.get("result") or "").strip()
        if not result:
            return "FAILED|browser-use return empty"
        if len(result) > _OUTPUT_TRUNCATE:
            result = result[:_OUTPUT_TRUNCATE] + "\n...[truncated]"

        video_path = response.get("video_path")
        video_hint = f"\n\n_Rekaman session: {video_path}_" if video_path else ""
        return f"SUCCESS|browser_use|{result}{video_hint}"
