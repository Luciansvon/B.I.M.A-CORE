import json
import re
import sys
from pathlib import Path
from types import ModuleType

import fitz
import pytest

from teams.t2_visual import ExcelReader
from teams.t4_admin import PDFGeneratorTool
from teams.t4_admin import chart_utils


def test_academic_footer_uses_actual_multipage_front_matter() -> None:
    sections = [
        {
            "heading": f"Bagian {index}",
            "content": "Isi singkat.",
        }
        for index in range(1, 75)
    ]
    payload = {
        "filename": "test_p2_academic_footer",
        "style": "akademik",
        "cover": True,
        "title": "Audit Penomoran Akademik",
        "author": "Bima",
        "abstract": " ".join(["Abstrak panjang untuk pengujian pagination."] * 900),
        "toc": True,
        "sections": sections,
    }

    result = PDFGeneratorTool()._run(json.dumps(payload))

    assert result.startswith("SUCCESS|")
    pdf_path = Path(result.split("|", 2)[1])
    try:
        with fitz.open(pdf_path) as document:
            footer_numbers: list[str] = []
            for page in document:
                matches = re.findall(
                    r"halaman\s+([ivxlcdm]+|\d+)",
                    page.get_text().lower(),
                )
                if matches:
                    footer_numbers.append(matches[-1])

        first_body = footer_numbers.index("1")
        assert first_body >= 3
        assert all(re.fullmatch(r"[ivxlcdm]+", value) for value in footer_numbers[:first_body])
        assert footer_numbers[first_body:first_body + 2] == ["1", "2"]
    finally:
        pdf_path.unlink(missing_ok=True)


def _chart_style() -> dict:
    return {
        "accent_rgb": (10, 100, 200),
        "table_header_rgb": (20, 30, 40),
        "title_rgb": (5, 10, 15),
    }


def test_invalid_chart_type_does_not_leave_open_figure() -> None:
    import matplotlib.pyplot as plt

    before = set(plt.get_fignums())
    try:
        with pytest.raises(ValueError, match="tidak didukung"):
            chart_utils.render_chart(
                {
                    "type": "scatter",
                    "labels": ["A"],
                    "datasets": [{"data": [1]}],
                },
                _chart_style(),
            )
        assert set(plt.get_fignums()) == before
    finally:
        plt.close("all")


def test_chart_save_failure_closes_created_figure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import matplotlib.pyplot as plt

    before = set(plt.get_fignums())
    monkeypatch.setattr(chart_utils, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(
        plt,
        "savefig",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    try:
        with pytest.raises(OSError, match="disk full"):
            chart_utils.render_chart(
                {
                    "type": "bar",
                    "labels": ["A"],
                    "datasets": [{"data": [1]}],
                },
                _chart_style(),
            )
        assert set(plt.get_fignums()) == before
    finally:
        plt.close("all")


def test_excel_reader_closes_workbook_when_iteration_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "broken.xlsx"
    source.write_bytes(b"fixture")

    class FakeSheet:
        dimensions = "A1:A1"
        max_row = 1
        max_column = 1

        def iter_rows(self, values_only: bool):
            raise RuntimeError("iteration failed")

    class FakeWorkbook:
        sheetnames = ["Bad"]

        def __init__(self) -> None:
            self.closed = False

        def __getitem__(self, name: str) -> FakeSheet:
            return FakeSheet()

        def close(self) -> None:
            self.closed = True

    workbook = FakeWorkbook()
    fake_openpyxl = ModuleType("openpyxl")
    fake_openpyxl.load_workbook = lambda *args, **kwargs: workbook
    monkeypatch.setitem(sys.modules, "openpyxl", fake_openpyxl)

    result = ExcelReader()._run(str(source))

    assert result.startswith("FAILED|")
    assert workbook.closed is True
