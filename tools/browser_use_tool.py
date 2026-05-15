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
import re
from datetime import datetime
from pathlib import Path

from crewai.tools import BaseTool

logger = logging.getLogger("bima_core.browser_use")

# Default model: Gemini 3 Flash Preview — vision native, TTFT cepat untuk web "clean"
# (GitHub, HuggingFace, dll). Override via env BROWSER_USE_MODEL.
_DEFAULT_MODEL = os.environ.get("BROWSER_USE_MODEL", "google/gemini-3-flash-preview").strip()

# Marketplace model: Gemini 2.5 Flash — lebih cepat parse halaman ramai
# (Tokopedia/Shopee SPA berat). Override via env BROWSER_USE_MODEL_MARKETPLACE.
_MARKETPLACE_MODEL = os.environ.get("BROWSER_USE_MODEL_MARKETPLACE", "google/gemini-2.5-flash").strip()

# Trigger per-domain routing: kalau task punya keyword marketplace, downgrade ke model lebih cepat
_MARKETPLACE_PATTERN = re.compile(
    r'\b(tokopedia|shopee|lazada|bukalapak|tiktokshop|tiktok\s+shop|tiktok\.com/shop)\b',
    re.IGNORECASE,
)

_MAX_STEPS = 20  # cap actions per task biar gak runaway
_STEP_TIMEOUT = 60  # detik — safety net, kalau 1 step stuck >60s → force fail
_OUTPUT_TRUNCATE = 4000  # avoid Discord overflow + token waste


def _pick_model(task: str) -> tuple[str, str]:
    """Return (model_id, label). Label dipakai buat logging."""
    if _MARKETPLACE_PATTERN.search(task or ""):
        return _MARKETPLACE_MODEL, "marketplace"
    return _DEFAULT_MODEL, "default"


def _make_step_callback():
    """Hook untuk log tiap step agent — visible di pm2 logs anisa-v3 -f.
    Extract action info (click/extract/type/etc) + target element kalau ada."""
    counter = {"n": 0}

    async def on_step(*args, **kwargs):
        counter["n"] += 1
        url_hint = ""
        action_hint = ""

        # Extract URL + action info dari browser-use callback args
        # Browser-use 0.12.x biasanya kirim browser_state_summary, agent_output, step_number
        try:
            for arg in list(args) + list(kwargs.values()):
                # URL dari browser_state
                if not url_hint:
                    u = getattr(arg, "url", None)
                    if u:
                        url_hint = f" url={str(u)[:80]}"
                # Action dari agent_output: .action[] list of action models
                if not action_hint:
                    actions = getattr(arg, "action", None)
                    if actions and isinstance(actions, (list, tuple)) and actions:
                        first = actions[0]
                        # Setiap action adalah Pydantic model dengan satu field non-None
                        try:
                            d = first.model_dump(exclude_none=True) if hasattr(first, "model_dump") else dict(first.__dict__)
                            for k, v in d.items():
                                if v is not None and k != "thinking":
                                    # Format value singkat: tampilkan key + first string field
                                    summary = ""
                                    if isinstance(v, dict):
                                        for vk in ("text", "query", "url", "index", "selector"):
                                            if vk in v and v[vk]:
                                                summary = f" {vk}={str(v[vk])[:60]}"
                                                break
                                        if not summary:
                                            summary = f" {str(v)[:60]}"
                                    else:
                                        summary = f" {str(v)[:60]}"
                                    action_hint = f" ▶ {k}{summary}"
                                    break
                        except Exception:
                            pass
        except Exception:
            pass

        msg = f"🔄 [BROWSER_USE] Step {counter['n']}{url_hint}"
        if action_hint:
            msg += action_hint
        else:
            msg += " — thinking..."
        logger.info(msg)

    return on_step

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VIDEO_BASE_DIR = _PROJECT_ROOT / "outputs" / "browser_use"
# Persistent Chrome profile khusus marketplace — login sekali, cookies stay.
# Folder ini WAJIB di-gitignore (pegang session/cookie sensitif).
_MARKETPLACE_PROFILE_DIR = _VIDEO_BASE_DIR / "profile_marketplace"


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

        # Per-domain model routing — marketplace pakai model lebih cepat
        model_id, model_label = _pick_model(task)

        # Persistent profile reuse logic — marketplace dapet profile_marketplace
        # (cookie/session survive antar request, lo login sekali doang).
        # GitHub/HN/dll tetep ephemeral biar gak cross-track sesi.
        use_persistent_profile = (model_label == "marketplace")

        try:
            llm = ChatOpenAI(
                model=model_id,
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.1,
            )
            # Visual feedback ON — highlight kotak hijau muncul 1.5s di element yang
            # mau di-click/extract. Default orange suka ke-blend di theme abu/dark.
            profile_kwargs = {
                "headless": not headed,
                "highlight_elements": True,
                "interaction_highlight_duration": 1.5,
                "interaction_highlight_color": "rgb(0, 200, 100)",
                "wait_between_actions": 0.0,
                "minimum_wait_page_load_time": 0.1,  # default 0.25, lebih agresif
                # Stealth + bypass flags:
                # - ignore-certificate-errors: bypass SSL warning (perlu kalau pakai Cloudflare WARP/MITM proxy)
                # - disable-blink-features=AutomationControlled: hide `navigator.webdriver=true` (anti-bot detection #1)
                # - disable-features=IsolateOrigins,site-per-process: kurangi side-channel detection
                # Trade-off OK karena ini browser scraping, bukan personal browsing.
                "args": [
                    "--ignore-certificate-errors",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            }
            if session_dir is not None:
                profile_kwargs["record_video_dir"] = str(session_dir)
            if use_persistent_profile:
                _MARKETPLACE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
                profile_kwargs["user_data_dir"] = str(_MARKETPLACE_PROFILE_DIR)
            profile = BrowserProfile(**profile_kwargs)
            agent = Agent(
                task=task,
                llm=llm,
                browser_profile=profile,
                step_timeout=_STEP_TIMEOUT,
                register_new_step_callback=_make_step_callback(),
            )
            profile_hint = f", profile={_MARKETPLACE_PROFILE_DIR.name}" if use_persistent_profile else ""
            logger.info(f"browser-use start: headed={headed}, model={model_id} ({model_label}){profile_hint}, step_timeout={_STEP_TIMEOUT}s, video_dir={session_dir}")
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
