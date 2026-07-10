"""Unit tests untuk core/qc_ground_truth.py — ground truth QC (teks/tabel/OCR).

Jalankan: pytest tests/test_qc_ground_truth.py -v
Semua offline: PDF sintetis via fitz, RapidOCR di-mock (gak load model).
"""
import base64
from io import BytesIO
from types import SimpleNamespace

import fitz
from PIL import Image

from core import qc_ground_truth
from core.qc_ground_truth import (
    _ocr_lines,
    build_page_ground_truth,
    extract_pdf_page_text,
    format_tables,
)


def _text_pdf(text: str = "DIMENSI: 600 x 400 mm") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=14)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _blank_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _tiny_png_b64() -> str:
    img = Image.new("RGB", (16, 16), (255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class TestExtractPdfPageText:
    def test_vector_pdf(self):
        assert "600" in (extract_pdf_page_text(_text_pdf(), 1) or "")

    def test_invalid_bytes_returns_none(self):
        assert extract_pdf_page_text(b"not a pdf", 1) is None

    def test_out_of_range_page_returns_none(self):
        assert extract_pdf_page_text(_blank_pdf(), 99) is None


class TestFormatTables:
    def test_basic_pipe_format(self):
        tables = [[["Part", "W", "H"], ["Top", "600", "400"], [None, None, None]]]
        out = format_tables(tables)
        assert out is not None
        assert "[Tabel 1]" in out
        assert "| Part | W | H |" in out
        assert "| Top | 600 | 400 |" in out
        # Baris full-empty di-skip
        assert "|  |  |  |" not in out

    def test_newline_in_cell_flattened(self):
        out = format_tables([[["Top\nPanel", "600"]]])
        assert out is not None
        assert "Top Panel" in out

    def test_empty_returns_none(self):
        assert format_tables([]) is None
        assert format_tables([[[None, None]]]) is None

    def test_row_budget_cap(self):
        big = [[[f"r{i}", "x"] for i in range(200)]]
        out = format_tables(big)
        assert out is not None
        assert out.count("\n") < 250  # kena cap rows/chars, gak dump 200 baris utuh


class TestOcrLines:
    def test_v3_object_format_with_score_filter(self):
        res = SimpleNamespace(txts=("600 x 400", "blur??", ""), scores=(0.95, 0.3, 0.9))
        assert _ocr_lines(res) == ["600 x 400"]

    def test_v3_object_without_scores(self):
        res = SimpleNamespace(txts=("A", " B "), scores=None)
        assert _ocr_lines(res) == ["A", "B"]

    def test_legacy_tuple_format(self):
        legacy = ([[None, "PANEL ATAS", 0.9], [None, "noise", 0.2]], 0.5)
        assert _ocr_lines(legacy) == ["PANEL ATAS"]

    def test_unknown_shape_returns_empty(self):
        assert _ocr_lines(None) == []
        assert _ocr_lines("aneh") == []


class TestBuildPageGroundTruth:
    def test_vector_pdf_includes_native_text(self):
        out = build_page_ground_truth(_text_pdf(), 1, None)
        assert out is not None
        assert "[TEKS NATIVE PDF]" in out
        assert "600" in out

    def test_nothing_available_returns_none(self, monkeypatch):
        monkeypatch.setattr(qc_ground_truth, "_get_rapidocr", lambda: None)
        assert build_page_ground_truth(None, 1, None) is None
        assert build_page_ground_truth(_blank_pdf(), 1, None) is None

    def test_blank_pdf_falls_back_to_ocr_crop(self, monkeypatch):
        fake_engine = lambda img: SimpleNamespace(txts=("KOP: JM-024",), scores=(0.9,))
        monkeypatch.setattr(qc_ground_truth, "_get_rapidocr", lambda: fake_engine)
        out = build_page_ground_truth(_blank_pdf(), 1, _tiny_png_b64())
        assert out is not None
        assert "[OCR AREA KOP/BOM" in out
        assert "JM-024" in out

    def test_image_input_uses_ocr(self, monkeypatch):
        """Input image (pdf_bytes=None) + crop → jalan lewat OCR."""
        fake_engine = lambda img: SimpleNamespace(txts=("600",), scores=(0.9,))
        monkeypatch.setattr(qc_ground_truth, "_get_rapidocr", lambda: fake_engine)
        out = build_page_ground_truth(None, 1, _tiny_png_b64())
        assert out is not None and "600" in out

    def test_native_text_skips_ocr(self, monkeypatch):
        """Kalau teks native ada, OCR gak boleh dipanggil (hemat CPU)."""
        def _boom():
            raise AssertionError("OCR tidak boleh dipanggil kalau native text ada")
        monkeypatch.setattr(qc_ground_truth, "_get_rapidocr", _boom)
        out = build_page_ground_truth(_text_pdf(), 1, _tiny_png_b64())
        assert out is not None and "[TEKS NATIVE PDF]" in out

    def test_ocr_engine_failure_graceful(self, monkeypatch):
        monkeypatch.setattr(qc_ground_truth, "_get_rapidocr", lambda: None)
        out = build_page_ground_truth(None, 1, _tiny_png_b64())
        assert out is None

    def test_total_length_capped(self):
        out = build_page_ground_truth(_text_pdf("X " * 9000), 1, None)
        assert out is not None
        assert len(out) <= qc_ground_truth._MAX_TOTAL_CHARS + 50
