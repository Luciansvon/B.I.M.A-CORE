import json
import logging
from pathlib import Path

logger = logging.getLogger('bima_core')

_STYLES_PATH = Path(__file__).parent / "document_styles.json"

# Dipakai kalau document_styles.json hilang/corrupt -- bot tetap jalan dengan 1 preset darurat
_FALLBACK_STYLES = {
    "formal": {
        "title_rgb": (43, 74, 138), "accent_rgb": (43, 74, 138),
        "table_header_rgb": (43, 74, 138), "table_alt_rgb": (238, 242, 255),
        "title_size": 18, "body_size": 10, "heading_size": 13,
        "tone": "Baku, resmi, struktur kaku.", "label": "FORMAL",
        "font_family": "Calibri", "pdf_font": "Helvetica",
        "line_spacing": 1.15, "justify": False,
        "margins_cm": {"top": 2.54, "bottom": 2.54, "left": 2.54, "right": 2.54},
    },
}


def _load_styles() -> dict:
    try:
        with open(_STYLES_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        styles = {}
        for name, cfg in raw.items():
            cfg = dict(cfg)
            for key in ("title_rgb", "accent_rgb", "table_header_rgb", "table_alt_rgb"):
                if key in cfg:
                    cfg[key] = tuple(cfg[key])
            styles[name] = cfg
        if not styles:
            raise ValueError("document_styles.json kosong")
        return styles
    except Exception as e:
        logger.error(f"[ADMIN] Gagal load {_STYLES_PATH.name}, pakai fallback darurat: {e}")
        return _FALLBACK_STYLES


STYLES = _load_styles()
DEFAULT_STYLE_NAME = "formal" if "formal" in STYLES else next(iter(STYLES))


def resolve_style(data: dict) -> dict:
    """Ambil style dict dari field 'style' pada JSON input tool. Fallback ke default kalau nama gak dikenal."""
    style_name = data.get("style", DEFAULT_STYLE_NAME)
    return STYLES.get(style_name, STYLES[DEFAULT_STYLE_NAME])


def _hex_from_rgb(rgb: tuple) -> str:
    return "{:02X}{:02X}{:02X}".format(*rgb)


def detect_style(text: str) -> str:
    """Tebakan awal gaya tulisan dari kata kunci literal di permintaan user.
    Ini FALLBACK, bukan keputusan final -- admin_agent (LLM) diinstruksikan
    memprioritaskan penalaran atas konteks penuh (histori, data, tim sebelumnya)
    dan cuma pakai ini kalau dia ragu. Lihat core/langgraph_nodes/admin.py."""
    t = (text or "").lower()
    if any(k in t for k in ["skripsi", "tugas akhir", "tesis", "disertasi", "jurnal ilmiah",
                             "akademik", "academic", "thesis", "makalah", "karya ilmiah"]):
        return "akademik"
    if any(k in t for k in ["santai", "casual", "blog", "newsletter", "ngobrol", "ramah",
                             "asik", "ringan", "kreatif", "naratif", "cerita", "story",
                             "esai", "puisi", "creative", "novel"]):
        return "informal"
    if any(k in t for k in ["tutorial", "panduan", "lesson", "edukasi", "ajar", "pemula",
                             "step", "belajar", "teknis", "technical", "dokumentasi",
                             "spek", "api", "manual", "code", "kode"]):
        return "semi_formal"
    if any(k in t for k in ["formal", "resmi", "profesional", "kontrak", "proposal", "baku",
                             "perusahaan", "bisnis", "surat dinas", "laporan resmi"]):
        return "formal"
    return DEFAULT_STYLE_NAME


def detect_format(text: str) -> str:
    """Auto-detect format dokumen yang diminta (pdf / word / excel)."""
    t = (text or "").lower()
    if any(k in t for k in ["excel", "xlsx", "spreadsheet", "tabel data", "rekap"]):
        return "excel"
    if any(k in t for k in [".docx", "word", "dokumen word"]):
        return "word"
    return "pdf"  # default
