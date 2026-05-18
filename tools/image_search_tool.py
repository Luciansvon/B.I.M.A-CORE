"""Image Search Tool — cari + download gambar dari internet.
PRIORITAS: Wikimedia Commons (license aman) → fallback Serper Images.

Awalnya inline di teams/t4_admin.py, extracted ke sini supaya bisa di-share
ke team Intel (user-facing image search) dan tetap dipakai team Admin
(buat embed gambar di PDF/Word).
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime

import httpx
from crewai.tools import BaseTool

from config import OUTPUT_DIR

logger = logging.getLogger("bima_core")


class ImageSearchTool(BaseTool):
    name: str = "Image Search Tool"
    description: str = """Cari + download gambar dari internet ke disk lokal.
    PRIORITAS: Wikimedia Commons (license aman untuk publikasi/akademik) → fallback Serper Images.
    Cocok untuk: logo institusi/kampus, foto produk, gambar referensi, ilustrasi penelitian.
    Input: keyword pencarian. Contoh: 'logo Universitas Indonesia', 'kayu jati Jepara', 'Rattus norvegicus'.
    Output format: SUCCESS|/path/to/image.jpg|Sumber: ... | License: ... | URL: ..."""

    def _run(self, query: str) -> str:
        safe_q = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')[:50]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # === 1. Wikimedia Commons (license aman utk akademik) ===
        try:
            resp = httpx.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "generator": "search",
                    "gsrsearch": query,
                    "gsrnamespace": 6,
                    "gsrlimit": 8,
                    "prop": "imageinfo",
                    "iiprop": "url|mime|extmetadata",
                    "iiurlwidth": 800,
                },
                headers={"User-Agent": "BIMA-Core-Research/1.0 (academic-use)"},
                timeout=15,
            )
            data = resp.json()
            pages = list(data.get("query", {}).get("pages", {}).values())
            pages.sort(key=lambda p: p.get("index", 999))

            for page in pages:
                info = (page.get("imageinfo") or [{}])[0]
                mime = info.get("mime", "")
                if mime not in ("image/jpeg", "image/png"):
                    continue
                img_url = info.get("thumburl") or info.get("url")
                if not img_url:
                    continue

                img_resp = httpx.get(
                    img_url,
                    headers={"User-Agent": "BIMA-Core-Research/1.0 (academic-use)"},
                    follow_redirects=True,
                    timeout=20,
                )
                if img_resp.status_code != 200 or len(img_resp.content) < 5000:
                    continue

                ext = ".jpg" if mime == "image/jpeg" else ".png"
                filename = f"img_{safe_q}_{timestamp}{ext}"
                filepath = OUTPUT_DIR / filename
                filepath.write_bytes(img_resp.content)

                title = page.get("title", "Unknown")
                meta = info.get("extmetadata", {})
                license_short = meta.get("LicenseShortName", {}).get("value", "Lihat sumber")
                artist = meta.get("Artist", {}).get("value", "")
                if "<" in artist:
                    artist = re.sub(r"<[^>]+>", "", artist).strip()
                source_page = f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}"

                return (
                    f"SUCCESS|{filepath}|"
                    f"Sumber: Wikimedia Commons - {title} | "
                    f"License: {license_short} | "
                    f"Artist: {artist or 'tidak disebutkan'} | "
                    f"URL Citation: {source_page}"
                )
            logger.info(f"[IMG] Wikimedia kosong untuk '{query}', fallback ke Serper")
        except Exception as e:
            logger.warning(f"[IMG] Wikimedia error: {e}, fallback ke Serper")

        # === 2. Serper Images (fallback) ===
        serper_key = os.environ.get("SERPER_API_KEY", "")
        if not serper_key:
            return f"FAILED|Tidak ada gambar di Wikimedia untuk '{query}', dan SERPER_API_KEY tidak tersedia untuk fallback"

        try:
            resp = httpx.post(
                "https://google.serper.dev/images",
                headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                json={"q": query, "num": 8},
                timeout=15,
            )
            for item in resp.json().get("images", []):
                img_url = item.get("imageUrl") or ""
                lower_url = img_url.lower()
                if not (".jpg" in lower_url or ".jpeg" in lower_url or ".png" in lower_url):
                    continue

                try:
                    img_resp = httpx.get(
                        img_url,
                        headers={"User-Agent": "Mozilla/5.0 (BIMA-Core)"},
                        follow_redirects=True,
                        timeout=15,
                    )
                except Exception:
                    continue
                if img_resp.status_code != 200 or len(img_resp.content) < 5000:
                    continue

                ext = ".jpg" if (".jpg" in lower_url or ".jpeg" in lower_url) else ".png"
                filename = f"img_{safe_q}_{timestamp}{ext}"
                filepath = OUTPUT_DIR / filename
                filepath.write_bytes(img_resp.content)

                source = item.get("source", "Google Images")
                return (
                    f"SUCCESS|{filepath}|"
                    f"Sumber: {source} (via Google Images) | "
                    f"License: Periksa sumber asli — gunakan dengan hati-hati untuk publikasi akademik | "
                    f"URL Citation: {img_url}"
                )

            return f"FAILED|Tidak ada gambar valid ditemukan untuk '{query}' di Wikimedia maupun Serper"
        except Exception as e:
            logger.error(f"[IMG] Serper Images error: {e}", exc_info=True)
            return f"FAILED|Image search gagal: {e}"
