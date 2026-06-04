"""Last30DaysResearchTool — perform multi-platform social media and technical sentiment research."""
from __future__ import annotations

import logging
import os
import sys
import time
import hashlib
import re
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

logger = logging.getLogger("bima_core.last30days")

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "last30days"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Tambahkan scripts directory milik last30days-skill ke sys.path agar lib folder bisa di-import langsung
_SKILL_DIR = Path(__file__).resolve().parent / "last30days-skill" / "skills" / "last30days" / "scripts"
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

try:
    from lib import env as skill_env
    from lib import pipeline as skill_pipeline
    from lib import render as skill_render
    from lib import html_render as skill_html_render
    _IMPORT_SUCCESS = True
except ImportError as e:
    logger.warning(f"Gagal mengimpor last30days-skill library secara in-process: {e}")
    _IMPORT_SUCCESS = False


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "last30days"


class Last30DaysResearchInput(BaseModel):
    topic: str = Field(..., description="Topik atau kata kunci pencarian yang ingin diriset di Reddit, X, HN, dll.")
    quick: bool = Field(True, description="Gunakan mode pencarian cepat (mengurangi pemanggilan API / delay).")
    days: int = Field(30, description="Rentang hari ke belakang untuk pencarian data (default: 30).")
    x_handle: Optional[str] = Field(None, description="Username X/Twitter target (tanpa @) jika riset spesifik ke orang/brand.")
    github_user: Optional[str] = Field(None, description="Username GitHub target jika riset spesifik ke developer/organisasi.")
    subreddits: Optional[str] = Field(None, description="Daftar subreddit dipisahkan koma untuk membatasi pencarian Reddit.")
    mock: bool = Field(False, description="Set ke True untuk simulasi (mock fixtures) demi pengujian terisolasi.")


class Last30DaysResearchTool(BaseTool):
    name: str = "Last 30 Days Research Tool"
    description: str = (
        "Riset lintas platform (Reddit, X, YouTube, Hacker News, Polymarket, GitHub, web) "
        "mengenai sentimen, opini komunitas, perbandingan produk (vs), dan tren terbaru dalam 30 hari terakhir. "
        "Tool ini akan mengembalikan ringkasan riset berformat Markdown, dan otomatis menulis "
        "laporan visual berupa berkas HTML interaktif yang siap dikirimkan ke pengguna. "
        "Input: topic (str) + parameter opsional (quick, days, x_handle, github_user, subreddits, mock)."
    )
    args_schema: type[BaseModel] = Last30DaysResearchInput

    def _run(
        self,
        topic: str,
        quick: bool = True,
        days: int = 30,
        x_handle: Optional[str] = None,
        github_user: Optional[str] = None,
        subreddits: Optional[str] = None,
        mock: bool = False
    ) -> str:
        topic = (topic or "").strip()
        if not topic:
            return "FAILED|Topic kosong"

        if not _IMPORT_SUCCESS:
            return "FAILED|Library last30days-skill gagal di-import. Pastikan repository berada di tools/last30days-skill"

        logger.info(f"[LAST30DAYS] Memulai riset topik '{topic}' (quick={quick}, days={days}, mock={mock})")

        # Muat konfigurasi dasar engine
        try:
            config = skill_env.get_config()
        except Exception as e:
            logger.error(f"[LAST30DAYS] Gagal memuat config: {e}")
            config = {}

        # Parse subreddits & x_handle jika disuplai
        parsed_subreddits = None
        if subreddits:
            parsed_subreddits = [s.strip().removeprefix("r/") for s in subreddits.split(",") if s.strip()]

        clean_x_handle = x_handle.lstrip("@") if x_handle else None
        clean_github_user = github_user.lstrip("@").lower() if github_user else None

        depth = "quick" if quick else "default"

        try:
            # Jalankan pipeline riset secara in-process
            report = skill_pipeline.run(
                topic=topic,
                config=config,
                depth=depth,
                mock=mock,
                x_handle=clean_x_handle,
                github_user=clean_github_user,
                subreddits=parsed_subreddits,
                lookback_days=days,
            )

            # 1. Render ringkasan compact markdown
            compact_md = skill_render.render_compact(report)

            # 2. Render HTML brief visual dan simpan ke outputs/last30days/
            html_content = skill_html_render.render_html(report)
            slug = slugify(topic)
            ts = int(time.time())
            html_filename = f"{slug}_brief_{ts}.html"
            html_file = _OUTPUT_DIR / html_filename
            html_file.write_text(html_content, encoding="utf-8")

            logger.info(f"[LAST30DAYS] Riset selesai. HTML brief disimpan di: {html_file}")
            
            # Kita format output agar downstream node / bot bisa mengekstrak path HTML brief
            # format: SUCCESS|<html_filepath>|<compact_markdown>
            return f"SUCCESS|{html_file}|{compact_md}"

        except Exception as e:
            logger.exception(f"[LAST30DAYS] Terjadi kesalahan saat menjalankan riset: {e}")
            return f"FAILED|Kesalahan internal riset: {e}"
