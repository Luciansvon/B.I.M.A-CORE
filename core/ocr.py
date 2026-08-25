"""OCR helper pakai EasyOCR. Lazy-load model (~80MB) supaya boot tetep cepat.

Pemakaian:
    from core.ocr import extract_text
    text = await extract_text_async(image_bytes)
    # atau sync: text = extract_text(image_bytes)

Discord command `!ocr` wire-nya di core/discord_bot.py.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("bima_core.ocr")

_reader = None  # type: ignore[var-annotated]
_reader_lock = asyncio.Lock()


def _build_reader():
    """Init EasyOCR Reader. Bahasa: Indonesia + English."""
    import easyocr  # heavy import, lazy
    return easyocr.Reader(["id", "en"], gpu=False, verbose=False)


def extract_text(image_bytes: bytes) -> str:
    """Sync OCR — return concatenated text dari semua region terdeteksi."""
    global _reader
    if _reader is None:
        logger.info("[ocr] init EasyOCR Reader (id+en, ~80MB) — first call only")
        _reader = _build_reader()
    # readtext(image) bisa terima bytes; return [(bbox, text, conf), ...]
    results = _reader.readtext(image_bytes)
    return "\n".join(t for _, t, _ in results if t.strip())


async def extract_text_async(image_bytes: bytes) -> str:
    """Async wrapper — offload ke thread biar discord.py event loop ga blocked."""
    return await asyncio.to_thread(extract_text, image_bytes)


def _detect_image_mime(image_bytes: bytes) -> str:
    if image_bytes[:4] == b"\x89PNG":
        return "image/png"
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def extract_text_vlm(image_bytes: bytes) -> str:
    """OCR pakai VLM (Gemini via OpenRouter) — jauh lebih akurat dari easyocr buat
    layout kompleks, tabel, tulisan tangan, teks miring. Raise kalau gagal supaya
    caller bisa fallback ke easyocr (offline)."""
    import base64
    import os

    from openai import OpenAI

    from config import VISUAL_MODEL_NAME
    from core.model_router import openrouter_extra_body

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY tidak tersedia untuk VLM OCR")

    mime = _detect_image_mime(image_bytes)
    b64 = base64.b64encode(image_bytes).decode()
    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    resp = client.chat.completions.create(
        model=VISUAL_MODEL_NAME,
        extra_body=openrouter_extra_body("visual"),
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "Ekstrak SEMUA teks dari gambar ini persis apa adanya (verbatim). "
                    "Pertahankan urutan baris dan struktur asli. "
                    "Output HANYA teksnya — tanpa komentar, penjelasan, atau markdown pembungkus. "
                    "Kalau tidak ada teks sama sekali, balas string kosong."
                )},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
        temperature=0,
        max_tokens=2000,
    )
    return (resp.choices[0].message.content or "").strip()


async def extract_text_vlm_async(image_bytes: bytes) -> str:
    """Async wrapper VLM OCR."""
    return await asyncio.to_thread(extract_text_vlm, image_bytes)


async def handle_ocr_command(message, bot_client=None) -> None:
    """Discord `!ocr` handler — extract text dari image attachment."""
    import httpx

    if not message.attachments:
        await message.reply(
            "📷 **`!ocr` — Extract text dari image**\n"
            "Upload image (PNG/JPG/WEBP) + ketik `!ocr`. Support Bahasa Indonesia + English."
        )
        return

    att = message.attachments[0]
    fname_lower = att.filename.lower()
    if not fname_lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
        await message.reply(f"❌ Format `{att.filename}` ga didukung. Pakai PNG/JPG/WEBP/BMP.")
        return
    if att.size > 10 * 1024 * 1024:
        await message.reply(f"❌ Image terlalu besar ({att.size / 1024 / 1024:.1f} MB). Max 10 MB.")
        return

    progress = await message.reply(f"📷 Extract text dari `{att.filename}`... (~5-15 detik first time, lebih cepat selanjutnya)")
    try:
        async with httpx.AsyncClient(timeout=30) as cx:
            resp = await cx.get(att.url, follow_redirects=True)
            resp.raise_for_status()
            img_bytes = resp.content
        # VLM (Gemini) dulu — akurasi jauh lebih baik; fallback ke easyocr (offline) kalau gagal.
        try:
            text = await extract_text_vlm_async(img_bytes)
            engine = "Gemini Vision"
        except Exception as vlm_err:
            logger.warning(f"[ocr] VLM gagal ({vlm_err}), fallback ke easyocr")
            text = await extract_text_async(img_bytes)
            engine = "easyocr"
        if not text:
            await progress.edit(content=f"🤷 Ga ada text terdeteksi di `{att.filename}`.")
            return
        # Truncate to Discord limit
        if len(text) > 1800:
            text = text[:1800] + "\n\n... _(terpotong)_"
        await progress.edit(content=f"📄 **OCR `{att.filename}`** _(via {engine})_:\n```\n{text}\n```")
    except Exception as e:
        logger.exception("[ocr] gagal")
        await progress.edit(content=f"❌ Gagal OCR: `{e}`")
