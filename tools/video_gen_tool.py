"""VideoGenTool — text-to-video via OpenRouter Kling v3 Pro (primary) atau fal.ai Kling Standard (fallback)."""
from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

import httpx
from crewai.tools import BaseTool

logger = logging.getLogger("bima_core")

_MODEL = os.environ.get("VIDEO_GEN_MODEL", "kwaivgi/kling-v3.0-pro").strip()
_DURATION = int(os.environ.get("VIDEO_GEN_DURATION", "5"))
_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
_OUTPUT_DIR.mkdir(exist_ok=True)
_POLL_INTERVAL = 8
_POLL_MAX = int(os.environ.get("VIDEO_POLL_MAX", "25"))  # 25 * 8s = 200s cap


class VideoGenTool(BaseTool):
    name: str = "Video Generation Tool"
    description: str = (
        "Generate video pendek (default 5 detik) dari prompt teks. "
        "PROSES LAMA (1-3 menit). Pakai HANYA kalau Bima eksplisit minta "
        "'bikin video', 'animasiin', 'render video'. "
        "Input: prompt deskripsi adegan (Bahasa Indonesia atau English). "
        "Output: SUCCESS|<filepath>|<message> atau FAILED|<error>."
    )

    def _run(self, prompt: str) -> str:
        prompt = (prompt or "").strip()
        if not prompt:
            return "FAILED|Prompt kosong"

        # Primary: OpenRouter
        result = self._try_openrouter(prompt)
        if result.startswith("SUCCESS|"):
            return result

        # Fallback: fal.ai
        logger.warning(f"[VIDEO_GEN] OpenRouter failed ({result[:120]}), trying fal.ai fallback")
        fal_result = self._try_fal(prompt)
        if fal_result.startswith("SUCCESS|"):
            return fal_result

        return f"FAILED|OpenRouter: {result[7:100]} / fal.ai: {fal_result[7:100]}"

    def _try_openrouter(self, prompt: str) -> str:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return "FAILED|OPENROUTER_API_KEY belum diset"

        base = "https://openrouter.ai/api/v1"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Submit job
        try:
            submit = httpx.post(
                f"{base}/video/generations",
                headers=headers,
                json={"model": _MODEL, "prompt": prompt, "duration": _DURATION},
                timeout=30,
            )
            submit.raise_for_status()
            submit_data = submit.json()
        except Exception as e:
            return f"FAILED|submit error: {e}"

        job_id = submit_data.get("id") or submit_data.get("job_id")
        if not job_id:
            return f"FAILED|no job_id: {str(submit_data)[:200]}"

        logger.info(f"[VIDEO_GEN] OpenRouter job submitted: {job_id} (model={_MODEL}, duration={_DURATION}s)")

        # Poll
        for i in range(_POLL_MAX):
            time.sleep(_POLL_INTERVAL)
            try:
                status_resp = httpx.get(
                    f"{base}/video/generations/{job_id}",
                    headers=headers,
                    timeout=15,
                )
                status_data = status_resp.json()
            except Exception as e:
                logger.warning(f"[VIDEO_GEN] poll {i+1}/{_POLL_MAX} HTTP error: {e}")
                continue

            state = str(status_data.get("status", "")).lower()
            logger.info(f"[VIDEO_GEN] poll {i+1}/{_POLL_MAX} state={state}")

            if state in ("succeeded", "completed", "success"):
                # Try multiple response schema variants (OpenRouter beta)
                video_url = (
                    (status_data.get("output") or {}).get("video_url")
                    or status_data.get("video_url")
                    or (status_data.get("output") or {}).get("url")
                )
                if not video_url:
                    return f"FAILED|succeeded but no video_url: {str(status_data)[:200]}"
                return self._download_and_save(video_url, prompt, label="kling-v3-pro")

            if state in ("failed", "canceled", "error"):
                err = status_data.get("error") or status_data.get("message", "")
                return f"FAILED|gen {state}: {str(err)[:200]}"

        return f"FAILED|timeout {_POLL_MAX * _POLL_INTERVAL}s polling"

    def _try_fal(self, prompt: str) -> str:
        fal_key = os.environ.get("FAL_KEY", "").strip()
        if not fal_key:
            return "FAILED|FAL_KEY belum diset (fallback skipped)"

        try:
            import fal_client
        except ImportError:
            return "FAILED|Package 'fal-client' belum terinstall"

        os.environ["FAL_KEY"] = fal_key  # fal_client read from env
        try:
            logger.info(f"[VIDEO_GEN] fal.ai submit Kling v3 Standard")
            result = fal_client.subscribe(
                "fal-ai/kling-video/v3.0/standard/text-to-video",
                arguments={"prompt": prompt, "duration": str(_DURATION)},
            )
        except Exception as e:
            return f"FAILED|fal.ai error: {e}"

        video_url = None
        if isinstance(result, dict):
            video_url = (result.get("video") or {}).get("url") or result.get("url")
        if not video_url:
            return f"FAILED|fal.ai no video.url: {str(result)[:200]}"
        return self._download_and_save(video_url, prompt, label="kling-v3-std-fal")

    def _download_and_save(self, video_url: str, prompt: str, label: str) -> str:
        try:
            raw = httpx.get(video_url, timeout=60).content
        except Exception as e:
            return f"FAILED|download error: {e}"

        if len(raw) < 1024:
            return f"FAILED|download too small ({len(raw)} bytes)"

        slug = hashlib.md5(prompt.encode()).hexdigest()[:8]
        fp = _OUTPUT_DIR / f"anisa_vid_{slug}_{int(time.time())}.mp4"
        fp.write_bytes(raw)

        try:
            from core.output_prune import prune_outputs
            prune_outputs(_OUTPUT_DIR, "anisa_vid_*.mp4", keep=10)
        except Exception:
            pass

        size_mb = len(raw) / (1024 * 1024)
        logger.info(f"[VIDEO_GEN] Saved {fp} ({size_mb:.1f} MB) source={label}")
        return f"SUCCESS|{fp}|Video siap ({size_mb:.1f} MB, {_DURATION}s, {label})"
