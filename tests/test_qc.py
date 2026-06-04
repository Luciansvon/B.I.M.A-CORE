"""Unit tests untuk furniture_qc.py dan cutlist.py.

Jalankan: pytest tests/test_qc.py -v
(atau: python -m pytest tests/test_qc.py -v)

Tidak butuh API call — semua test offline pakai sample data.
"""
import json
import pytest
from io import BytesIO
from PIL import Image

# ============================================================
# 1. Pydantic Models
# ============================================================

from core.furniture_qc import (
    QCIssue,
    QCResult,
    TitleBlock,
    BomPart,
    QCDiffChange,
    QCDiffResult,
    format_result_for_discord,
    format_diff_for_discord,
    _estimate_cost_from_bom,
    _resolve_material_price,
    _safe_json_loads,
    _MATERIAL_PRICES_PER_M2,
)

from core.cutlist import (
    parse_cutlist_input,
    solve_cutlist_full,
    CutPart,
    DEFAULT_PANEL,
)


# --- QCIssue severity normalization ---

class TestQCIssueSeverity:
    def test_standard_severities(self):
        for sev in ("critical", "warning", "info"):
            issue = QCIssue(severity=sev, category="dimensi", location="atas", issue="test")
            assert issue.severity == sev

    def test_normalize_critical_variants(self):
        for alias in ("crit", "error", "high", "blocker", "CRITICAL", "  High  "):
            issue = QCIssue(severity=alias, category="dimensi", location="atas", issue="test")
            assert issue.severity == "critical", f"{alias!r} harus jadi 'critical'"

    def test_normalize_warning_variants(self):
        for alias in ("warn", "medium", "moderate", "WARNING", "  Warn "):
            issue = QCIssue(severity=alias, category="dimensi", location="atas", issue="test")
            assert issue.severity == "warning", f"{alias!r} harus jadi 'warning'"

    def test_unknown_severity_defaults_to_info(self):
        for alias in ("low", "note", "suggestion", "unknown", "xyz"):
            issue = QCIssue(severity=alias, category="dimensi", location="atas", issue="test")
            assert issue.severity == "info", f"{alias!r} harus fallback ke 'info'"


# --- QCResult from sample JSON ---

class TestQCResult:
    SAMPLE_JSON = {
        "overall_verdict": "needs_revision",
        "summary": "Ada 2 issue dimensi",
        "issues": [
            {
                "severity": "critical",
                "category": "dimensi",
                "location": "panel atas",
                "issue": "dimensi panjang tidak ada",
                "suggestion": "tambahkan dimensi",
                "page": 1,
                "bbox": [0.1, 0.2, 0.5, 0.6],
            },
            {
                "severity": "info",
                "category": "material",
                "location": "global",
                "issue": "material tidak disebutkan",
                "page": 1,
                "bbox": None,
            },
        ],
        "praise": ["Drawing rapi"],
        "title_block": {
            "drawing_number": "JM-024",
            "title": "Lemari Pakaian",
            "revision": "Rev.1",
            "scale": "1:20",
            "author": "Bima",
            "date": "2026-05-01",
        },
        "bom": [
            {"name": "top", "width": 600, "height": 400, "thickness": 18, "qty": 2, "material": "plywood_18mm"},
            {"name": "side", "width": 800, "height": 300, "thickness": 18, "qty": 4, "material": "plywood_18mm"},
        ],
    }

    def test_parse_full_result(self):
        result = QCResult(**self.SAMPLE_JSON)
        assert result.overall_verdict == "needs_revision"
        assert len(result.issues) == 2
        assert result.issues[0].severity == "critical"
        assert result.issues[1].bbox is None
        assert result.title_block is not None
        assert result.title_block.drawing_number == "JM-024"
        assert len(result.bom) == 2

    def test_minimal_result(self):
        result = QCResult(overall_verdict="approved", summary="OK")
        assert result.issues == []
        assert result.praise == []
        assert result.title_block is None
        assert result.bom == []

    def test_severity_normalized_in_result(self):
        data = dict(self.SAMPLE_JSON)
        data["issues"] = [
            {"severity": "high", "category": "dimensi", "location": "bawah", "issue": "missing"},
        ]
        result = QCResult(**data)
        assert result.issues[0].severity == "critical"


# --- QCDiffResult ---

