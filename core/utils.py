import re
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ============================================================
# WAKTU REAL-TIME WIB
# ============================================================
def get_waktu() -> str:
    wib = timezone(timedelta(hours=7))
    now = datetime.now(wib)
    hari = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"][now.weekday()]
    bulan = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"][now.month-1]
    return f"{hari}, {now.day} {bulan} {now.year} pukul {now.strftime('%H:%M')} WIB"

# ============================================================
# EXTRACT FILE OUTPUT
# ============================================================
logger = logging.getLogger('bima_core')

def extract_output_files(hasil_str: str) -> list:
    pattern = r'SUCCESS\|([^\| \n\r]+)'
    matches = re.findall(pattern, hasil_str)
    valid = []
    for m in matches:
        p = Path(m.strip())
        if not p.exists():
            logger.warning(f"[UTILS] File tidak ditemukan: {p}")
            continue
        if p.name.startswith("tmp"):
            continue
        if p.stat().st_size < 100:
            logger.warning(f"[UTILS] File terlalu kecil ({p.stat().st_size} bytes): {p}")
            continue
        valid.append(p)
        logger.info(f"[UTILS] File valid ditemukan: {p}")
    return valid

# ============================================================
# SMART CHUNKING
# ============================================================
def smart_chunks(text, limit=1900):
    """Split text for Discord (max 2000 chars) while preserving markdown code blocks.
    Kalau terpaksa split di tengah code block, tutup ``` dulu lalu buka lagi di chunk berikutnya.
    """
    res, cur = [], ""
    in_code = False
    code_lang = ""  # track language (```python, ```json, dll)
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_code:
                in_code = True
                # Capture language tag (e.g. "python" dari "```python")
                code_lang = stripped[3:].strip()
            else:
                in_code = False
                code_lang = ""
        if len(cur) + len(line) > limit and cur:
            if in_code:
                # Tutup code block sebelum split
                cur += "\n```\n"
            res.append(cur)
            if in_code:
                # Buka ulang code block di chunk baru
                cur = f"```{code_lang}\n{line}"
            else:
                cur = line
        else:
            cur += line
    if cur:
        res.append(cur)
    return res if res else [text[:limit]]
