"""JSON stdin/stdout worker for Browser Use 0.13.x."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIDEO_BASE_DIR = PROJECT_ROOT / "outputs" / "browser_use"
MARKETPLACE_PROFILE_DIR = VIDEO_BASE_DIR / "profile_marketplace"
MARKETPLACE_PATTERN = re.compile(
    r"\b(tokopedia|shopee|lazada|bukalapak|tiktokshop|tiktok\s+shop|tiktok\.com/shop)\b",
    re.IGNORECASE,
)
MAX_STEPS = 20
STEP_TIMEOUT = 60
DEFAULT_BROWSER_MODEL = "google/gemini-3.7-flash"

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("bima_core.browser_worker")


def _enabled(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _pick_model(task: str) -> tuple[str, str]:
    if MARKETPLACE_PATTERN.search(task):
        return os.environ.get(
            "BROWSER_USE_MODEL_MARKETPLACE", DEFAULT_BROWSER_MODEL
        ), "marketplace"
    return os.environ.get("BROWSER_USE_MODEL", DEFAULT_BROWSER_MODEL), "default"


def _step_callback():
    counter = {"value": 0}

    async def on_step(browser_state, agent_output, step_number) -> None:
        counter["value"] += 1
        url = getattr(browser_state, "url", "")
        logger.info("step=%s url=%s", step_number or counter["value"], str(url)[:120])

    return on_step


async def run_task(task: str) -> dict:
    from browser_use import Agent, BrowserProfile
    from browser_use.llm.openai.chat import ChatOpenAI

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY gak diset"}

    headed = _enabled("BROWSER_USE_HEADED")
    record = _enabled("BROWSER_USE_RECORD")
    model_id, model_label = _pick_model(task)
    persistent = model_label == "marketplace"

    session_dir = None
    if record:
        session_dir = VIDEO_BASE_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir.mkdir(parents=True, exist_ok=True)

    profile_kwargs = {
        "headless": not headed,
        "highlight_elements": True,
        "interaction_highlight_duration": 1.5,
        "interaction_highlight_color": "rgb(0, 200, 100)",
        "wait_between_actions": 0.0,
        "minimum_wait_page_load_time": 0.1,
        "args": [
            "--ignore-certificate-errors",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    }
    if session_dir is not None:
        profile_kwargs["record_video_dir"] = session_dir
    if persistent:
        MARKETPLACE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        profile_kwargs["user_data_dir"] = MARKETPLACE_PROFILE_DIR

    llm = ChatOpenAI(
        model=model_id,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0.1,
    )
    agent = Agent(
        task=task,
        llm=llm,
        browser_profile=BrowserProfile(**profile_kwargs),
        step_timeout=STEP_TIMEOUT,
        register_new_step_callback=_step_callback(),
        enable_signal_handler=False,
    )
    history = await agent.run(max_steps=MAX_STEPS)
    result = history.final_result() if hasattr(history, "final_result") else str(history)

    video_path = None
    if session_dir is not None:
        videos = list(session_dir.glob("*.webm")) + list(session_dir.glob("*.mp4"))
        if videos:
            video_path = str(videos[0])
    return {"ok": True, "result": str(result or ""), "video_path": video_path}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        task = str(payload.get("task") or "").strip()
        if not task:
            raise ValueError("task kosong")
        response = asyncio.run(run_task(task))
    except Exception as exc:
        logger.exception("browser worker gagal")
        response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