class TestQCDiffResult:
    def test_parse_diff_result(self):
        data = {
            "summary": "Perubahan dimensi panel",
            "overall_change_level": "major",
            "rev_a_pages": 2,
            "rev_b_pages": 3,
            "changes": [
                {"severity": "major", "category": "dimensi", "page_a": 1, "page_b": 1, "what_changed": "lebar 600→650"},
                {"severity": "minor", "category": "label", "page_a": 2, "page_b": 2, "what_changed": "typo title"},
            ],
        }
        result = QCDiffResult(**data)
        assert result.overall_change_level == "major"
        assert len(result.changes) == 2


# ============================================================
# 2. Format Functions
# ============================================================

class TestFormatResultForDiscord:
    def test_approved_no_issues(self):
        result = QCResult(overall_verdict="approved", summary="Semua OK")
        text = format_result_for_discord(result)
        assert "✅" in text
        assert "APPROVED" in text
        assert "Ga ada issue" in text

    def test_with_issues_grouped_by_severity(self):
        result = QCResult(
            overall_verdict="needs_revision",
            summary="Ada masalah",
            issues=[
                QCIssue(severity="critical", category="dimensi", location="atas", issue="missing dim"),
                QCIssue(severity="warning", category="view", location="samping", issue="kurang view"),
                QCIssue(severity="info", category="material", location="global", issue="saran"),
            ],
        )
        text = format_result_for_discord(result)
        assert "🚨 Critical (1)" in text
        assert "⚠️ Warning (1)" in text
        assert "💡 Info (1)" in text

    def test_bom_section_rendered(self):
        result = QCResult(
            overall_verdict="approved",
            summary="OK",
            bom=[BomPart(name="top", width=600, height=400, thickness=18, qty=2, material="plywood_18mm")],
        )
        text = format_result_for_discord(result)
        assert "📦 BOM" in text
        assert "top" in text
        assert "cutlist last" in text.lower()


class TestFormatDiffForDiscord:
    def test_no_changes(self):
        result = QCDiffResult(summary="Sama", overall_change_level="minor")
        text = format_diff_for_discord(result, "a.pdf", "b.pdf")
        assert "Gak ada perubahan" in text

    def test_with_changes(self):
        result = QCDiffResult(
            summary="Dimensi berubah",
            overall_change_level="major",
            rev_a_pages=1,
            rev_b_pages=1,
            changes=[QCDiffChange(severity="major", category="dimensi", page_a=1, page_b=1, what_changed="600→700")],
        )
        text = format_diff_for_discord(result, "old.pdf", "new.pdf")
        assert "🚨" in text
        assert "Major" in text
        assert "600→700" in text


# ============================================================
# 3. Cost Estimation + Material Fuzzy Matching
# ============================================================

class TestMaterialPricing:
    def test_exact_match(self):
        price = _resolve_material_price("plywood_18mm")
        assert price == _MATERIAL_PRICES_PER_M2["plywood_18mm"]

    def test_fuzzy_plywood(self):
        """'plywood' tanpa suffix harus resolve ke plywood_18mm, bukan fallback 'other'."""
        price = _resolve_material_price("plywood")
        assert price == _MATERIAL_PRICES_PER_M2["plywood_18mm"]

    def test_fuzzy_mdf(self):
        price = _resolve_material_price("mdf")
        assert price == _MATERIAL_PRICES_PER_M2["mdf_18mm"]

    def test_fuzzy_multiplex(self):
        price = _resolve_material_price("multiplex")
        assert price == _MATERIAL_PRICES_PER_M2["plywood_18mm"]

    def test_fuzzy_kayu(self):
        price = _resolve_material_price("kayu")
        assert price == _MATERIAL_PRICES_PER_M2["solid_jati"]

    def test_unknown_fallback(self):
        price = _resolve_material_price("baja_ringan")
        assert price == _MATERIAL_PRICES_PER_M2.get("other", 100000.0)

    def test_estimate_cost_basic(self):
        bom = [BomPart(name="top", width=1000, height=500, thickness=18, qty=2, material="plywood_18mm")]
        cost = _estimate_cost_from_bom(bom)
        # 1000×500mm = 0.5 m² × 2 = 1.0 m² × 120000 = 120000
        assert cost["total_area_m2"] == pytest.approx(1.0)
        assert cost["total_idr"] == pytest.approx(120000.0)

    def test_estimate_cost_fuzzy_material(self):
        """BOM dengan material='plywood' harus pakai harga plywood_18mm, bukan 'other'."""
        bom = [BomPart(name="panel", width=1000, height=1000, thickness=18, qty=1, material="plywood")]
        cost = _estimate_cost_from_bom(bom)
        expected_price = _MATERIAL_PRICES_PER_M2["plywood_18mm"]
        assert cost["total_idr"] == pytest.approx(expected_price)

    def test_estimate_cost_skip_invalid(self):
        bom = [
            BomPart(name="zero", width=0, height=500, qty=1),
            BomPart(name="valid", width=1000, height=1000, qty=1, material="other"),
        ]
        cost = _estimate_cost_from_bom(bom)
        assert cost["total_area_m2"] == pytest.approx(1.0)
        assert len(cost["breakdown"]) == 1


