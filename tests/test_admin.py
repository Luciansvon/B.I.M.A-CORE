import json
import subprocess

import pytest
from pathlib import Path
from config import OUTPUT_DIR
from teams.t4_admin import ExcelGeneratorTool, PDFGeneratorTool, DataAnalysisTool
import teams.t4_admin.excel_tool as excel_module


def _fake_officecli_run(
    args: list[str], **_: object
) -> subprocess.CompletedProcess[str]:
    command = args[1]
    if command == "create":
        Path(args[2]).touch()
        return subprocess.CompletedProcess(args, 0, "", "")
    if command == "batch":
        payload = {"data": {"summary": {"failed": 0}, "results": []}}
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
    return subprocess.CompletedProcess(args, 0, "", "")


def test_data_analysis_fallback_path(tmp_path):
    # Buat file CSV dummy di OUTPUT_DIR
    csv_file = OUTPUT_DIR / "test_data_fallback.csv"
    csv_file.write_text("Bulan,Penjualan\nJan,100\nFeb,120\n")

    tool = DataAnalysisTool()
    # Panggil dengan path dummy yang tidak ada, tapi nama filenya ada di OUTPUT_DIR
    input_str = "nonexistent_dir/test_data_fallback.csv|bar|Bulan|Penjualan|formal"
    res = tool._run(input_str)

    # Bersihkan file
    if csv_file.exists():
        csv_file.unlink()

    # Harus berhasil memproses (mengembalikan path file chart)
    assert res.startswith("SUCCESS") or "SUCCESS" in res

def test_excel_generator_with_charts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(excel_module, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(
        excel_module,
        "_officecli_bin",
        lambda: "/usr/bin/officecli",
    )
    monkeypatch.setattr(excel_module.subprocess, "run", _fake_officecli_run)

    # Setup data JSON dengan chart tingkat dokumen dan tingkat sheet
    excel_data = {
        "filename": "test_chart_excel",
        "style": "formal",
        "charts": [
            {
                "type": "bar",
                "title": "Top Level Chart",
                "labels": ["Jan", "Feb"],
                "datasets": [{"label": "Penjualan", "data": [10, 20]}]
            }
        ],
        "sheets": [
            {
                "name": "Sheet Utama",
                "headers": ["Kolom1", "Kolom2"],
                "rows": [
                    ["Data A", 100],
                    ["Data B", 200]
                ],
                "charts": [
                    {
                        "type": "line",
                        "title": "Sheet Level Chart",
                        "labels": ["A", "B"],
                        "datasets": [{"label": "Target", "data": [100, 200]}]
                    }
                ]
            }
        ]
    }

    tool = ExcelGeneratorTool()
    res = tool._run(json.dumps(excel_data))

    assert res.startswith("SUCCESS")
    parts = res.split("|")
    filepath = Path(parts[1])
    assert filepath.exists()

    # Bersihkan file hasil output
    if filepath.exists():
        filepath.unlink()

def test_pdf_generator_footer():
    # Setup data JSON PDF dengan cover page diaktifkan
    pdf_data = {
        "filename": "test_pdf_cover",
        "style": "formal",
        "cover": True,
        "title": "Test Dokumen PDF",
        "author": "Bima",
        "sections": [
            {
                "title": "Pendahuluan",
                "content": "Ini adalah isi dokumen pertama."
            }
        ]
    }

    tool = PDFGeneratorTool()
    res = tool._run(json.dumps(pdf_data))

    assert res.startswith("SUCCESS")
    parts = res.split("|")
    filepath = Path(parts[1])
    assert filepath.exists()

    # Bersihkan file hasil output
    if filepath.exists():
        filepath.unlink()
