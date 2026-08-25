"""ImageGenTool — text-to-image + image-to-image via OpenRouter
(default: Gemini 3.1 Flash Image / Nano Banana 2)."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from pathlib import Path

from crewai.tools import BaseTool
from core.path_security import resolve_allowed_path
from core.model_router import IMAGE_MODEL

logger = logging.getLogger("bima_core")

_MODEL = os.environ.get("IMAGE_GEN_MODEL", IMAGE_MODEL).strip()
_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
_OUTPUT_DIR.mkdir(exist_ok=True)

_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


def _guess_mime(path: str) -> str:
    return _MIME_MAP.get(Path(path).suffix.lower(), "image/png")


class ImageGenTool(BaseTool):
    name: str = "Image Generation Tool"
    description: str = (
        "Generate gambar dari prompt teks ATAU dari gambar referensi (image-to-image). "
        "Pakai HANYA kalau Bima eksplisit minta 'bikin gambar', 'gambarin', "
        "'visualisasi', 'illustration'. Kalau dikasih reference_image_paths, "
        "output bakal ikutin style/komposisi gambar referensi tersebut. "
        "Input: prompt (str) + optional reference_image_paths (list[str], max 3). "
        "Output: SUCCESS|<filepath>|<message> atau FAILED|<error>."
    )

    def _run(self, prompt: str, reference_image_paths: list[str] | None = None) -> str:
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

        # Build multimodal content kalau ada reference image (img2img mode)
        ref_used: list[str] = []
        if reference_image_paths:
            content_parts: list[dict] = []
            for img_path in reference_image_paths[:3]:  # cap 3 ref images
                try:
                    safe_img_path = resolve_allowed_path(
                        img_path,
                        (_OUTPUT_DIR,),
                        base_dir=_OUTPUT_DIR.parent,
                        allowed_suffixes=set(_MIME_MAP),
                    )
                except ValueError:
                    logger.warning(
                        "[IMAGE_GEN] Tolak reference image di luar outputs"
                    )
                    return "FAILED|Reference image tidak diizinkan"
                try:
                    mime = _guess_mime(str(safe_img_path))
                    with safe_img_path.open("rb") as handle:
                        b64 = base64.b64encode(handle.read()).decode()
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    })
                    ref_used.append(str(safe_img_path))
                except OSError:
                    logger.exception("[IMAGE_GEN] Gagal membaca reference image")
                    return "FAILED|Reference image gagal dibaca"
            content_parts.append({"type": "text", "text": prompt})
            user_content: str | list[dict] = content_parts
        else:
            user_content = prompt

        try:
            client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
            resp = client.chat.completions.create(
                model=_MODEL,
                messages=[{"role": "user", "content": user_content}],
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
        ref_info = f" ref={len(ref_used)}" if ref_used else ""
        mode = "img2img" if ref_used else "txt2img"
        logger.info(f"[IMAGE_GEN] Saved {fp} ({size_kb} KB) model={_MODEL} mode={mode}{ref_info}")
        meta_extra = f", {mode}" if ref_used else ""
        return f"SUCCESS|{fp}|Gambar siap ({size_kb} KB, {_MODEL.split('/')[-1]}{meta_extra})"