# ============================================================
# 4. Safe JSON Loading
# ============================================================

class TestSafeJsonLoads:
    def test_clean_json(self):
        data = _safe_json_loads('{"key": "value"}')
        assert data == {"key": "value"}

    def test_markdown_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        data = _safe_json_loads(raw)
        assert data == {"key": "value"}

    def test_trailing_text(self):
        raw = '{"key": "value"}\n\nSome trailing explanation.'
        data = _safe_json_loads(raw)
        assert data == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="JSON invalid"):
            _safe_json_loads("this is not json at all")

    def test_nested_json_extracted(self):
        raw = 'Here is the result:\n{"overall_verdict": "approved", "summary": "ok"}\nDone.'
        data = _safe_json_loads(raw)
        assert data["overall_verdict"] == "approved"


# ============================================================
# 5. Cutlist Parser + Validation
# ============================================================

class TestCutlistParser:
    def test_basic_parse(self):
        text = "top 600x400 x2\nside 800x300 x4"
        panel, parts = parse_cutlist_input(text)
        assert panel == DEFAULT_PANEL
        assert len(parts) == 2
        assert parts[0].name == "top"
        assert parts[0].width == 600
        assert parts[0].height == 400
        assert parts[0].qty == 2
        assert parts[1].qty == 4

    def test_custom_panel(self):
        text = "panel: 3000x1500\ntop 600x400"
        panel, parts = parse_cutlist_input(text)
        assert panel == (3000.0, 1500.0)

    def test_default_qty_is_1(self):
        text = "shelf 500x300"
        _, parts = parse_cutlist_input(text)
        assert parts[0].qty == 1

    def test_no_parts_raises(self):
        with pytest.raises(ValueError, match="Gak ada parts"):
            parse_cutlist_input("# just a comment\n")

    def test_width_too_big_raises(self):
        """Part yang width DAN height lebih besar dari panel harus error."""
        with pytest.raises(ValueError, match="gak akan muat"):
            parse_cutlist_input("huge 5000x3000", default_panel=(2440, 1220))

    def test_height_too_big_raises(self):
        """Part yang height lebih besar dari panel (rotation tetap gak muat) harus error."""
        with pytest.raises(ValueError, match="gak akan muat"):
            parse_cutlist_input("tall 100x3000", default_panel=(2440, 1220))

    def test_rotatable_part_passes(self):
        """Part 1300x100 bisa muat di 2440x1220 (tanpa rotasi). Harus OK."""
        _, parts = parse_cutlist_input("bar 1300x100", default_panel=(2440, 1220))
        assert len(parts) == 1

    def test_skip_zero_dimensions(self):
        text = "bad 0x500\ngood 600x400"
        _, parts = parse_cutlist_input(text)
        assert len(parts) == 1
        assert parts[0].name == "good"


class TestCutlistSolver:
    def test_solve_basic(self):
        parts = [CutPart(name="a", width=600, height=400, qty=4)]
        out = solve_cutlist_full((2440, 1220), parts)
        assert out.sheets_count >= 1
        assert out.efficiency_pct > 0
        assert "Cutting List" in out.text

    def test_solve_single_part(self):
        parts = [CutPart(name="x", width=100, height=100, qty=1)]
        out = solve_cutlist_full((2440, 1220), parts)
        assert out.sheets_count == 1
        assert out.efficiency_pct > 0
"""Unit tests untuk furniture_qc.py dan cutlist.py.

Jalankan: pytest tests/test_qc.py -v
"""


