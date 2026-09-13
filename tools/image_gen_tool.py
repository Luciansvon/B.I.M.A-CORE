"""ImageGenTool — text-to-image + image-to-image via 9Router / OpenRouter
(default 9Router: ag/gemini-3.1-flash-image; fallback OpenRouter: google/gemini-3.1-flash-image)."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
import urllib.request
from pathlib import Path

from crewai.tools import BaseTool
from core.model_router import IMAGE_MODEL, get_router_credentials

logger = logging.getLogger("bima_core")

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

        api_key, base_url = get_router_credentials()
        if not api_key:
            return "FAILED|API Key router (NINEROUTER_API_KEY / OPENROUTER_API_KEY) belum diset"

        model = os.environ.get("IMAGE_GEN_MODEL", IMAGE_MODEL).strip()

        try:
            from openai import OpenAI
        except ImportError:
            return "FAILED|Package 'openai' belum terinstall — pip install openai"

        is_openrouter = "openrouter.ai" in base_url.lower()

        # Mode OpenRouter (multimodal chat completions) vs 9Router / OpenAI (/v1/images/generations)
        if is_openrouter:
            return self._run_openrouter(prompt, reference_image_paths, api_key, base_url, model)
        else:
            return self._run_images_api(prompt, reference_image_paths, api_key, base_url, model)

    def _run_images_api(
        self,
        prompt: str,
        reference_image_paths: list[str] | None,
        api_key: str,
        base_url: str,
        model: str,
    ) -> str:
        """Panggil endpoint standar /v1/images/generations (9Router atau OpenAI)."""
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)

        ref_used: list[str] = []
        extra_body: dict[str, object] = {}

        if reference_image_paths:
            encoded_refs: list[str] = []
            for img_path in reference_image_paths[:3]:
                try:
                    mime = _guess_mime(img_path)
                    with open(img_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    encoded_refs.append(f"data:{mime};base64,{b64}")
                    ref_used.append(img_path)
                except Exception as e:
                    logger.warning(f"[IMAGE_GEN] Skip ref image {img_path}: {e}")
            if encoded_refs:
                extra_body["images"] = encoded_refs
                extra_body["image"] = encoded_refs[0]

        try:
            kwargs: dict[str, object] = {
                "model": model,
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                "response_format": "b64_json",
            }
            if extra_body:
                kwargs["extra_body"] = extra_body

            resp = client.images.generate(**kwargs)
        except Exception as e:
            logger.exception(f"[IMAGE_GEN] Call {base_url}/images/generations gagal")
            return f"FAILED|Image API call error: {e}"

        try:
            if not resp.data or len(resp.data) == 0:
                return "FAILED|Model tidak mengembalikan data gambar"

            first_item = resp.data[0]
            raw: bytes | None = None

            if getattr(first_item, "b64_json", None):
                raw = base64.b64decode(first_item.b64_json)
            elif getattr(first_item, "url", None):
                with urllib.request.urlopen(first_item.url, timeout=30) as u:
                    raw = u.read()

            if not raw:
                return "FAILED|Format output gambar tidak valid (tidak ada b64_json maupun url)"
        except Exception as e:
            return f"FAILED|Parse image response error: {e}"

        return self._save_and_finish(raw, prompt, model, ref_used)

    def _run_openrouter(
        self,
        prompt: str,
        reference_image_paths: list[str] | None,
        api_key: str,
        base_url: str,
        model: str,
    ) -> str:
        """Panggil OpenRouter via chat completions multimodal."""
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)

        ref_used: list[str] = []
        if reference_image_paths:
            content_parts: list[dict] = []
            for img_path in reference_image_paths[:3]:
                try:
                    mime = _guess_mime(img_path)
                    with open(img_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    })
                    ref_used.append(img_path)
                except Exception as e:
                    logger.warning(f"[IMAGE_GEN] Skip ref image {img_path}: {e}")
            content_parts.append({"type": "text", "text": prompt})
            user_content: str | list[dict] = content_parts
        else:
            user_content = prompt

        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": user_content}],
                extra_body={"modalities": ["image", "text"]},
            )
        except Exception as e:
            logger.exception("[IMAGE_GEN] OpenRouter call gagal")
            return f"FAILED|OpenRouter call error: {e}"

        try:
            msg = resp.choices[0].message
            images = getattr(msg, "images", None)
            if not images:
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

        return self._save_and_finish(raw, prompt, model, ref_used)

    def _save_and_finish(self, raw: bytes, prompt: str, model: str, ref_used: list[str]) -> str:
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
        logger.info(f"[IMAGE_GEN] Saved {fp} ({size_kb} KB) model={model} mode={mode}{ref_info}")
        meta_extra = f", {mode}" if ref_used else ""
        return f"SUCCESS|{fp}|Gambar siap ({size_kb} KB, {model.split('/')[-1]}{meta_extra})"
