"""SherlockTool — OSINT username scanner across 400+ sosmed platforms.

Pakai CLI `sherlock-project` (pip install sherlock-project) via subprocess.
Return summary list akun yang ditemukan + URL-nya.

Note: scan bisa makan 30-90 detik (paralel HTTP ke ratusan situs). Set timeout
default 90s, kalau timeout return partial result yang udah keburu di-scan.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from crewai.tools import BaseTool

logger = logging.getLogger("bima_core")


class SherlockTool(BaseTool):
    name: str = "Sherlock Username Scanner"
    description: str = (
        "OSINT: cek satu username terdaftar di sosmed mana aja (Twitter/X, Instagram, "
        "Reddit, GitHub, TikTok, Telegram, dll — total 400+ situs). "
        "Input: username (huruf, angka, underscore, dot). Contoh: 'luciansvon', 'bimacore'. "
        "Output: SUCCESS|<count_found>|<list akun dengan URL>, atau FAILED|<error>."
    )

    def _run(self, username: str) -> str:
        raw_username = (username or "").strip()
        username = raw_username.split()[0] if raw_username else ""
        username = re.sub(r"[^A-Za-z0-9._-]", "", username)[:40]
        if not username:
            return "FAILED|Username kosong / cuma karakter terlarang"

        sherlock_bin = shutil.which("sherlock")
        if not sherlock_bin:
            return "FAILED|sherlock CLI gak ada di PATH — pip install sherlock-project"

        # Output ke temp dir biar gampang cleanup
        with tempfile.TemporaryDirectory(prefix="sherlock_") as tmpdir:
            try:
                # --print-found = cuma print akun yang FOUND (skip "not found")
                # --timeout 8 per-site timeout (default 60 kelamaan)
                # --folderoutput hasil text file per username
                proc = subprocess.run(
                    [sherlock_bin, username,
                     "--print-found",
                     "--timeout", "8",
                     "--folderoutput", tmpdir,
                     "--no-color"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except subprocess.TimeoutExpired:
                return f"FAILED|Sherlock timeout (>120s) buat '{username}'"
            except Exception as e:
                logger.exception("[SHERLOCK] Subprocess error")
                return f"FAILED|Sherlock subprocess error: {e}"

            # Parse stdout — format per line: "[+] SiteName: URL"
            found: list[str] = []
            for line in (proc.stdout or "").splitlines():
                line = line.strip()
                if line.startswith("[+]"):
                    # "[+] GitHub: https://github.com/luciansvon"
                    found.append(line[3:].strip())

            count = len(found)
            if count == 0:
                msg = (proc.stdout or proc.stderr or "").strip()[:200]
                return f"FAILED|Gak ada akun ditemukan untuk '{username}' (atau semua situs error). Sample output: {msg}"

            # Truncate kalau kebanyakan
            top = found[:30]
            extra = f" (+{count - 30} lagi, total {count})" if count > 30 else ""
            joined = "\n".join(f"  - {x}" for x in top)
            return (
                f"SUCCESS|{count}|"
                f"Ditemukan {count} akun pakai username '{username}'{extra}:\n{joined}"
            )