class TestPageQCResult:
    def test_page_qc_result_initialization(self):
        from core.furniture_qc import PageQCResult, TitleBlock, QCIssue, BomPart
        
        # Test minimal PageQCResult
        page_res = PageQCResult(page_number=1)
        assert page_res.page_number == 1
        assert page_res.title_block is None
        assert len(page_res.issues) == 0
        assert len(page_res.bom) == 0
        
        # Test full PageQCResult
        title = TitleBlock(drawing_number="01", title="Meja Kerja")
        issue = QCIssue(
            severity="critical",
            category="dimensi",
            location="Kaki meja",
            issue="Missing ketebalan kaki",
            suggestion="Tambahkan tebal 18mm",
            page=1
        )
        bom_item = BomPart(name="top", width=1200, height=600, qty=1, material="plywood_18mm")
        
        page_res_full = PageQCResult(
            page_number=1,
            title_block=title,
            issues=[issue],
            praise=["Desain minimalis bagus"],
            bom=[bom_item]
        )
        
        assert page_res_full.page_number == 1
        assert page_res_full.title_block.title == "Meja Kerja"
        assert len(page_res_full.issues) == 1
        assert page_res_full.issues[0].severity == "critical"
        assert page_res_full.bom[0].name == "top"
        assert page_res_full.praise[0] == "Desain minimalis bagus"


# ============================================================
# 7. PDF Text Extraction (pdfplumber) — offline test
# ============================================================

class TestExtractPdfPageText:
    def test_returns_none_for_empty_bytes(self):
        from core.furniture_qc import _extract_pdf_page_text
        # PDF bytes yang invalid → harus return None tanpa raise
        result = _extract_pdf_page_text(b"not a pdf", 1)
        assert result is None

    def test_returns_none_for_out_of_range_page(self):
        """Halaman di luar jangkauan → None."""
        from core.furniture_qc import _extract_pdf_page_text
        import fitz
        # Buat PDF 1 halaman kosong
        doc = fitz.open()
        doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()
        # Minta halaman 99 → None
        result = _extract_pdf_page_text(pdf_bytes, 99)
        assert result is None

    def test_extracts_text_from_vector_pdf(self):
        """PDF dengan teks vektor harus bisa di-extract."""
        from core.furniture_qc import _extract_pdf_page_text
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        # Tulis teks ke PDF
        page.insert_text((72, 72), "DIMENSI: 600 x 400 mm", fontsize=14)
        pdf_bytes = doc.tobytes()
        doc.close()

        result = _extract_pdf_page_text(pdf_bytes, 1)
        assert result is not None
        assert "600" in result
        assert "400" in result


# ============================================================
# 8. Heuristic Bottom-Right Crop — offline test
# ============================================================

class TestCropBottomRight:
    def test_crop_returns_base64_string(self):
        from core.furniture_qc import _crop_bottom_right
        import base64
        # Buat image dummy 200x200 putih
        img = Image.new("RGB", (200, 200), (255, 255, 255))
        buf = BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        result = _crop_bottom_right(img_b64)
        assert result is not None
        # Harus bisa di-decode kembali jadi gambar
        decoded = base64.b64decode(result)
        cropped_img = Image.open(BytesIO(decoded))
        # Crop kanan-bawah: 0.6*200=120→200 (w=80), 0.5*200=100→200 (h=100)
        assert cropped_img.size == (80, 100)

    def test_crop_returns_none_for_invalid_input(self):
        from core.furniture_qc import _crop_bottom_right
        result = _crop_bottom_right("not-valid-base64!!!")
        assert result is None


# ============================================================
# 9. Cutlist Cached BOM — Dimensi Validation Fix
# ============================================================

class TestCutlistCachedBomValidation:
    def test_height_only_too_big_is_skipped(self):
        """Part 100x3000 harus di-skip untuk panel 2440x1220 (height gak muat bahkan dirotasi)."""
        from core.cutlist import _solve_from_cached_bom
        from core.furniture_qc import save_last_bom, BomPart, TitleBlock
        # Simpan BOM cache dengan part yang tingginya terlalu besar
        bom = [
            BomPart(name="tall_part", width=100, height=3000, thickness=18, qty=1, material="plywood_18mm"),
            BomPart(name="ok_part", width=600, height=400, thickness=18, qty=1, material="plywood_18mm"),
        ]
        save_last_bom("test_height_fix.pdf", bom, TitleBlock(title="Test"))

        result = _solve_from_cached_bom(panel_override=(2440, 1220))
        # tall_part harus di-skip, ok_part harus masuk
        assert "ok_part" in result.text
        # tall_part tidak boleh ada di layout (harus di-skip)
        assert "tall_part" not in result.text or "skipped" in result.text.lower() or "terlalu besar" in result.text.lower()


# ============================================================
# 10. Robust Validation & Fallback Handlers — offline test
# ============================================================

