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
        text = await extract_text_async(img_bytes)
        if not text:
            await progress.edit(content=f"🤷 Ga ada text terdeteksi di `{att.filename}`.")
            return
        # Truncate to Discord limit
        if len(text) > 1800:
            text = text[:1800] + "\n\n... _(terpotong)_"
        await progress.edit(content=f"📄 **OCR `{att.filename}`:**\n```\n{text}\n```")
    except Exception as e:
        logger.exception("[ocr] gagal")
        await progress.edit(content=f"❌ Gagal OCR: `{e}`")
