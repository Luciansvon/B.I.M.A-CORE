"""Multi-channel notification helper: Discord-first dengan apprise fallback.

Pakai `safe_notify(channel, content)` di tempat-tempat critical (startup notif,
saham alert, error notification) supaya kalau Discord API down, alert tetep
nyampe via Telegram/ntfy/email/dll.

Setup channel fallback:
- Set env `APPRISE_URLS` di .env, comma-separated.
- Format URL: lihat https://github.com/caronc/apprise/wiki
- Contoh: `tgram://BOT_TOKEN/CHAT_ID,ntfy://default/bima-alerts`

Kalau APPRISE_URLS kosong, fallback no-op (cuma log warning).
"""
import asyncio
import logging
import os
from typing import Optional

import apprise
import discord

logger = logging.getLogger("bima_core.notify")

_apprise_instance: Optional[apprise.Apprise] = None
_apprise_init_done = False


def _get_apprise() -> apprise.Apprise:
    """Lazy-init apprise dengan channel dari APPRISE_URLS env."""
    global _apprise_instance, _apprise_init_done
    if _apprise_init_done:
        return _apprise_instance  # type: ignore[return-value]
    a = apprise.Apprise()
    urls = os.environ.get("APPRISE_URLS", "").strip()
    if urls:
        for url in [u.strip() for u in urls.split(",") if u.strip()]:
            if a.add(url):
                # Mask token bagian URL — log preview aja
                preview = url[:24] + "…" if len(url) > 24 else url
                logger.info(f"[notify] apprise channel ready: {preview}")
            else:
                logger.warning(f"[notify] apprise URL invalid: {url[:30]}")
    else:
        logger.info("[notify] APPRISE_URLS empty — fallback disabled, Discord-only mode")
    _apprise_instance = a
    _apprise_init_done = True
    return a


async def safe_notify(
    channel: Optional[discord.abc.Messageable],
    content: str = "",
    *,
    embed: Optional[discord.Embed] = None,
    title: str = "Anisa Alert",
    fallback_on_fail: bool = True,
) -> bool:
    """Coba kirim ke Discord channel. Kalau gagal & fallback_on_fail=True,
    fallback ke apprise.

    Return True kalau setidaknya satu jalur berhasil.
    """
    sent_discord = False
    if channel is not None:
        try:
            await channel.send(content=content, embed=embed)
            sent_discord = True
        except Exception as e:
            logger.warning(f"[notify] Discord send failed: {e}")

    if sent_discord:
        return True

    if not fallback_on_fail:
        return False

    body = content or (embed.description if embed and embed.description else "")
    if not body:
        body = "(empty body)"
    apr = _get_apprise()
    if not apr.urls():
        logger.warning("[notify] no fallback channel configured — alert lost")
        return False
    ok = await asyncio.to_thread(apr.notify, body=body, title=title)
    if ok:
        logger.info(f"[notify] sent via apprise fallback (title: {title})")
        return True
    logger.error("[notify] apprise fallback also failed")
    return False


async def broadcast_critical(content: str, title: str = "Anisa CRITICAL") -> bool:
    """Push ke SEMUA apprise channel langsung tanpa lewat Discord.
    Cocok buat alert dari background task yg ga punya akses channel Discord
    (mis. exception handler global).
    """
    apr = _get_apprise()
    if not apr.urls():
        logger.warning("[notify] broadcast_critical: no apprise channel — alert lost")
        return False
    ok = await asyncio.to_thread(apr.notify, body=content, title=title)
    if ok:
        logger.info(f"[notify] broadcast_critical sent: {title}")
        return True
    logger.error("[notify] broadcast_critical failed")
    return False
