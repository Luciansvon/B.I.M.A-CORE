"""ImageGenTool — text-to-image via OpenRouter (default: Gemini 3.1 Flash Image / Nano Banana 2)."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from pathlib import Path

from crewai.tools import BaseTool

logger = logging.getLogger("bima_core")

_MODEL = os.environ.get("IMAGE_GEN_MODEL", "google/gemini-3.1-flash-image-preview").strip()
_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
_OUTPUT_DIR.mkdir(exist_ok=True)


class ImageGenTool(BaseTool):
    name: str = "Image Generation Tool"
    description: str = (
        "Generate gambar dari prompt teks. Pakai HANYA kalau Bima eksplisit minta "
        "'bikin gambar', 'gambarin', 'visualisasi', 'illustration'. "
        "Input: prompt deskripsi gambar (Bahasa Indonesia atau English). "
        "Output: SUCCESS|<filepath>|<message> atau FAILED|<error>."
    )

    def _run(self, prompt: str) -> str:
        prompt = (prompt or "").strip()
        if not prompt:
            return "FAILED|Prompt kosong"

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return "FAILED|OPENROUTER_API_KEY belum diset"

        try:
            from openai import OpenAI
        except ImportError:
            return "FAILED|Package 'openai' belum terinstall — pip install openai"

        try:
            client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
            resp = client.chat.completions.create(
                model=_MODEL,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"modalities": ["image", "text"]},
            )
        except Exception as e:
            logger.exception("[IMAGE_GEN] OpenRouter call gagal")
            return f"FAILED|OpenRouter call error: {e}"

        # Extract image dari response (struktur: choices[0].message.images[0].image_url.url)
        try:
            msg = resp.choices[0].message
            images = getattr(msg, "images", None)
            if not images:
                # Defensive: cek dict access
                msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else {}
                images = msg_dict.get("images") or []
            if not images:
                content_preview = (getattr(msg, "content", "") or "")[:200]
                return f"FAILED|Model gak return image (text only: {content_preview})"
            first = images[0]
            url = first["image_url"]["url"] if isinstance(first, dict) else first.image_url.url
        except Exception as e:
            return f"FAILED|Parse response error: {e}"

        if not url.startswith("data:image"):
            return f"FAILED|Format image_url tidak diharapkan: {url[:80]}"

        try:
            b64data = url.split(",", 1)[1]
            raw = base64.b64decode(b64data)
        except Exception as e:
            return f"FAILED|Base64 decode error: {e}"

        slug = hashlib.md5(prompt.encode()).hexdigest()[:8]
        fp = _OUTPUT_DIR / f"anisa_img_{slug}_{int(time.time())}.png"
        fp.write_bytes(raw)

        # Prune outputs (keep last 15 anisa_img files)
        try:
            from core.output_prune import prune_outputs
            prune_outputs(_OUTPUT_DIR, "anisa_img_*.png", keep=15)
        except Exception:
            pass

        size_kb = len(raw) // 1024
        logger.info(f"[IMAGE_GEN] Saved {fp} ({size_kb} KB) model={_MODEL}")
        return f"SUCCESS|{fp}|Gambar siap ({size_kb} KB, {_MODEL.split('/')[-1]})"