class TestQCIssueRobustness:
    def test_qc_issue_accepts_null_string_fields(self):
        """String fields yang None/null harus di-normalize menjadi string kosong tanpa ValueError."""
        from core.furniture_qc import QCIssue
        issue = QCIssue(
            severity=None,
            category=None,
            location=None,
            issue=None,
            suggestion=None
        )
        assert issue.severity == "info"
        assert issue.category == ""
        assert issue.location == ""
        assert issue.issue == ""
        assert issue.suggestion == ""


class TestCheckerAgentFallback:
    @pytest.mark.asyncio
    async def test_call_page_checker_fallback_on_parse_error(self):
        """Checker harus menangani error parse JSON secara anggun dengan mengembalikan fallback warning."""
        from core.furniture_qc import _call_page_checker
        import asyncio
        from unittest.mock import MagicMock
        
        # Mock OpenAI Client
        mock_client = MagicMock()
        mock_completion = MagicMock()
        # Mengembalikan string invalid yang memicu ValueError pada _safe_json_loads
        mock_completion.choices = [MagicMock(message=MagicMock(content="this-is-not-json-or-dots"))]
        mock_client.chat.completions.create.return_value = mock_completion
        
        semaphore = asyncio.Semaphore(1)
        res = await _call_page_checker(
            client=mock_client,
            img_b64="dummy",
            page_num=5,
            content_type="image/png",
            semaphore=semaphore
        )
        
        # Harus mengembalikan fallback dictionary yang valid
        assert res["page_number"] == 5
        assert len(res["issues"]) == 1
        assert res["issues"][0]["severity"] == "warning"
        assert "VLM parse error" in res["issues"][0]["issue"]
        assert res["issues"][0]["page"] == 5


# ============================================================
# 11. QC Drawing Memory Integration — offline test
# ============================================================

class TestQCMemoryIntegration:
    @pytest.mark.asyncio
    async def test_review_from_bytes_save_and_recall_approved_memory(self):
        """Memverifikasi bahwa ingatan referensi dipanggil dan data disimpan jika gambar kerja disetujui (Approved)."""
        from core.furniture_qc import _review_from_bytes
        from unittest.mock import AsyncMock, patch, MagicMock
        
        # Mock OpenAI Client & agentmemory_client
        mock_completion_page = MagicMock()
        mock_completion_page.choices = [MagicMock(message=MagicMock(content='{"overall_verdict": "approved", "summary": "Halaman OK", "issues": [], "praise": ["Bagus"], "bom": [{"name": "top", "width": 600, "height": 400, "qty": 1, "material": "plywood_18mm"}]}'))]
        
        mock_completion_consolidate = MagicMock()
        mock_completion_consolidate.choices = [MagicMock(message=MagicMock(content='{"overall_verdict": "approved", "summary": "Semua approved", "issues": [], "praise": ["Luar biasa"], "bom": [{"name": "top", "width": 600, "height": 400, "qty": 1, "material": "plywood_18mm"}], "title_block": {"title": "Meja Belajar", "drawing_number": "MB-01"}}'))]
        
        mock_agentmemory = AsyncMock()
        mock_agentmemory.recall.return_value = "Referensi Sebelumnya: plywood meja 600x400"
        mock_agentmemory.save = AsyncMock()
        
        mock_memory_engine = MagicMock()
        mock_memory_engine.add_fact = MagicMock()
        
        # Buat dummy image bytes
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        buf = BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        
        with patch("core.furniture_qc.OpenAI") as mock_openai_cls, \
             patch("core.agentmemory_client.recall", mock_agentmemory.recall), \
             patch("core.agentmemory_client.save", mock_agentmemory.save), \
             patch("memory.memory_engine.add_fact", mock_memory_engine.add_fact):
            
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = [mock_completion_page, mock_completion_consolidate]
            mock_openai_cls.return_value = mock_client
            
            # Panggil review_from_bytes
            result, _, _ = await _review_from_bytes(png_bytes, "meja_belajar.png")
            
            # Verifikasi recall dipanggil dengan query file
            mock_agentmemory.recall.assert_called()
            # Verifikasi save dipanggil karena verdict "approved"
            mock_agentmemory.save.assert_called()
            assert "MB-01" in mock_agentmemory.save.call_args[0][1]
            # Verifikasi add_fact dipanggil
            mock_memory_engine.add_fact.assert_called_with(
                "Referensi Gambar QC: Meja Belajar (MB-01)",
                "File: meja_belajar.png, BOM: 1 parts, Status: Approved"
            )
