"""B.I.M.A Core — Browser Use Tool.

Wrapper CrewAI BaseTool untuk `browser-use` library (Playwright + LLM agent).
Dipake intel_agent untuk task yang butuh INTERACTIVE browsing — login, click,
form fill, SPA navigation, JS-heavy site. Read-only static fetch tetap pakai
WebFetchTool / Fetcher existing (lebih cepat + murah).

Pattern: mirror tools/prompt_optimizer.py (OpenAI client + OpenRouter base_url).
"""
from __future__ import annotations

import asyncio
import logging
import os

from crewai.tools import BaseTool

logger = logging.getLogger("bima_core.browser_use")

_DEFAULT_MODEL = "deepseek/deepseek-v4-flash"  # hemat — banyak action per task
_MAX_STEPS = 20  # cap actions per task biar gak runaway
_OUTPUT_TRUNCATE = 4000  # avoid Discord overflow + token waste


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
            from browser_use import Agent
            from browser_use.llm.openai.chat import ChatOpenAI
        except ImportError as e:
            return f"FAILED|browser-use gak ke-install: {e}"

        try:
            llm = ChatOpenAI(
                model=_DEFAULT_MODEL,
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.1,
            )
            agent = Agent(task=task, llm=llm)
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

        return f"SUCCESS|browser_use|{result}"
