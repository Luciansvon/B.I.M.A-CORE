"""B.I.M.A Core — Browser Use Tool.

Wrapper CrewAI BaseTool untuk `browser-use` library (Playwright + LLM agent).
Dipake intel_agent untuk task yang butuh INTERACTIVE browsing — login, click,
form fill, SPA navigation, JS-heavy site. Read-only static fetch tetap pakai
WebFetchTool / Fetcher existing (lebih cepat + murah).

Visibility hybrid (lo bisa monitor process-nya):
- Default: headless (gak nongol di desktop). Set `BROWSER_USE_HEADED=1` di .env
  buat toggle visible — Chromium window muncul (butuh WSLg di Windows 11).
- Video: tiap session di-record ke `outputs/browser_use/{timestamp}/`. Bisa lo
  review post-hoc kalau curious agent ngapain.

Pattern: mirror tools/prompt_optimizer.py (OpenAI client + OpenRouter base_url).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from crewai.tools import BaseTool

logger = logging.getLogger("bima_core.browser_use")

# Gemini 3.1 Flash: vision native + TTFT cepat. DeepSeek gak support vision,
# bikin agent buta di JS-heavy SPA. Override via env BROWSER_USE_MODEL=<id>.
_DEFAULT_MODEL = os.environ.get("BROWSER_USE_MODEL", "google/gemini-3.1-flash").strip()
_MAX_STEPS = 20  # cap actions per task biar gak runaway
_OUTPUT_TRUNCATE = 4000  # avoid Discord overflow + token waste

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VIDEO_BASE_DIR = _PROJECT_ROOT / "outputs" / "browser_use"


def _is_headed() -> bool:
    """Toggle via env BROWSER_USE_HEADED=1 → window Chromium visible (WSLg)."""
    return os.environ.get("BROWSER_USE_HEADED", "0").strip().lower() in ("1", "true", "yes", "on")


def _should_record() -> bool:
    """Toggle via env BROWSER_USE_RECORD=1 → MP4 video per session.
    Default OFF — disk + I/O overhead. Pakai headed mode buat live monitor."""
    return os.environ.get("BROWSER_USE_RECORD", "0").strip().lower() in ("1", "true", "yes", "on")


class BrowserUseTool(BaseTool):
    name: str = "Browser Use Tool"
    description: str = """Interactive browser automation — login, click, fill form, navigate SPA / JS-heavy site.
    PAKAI HANYA kalau task butuh aksi (click, type, scroll, multi-step navigation).
    Untuk read-only fetch URL, prefer WebFetchTool atau AsyncMultiFetchTool — lebih cepat & murah.
    Input: instruksi natural language. Contoh:
    - "Go to github.com/trending and return top 3 Python repos this week"
    - "Login to portal X with credentials (Bima provides), then download report Y"
    - "Open Tokopedia search 'kayu pinus', filter 'official store', return top 5 prices"
    Output: hasil akhir agent (text) atau FAILED|<error>."""

    def _run(self, task: str) -> str:
        task = (task or "").strip()
        if not task:
            return "FAILED|task kosong"

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return "FAILED|OPENROUTER_API_KEY gak diset"

        try:
            from browser_use import Agent, BrowserProfile
            from browser_use.llm.openai.chat import ChatOpenAI
        except ImportError as e:
            return f"FAILED|browser-use gak ke-install: {e}"

        # Visibility + recording settings
        headed = _is_headed()
        record = _should_record()
        session_dir = None
        if record:
            session_dir = _VIDEO_BASE_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                session_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"video dir create gagal ({e}), skip record")
                session_dir = None

        try:
            llm = ChatOpenAI(
                model=_DEFAULT_MODEL,
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.1,
            )
            # Speed-tune: matikan highlight animasi 1-detik per click (default browser-use)
            # + minimize wait. User tetep bisa lihat cursor + klik di headed window,
            # cuma tanpa overlay kuning yang nge-add 1s per action.
            profile_kwargs = {
                "headless": not headed,
                "highlight_elements": False,
                "interaction_highlight_duration": 0.0,
                "wait_between_actions": 0.0,
                "minimum_wait_page_load_time": 0.1,  # default 0.25, lebih agresif
            }
            if session_dir is not None:
                profile_kwargs["record_video_dir"] = str(session_dir)
            profile = BrowserProfile(**profile_kwargs)
            agent = Agent(task=task, llm=llm, browser_profile=profile)
            logger.info(f"browser-use start: headed={headed}, video_dir={session_dir}")
        except Exception as e:
            logger.exception("browser-use init error")
            return f"FAILED|init: {e}"

        try:
            # asyncio.run aman karena BaseTool._run dipanggil sync di dalam thread
            # (CrewAI crew.kickoff via asyncio.to_thread di langgraph node).
            history = asyncio.run(agent.run(max_steps=_MAX_STEPS))
        except Exception as e:
            logger.exception("browser-use run error")
            return f"FAILED|run: {e}"

        try:
            final = history.final_result() if hasattr(history, "final_result") else str(history)
        except Exception as e:
            logger.warning(f"final_result extract gagal, fallback str(): {e}")
            final = str(history)

        if not final or not str(final).strip():
            return "FAILED|browser-use return empty (kemungkinan max_steps reached tanpa hasil)"

        result = str(final).strip()
        if len(result) > _OUTPUT_TRUNCATE:
            result = result[:_OUTPUT_TRUNCATE] + "\n...[truncated]"

        # Append video hint kalau ke-record (gak attach ke Discord, just info)
        video_hint = ""
        if session_dir is not None:
            videos = list(session_dir.glob("*.webm")) + list(session_dir.glob("*.mp4"))
            if videos:
                video_hint = f"\n\n_📹 Rekaman session: {videos[0]}_"

        return f"SUCCESS|browser_use|{result}{video_hint}"
