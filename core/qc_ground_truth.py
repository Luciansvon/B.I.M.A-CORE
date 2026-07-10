"""Ground-truth extractor untuk QC gambar kerja.

Nyediain fakta deterministik ke Checker Agent (VLM) supaya dia tinggal
mencocokkan logika, bukan nebak-nebak baca teks blur:

1. Teks native PDF (pdfplumber) — cuma PDF vektor.
2. Tabel terdeteksi (pdfplumber.extract_tables) — kandidat tabel BOM.
3. Fallback OCR RapidOCR (model PaddleOCR via ONNX, sudah terinstal) untuk
   scan/raster & teks miring — dipakai kalau teks native gak ada.

Semua fungsi sync — caller offload via asyncio.to_thread.
"""
import base64
import logging
import threading
from io import BytesIO

logger = logging.getLogger("bima_core.qc_ground_truth")

# Cap output supaya prompt gak bengkak
_MAX_TABLE_ROWS = 40
_MAX_TABLE_CHARS = 2500
_MAX_OCR_LINES = 60
_MIN_OCR_SCORE = 0.5
_MAX_TOTAL_CHARS = 6000

_ocr_engine = None
_ocr_engine_failed = False
_ocr_lock = threading.Lock()


def extract_pdf_page_text(pdf_bytes: bytes, page_num: int) -> str | None:
    """Coba extract text native dari halaman PDF menggunakan pdfplumber.

    Cuma dapet hasil kalau PDF-nya berbasis vektor (bukan raster scan).
    """
    import pdfplumber
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            if page_num - 1 < len(pdf.pages):
                page = pdf.pages[page_num - 1]
                text = page.extract_text()
                if text and text.strip():
                    return text.strip()
    except Exception as e:
        logger.debug(f"[qc-gt] pdfplumber extract failed for page {page_num}: {e}")
    return None


def format_tables(tables: list[list[list[str | None]]]) -> str | None:
    """Format hasil extract_tables → teks pipe-table ringkas. None kalau kosong."""
    lines: list[str] = []
    row_budget = _MAX_TABLE_ROWS
    for t_idx, table in enumerate(tables, start=1):
        rows = [
            r for r in table
            if r and any(cell and str(cell).strip() for cell in r)
        ]
        if not rows:
            continue
        lines.append(f"[Tabel {t_idx}]")
        for row in rows[:row_budget]:
            cells = [str(c).strip().replace("\n", " ") if c else "" for c in row]
            lines.append("| " + " | ".join(cells) + " |")
        row_budget -= min(len(rows), row_budget)
        if row_budget <= 0:
            lines.append("... (tabel selanjutnya dipotong)")
            break
    if not lines:
        return None
    text = "\n".join(lines)
    if len(text) > _MAX_TABLE_CHARS:
        text = text[:_MAX_TABLE_CHARS] + "\n... (dipotong)"
    return text


def extract_pdf_page_tables(pdf_bytes: bytes, page_num: int) -> str | None:
    """Deteksi tabel (kandidat BOM) di halaman PDF vektor via pdfplumber."""
    import pdfplumber
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            if page_num - 1 >= len(pdf.pages):
                return None
            tables = pdf.pages[page_num - 1].extract_tables()
            if not tables:
                return None
            return format_tables(tables)
    except Exception as e:
        logger.debug(f"[qc-gt] pdfplumber tables failed for page {page_num}: {e}")
    return None


def _get_rapidocr():
    """Lazy singleton RapidOCR (load model ONNX sekali). None kalau init gagal."""
    global _ocr_engine, _ocr_engine_failed
    if _ocr_engine is not None or _ocr_engine_failed:
        return _ocr_engine
    with _ocr_lock:
        if _ocr_engine is not None or _ocr_engine_failed:
            return _ocr_engine
        try:
            from rapidocr import RapidOCR  # heavy import, lazy
            logger.info("[qc-gt] init RapidOCR engine (PaddleOCR/ONNX) — first call only")
            _ocr_engine = RapidOCR()
        except Exception as e:
            _ocr_engine_failed = True
            logger.warning(f"[qc-gt] RapidOCR init gagal, OCR fallback dimatikan: {e}")
    return _ocr_engine


def _ocr_lines(result: object) -> list[str]:
    """Normalisasi output RapidOCR (v3 object-style / legacy tuple-style) → list text."""
    txts = getattr(result, "txts", None)
    scores = getattr(result, "scores", None)
    if txts is not None:
        if scores is None:
            scores = [1.0] * len(txts)
        return [
            str(t).strip()
            for t, s in zip(txts, scores)
            if t and str(t).strip() and (s is None or float(s) >= _MIN_OCR_SCORE)
        ]
    # Legacy: (list [[box, text, score], ...], elapse)
    if isinstance(result, tuple) and result and isinstance(result[0], list):
        return [
            str(item[1]).strip()
            for item in result[0]
            if len(item) >= 3 and str(item[1]).strip() and float(item[2]) >= _MIN_OCR_SCORE
        ]
    return []


def ocr_image_b64(img_b64: str) -> str | None:
    """OCR image base64 (crop kop/BOM) via RapidOCR. Handle teks miring/rotasi."""
    engine = _get_rapidocr()
    if engine is None:
        return None
    try:
        import cv2
        import numpy as np
        arr = np.frombuffer(base64.b64decode(img_b64), dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        result = engine(img)
        lines = _ocr_lines(result)[:_MAX_OCR_LINES]
        return "\n".join(lines) if lines else None
    except Exception as e:
        logger.debug(f"[qc-gt] RapidOCR run gagal: {e}")
        return None


def build_page_ground_truth(
    pdf_bytes: bytes | None, page_num: int, crop_b64: str | None
) -> str | None:
    """Rakit blok ground truth 1 halaman untuk prompt Checker Agent.

    Urutan preferensi: teks native PDF (paling akurat) + tabel pdfplumber.
    Kalau dua-duanya kosong (scan/raster atau input image) → OCR RapidOCR
    pada crop area kop/BOM.
    """
    parts: list[str] = []

    if pdf_bytes is not None:
        text = extract_pdf_page_text(pdf_bytes, page_num)
        if text:
            parts.append(f"[TEKS NATIVE PDF]\n{text}")
        tables = extract_pdf_page_tables(pdf_bytes, page_num)
        if tables:
            parts.append(f"[TABEL TERDETEKSI — KANDIDAT BOM]\n{tables}")

    if not parts and crop_b64:
        ocr_text = ocr_image_b64(crop_b64)
        if ocr_text:
            parts.append(
                f"[OCR AREA KOP/BOM (RapidOCR — termasuk teks miring/rotasi)]\n{ocr_text}"
            )

    if not parts:
        return None
    combined = "\n\n".join(parts)
    if len(combined) > _MAX_TOTAL_CHARS:
        combined = combined[:_MAX_TOTAL_CHARS] + "\n... (dipotong)"
    return combined
