"""CrewAI wrapper for the dependency-isolated Browser Use worker."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import signal
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
        return max(30, int(os.environ.get("BROWSER_WORKER_TIMEOUT", "1260")))
    except ValueError:
        return 1260


def _parse_worker_response(stdout: str) -> dict:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("worker tidak mengembalikan output")
    return json.loads(lines[-1])


def _signal_worker_group(worker: subprocess.Popen[str], sig: signal.Signals) -> None:
    try:
        os.killpg(worker.pid, sig)
    except ProcessLookupError:
        return
    except OSError:
        logger.exception("browser worker process-group signal gagal")


def _terminate_worker_group(worker: subprocess.Popen[str]) -> None:
    _signal_worker_group(worker, signal.SIGTERM)
    try:
        worker.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logger.warning("browser worker masih hidup setelah SIGTERM; kirim SIGKILL")
        _signal_worker_group(worker, signal.SIGKILL)
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.error("browser worker process group tetap hidup setelah SIGKILL")


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
            return "FAILED|browser worker env belum siap"
        if not _WORKER_PATH.is_file():
            return "FAILED|browser worker script gak ada"

        payload = json.dumps({"task": task}, ensure_ascii=False)
        timeout = _worker_timeout()
        worker: subprocess.Popen[str] | None = None
        try:
            worker = subprocess.Popen(
                [str(worker_python), str(_WORKER_PATH)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(_PROJECT_ROOT),
                env=os.environ.copy(),
                start_new_session=True,
            )
            stdout, stderr = worker.communicate(payload, timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.error("browser worker timeout >%ss", timeout)
            if worker is not None:
                _terminate_worker_group(worker)
            return f"FAILED|browser worker timeout >{timeout}s"
        except OSError:
            logger.exception("browser worker spawn error")
            if worker is not None:
                _terminate_worker_group(worker)
            return "FAILED|browser worker gagal dijalankan"

        if worker.returncode != 0:
            error = (stderr or stdout or "unknown error")[-500:].strip()
            logger.error("browser worker exit=%s: %s", worker.returncode, error)
            return "FAILED|browser worker gagal"

        try:
            response = _parse_worker_response(stdout)
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("browser worker output invalid: %s", exc)
            return "FAILED|browser worker output invalid"

        if not response.get("ok"):
            logger.warning("browser worker gagal: %s", response.get("error"))
            return "FAILED|browser worker gagal"

        result = str(response.get("result") or "").strip()
        if not result:
            return "FAILED|browser-use return empty"
        if len(result) > _OUTPUT_TRUNCATE:
            result = result[:_OUTPUT_TRUNCATE] + "\n...[truncated]"

        video_path = response.get("video_path")
        video_hint = f"\n\n_Rekaman session: {video_path}_" if video_path else ""
        return f"SUCCESS|browser_use|{result}{video_hint}"
