"""
B.I.M.A Core — Smart File Organizer
Otomatis merapikan folder outputs/ berdasarkan tipe dan tanggal.

Jalankan manual:  python file_organizer.py
Atau via cron:    crontab -e → 0 0 * * * cd /home/bima_lucian/BIMA_CORE && python3 tools/file_organizer.py
"""
import logging
import shutil
import time
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
MIN_FILE_AGE_SECONDS = 300
logger = logging.getLogger("bima_core.file_organizer")

# Mapping ekstensi ke kategori folder
CATEGORIES = {
    ".html": "dashboards",
    ".pdf": "reports",
    ".xlsx": "spreadsheets",
    ".docx": "documents",
    ".csv": "spreadsheets",
    ".svg": "graphics",
    ".png": "images",
    ".jpg": "images",
    ".jpeg": "images",
    ".py": "scripts",
    ".txt": "notes",
}

# File yang TIDAK boleh dipindah
SKIP_FILES = {"pet_event.json"}

def organize() -> dict[str, int]:
    if not OUTPUT_DIR.exists():
        print("❌ Folder outputs/ tidak ditemukan!")
        return {"moved": 0, "skipped": 0, "errors": 0}

    moved = 0
    skipped = 0
    errors = 0
    now = time.time()

    for f in sorted(OUTPUT_DIR.iterdir()):
        try:
            if not f.is_file():
                continue
            if f.name in SKIP_FILES:
                skipped += 1
                continue

            stat = f.stat()
            if now - stat.st_mtime < MIN_FILE_AGE_SECONDS:
                skipped += 1
                continue

            ext = f.suffix.lower()
            category = CATEGORIES.get(ext, "others")
            mtime = datetime.fromtimestamp(stat.st_mtime)
            date_folder = mtime.strftime("%Y-%m-%d")

            dest_dir = OUTPUT_DIR / date_folder / category
            dest_dir.mkdir(parents=True, exist_ok=True)

            dest_path = dest_dir / f.name
            if dest_path.exists():
                dest_path = dest_dir / f"{f.stem}_{time.time_ns()}{ext}"

            shutil.move(str(f), str(dest_path))
            print(f"  📂 {f.name} → {date_folder}/{category}/")
            moved += 1
        except Exception:
            errors += 1
            logger.exception("Gagal mengorganisasi output %s", f)

    print(
        f"\n✅ Selesai! {moved} file dirapikan, {skipped} file di-skip, "
        f"{errors} error."
    )
    return {"moved": moved, "skipped": skipped, "errors": errors}

if __name__ == "__main__":
    print("🧹 B.I.M.A Core — Smart File Organizer")
    print(f"   Target: {OUTPUT_DIR}\n")
    organize()
