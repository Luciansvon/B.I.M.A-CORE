import os
import pytest
from pathlib import Path
from unittest.mock import patch
from tools.slide_generator import SlideGeneratorTool, extract_pdf_page_to_png

@pytest.fixture
def dummy_marp_content():
    return """---
marp: true
theme: default
class: lead
---
# Meja Kayu Scandinavian
Desain premium berbahan oak alami.
---
## Detail Material
- Oak solid wood
- Finishing natural oil varnish
- Dimensi: 120 x 60 x 75 cm
"""

def test_slide_generator_pdf(dummy_marp_content):
    tool = SlideGeneratorTool()
    res = tool._run(markdown_content=dummy_marp_content, output_format="pdf", theme_style="Scandinavian", bypass_preview=True)
    
    assert res.startswith("SUCCESS|")
    parts = res.split("|")
    out_path = Path(parts[1])
    assert out_path.exists()
    assert out_path.suffix == ".pdf"
    
    # Clean up
    if out_path.exists():
        out_path.unlink()

def test_slide_generator_pptx(dummy_marp_content):
    tool = SlideGeneratorTool()
    res = tool._run(markdown_content=dummy_marp_content, output_format="pptx", theme_style="Scandinavian", bypass_preview=True)
    
    assert res.startswith("SUCCESS|")
    parts = res.split("|")
    out_path = Path(parts[1])
    assert out_path.exists()
    assert out_path.suffix == ".pptx"
    
    # Clean up
    if out_path.exists():
        out_path.unlink()

def test_slide_generator_png(dummy_marp_content):
    tool = SlideGeneratorTool()
    res = tool._run(markdown_content=dummy_marp_content, output_format="png", theme_style="Scandinavian", bypass_preview=True)
    
    assert res.startswith("SUCCESS|")
    parts = res.split("|")
    png_paths = parts[1].split(",")
    assert len(png_paths) > 0
    for path_str in png_paths:
        p = Path(path_str)
        assert p.exists()
        assert p.suffix == ".png"
        p.unlink()

def test_extract_pdf_page(dummy_marp_content):
    # Buat PDF dummy dulu menggunakan slide generator
    tool = SlideGeneratorTool()
    res = tool._run(markdown_content=dummy_marp_content, output_format="pdf", bypass_preview=True)
    pdf_path = res.split("|")[1]
    
    # Lakukan ekstraksi halaman 1
    ext_res = extract_pdf_page_to_png(pdf_path, page_num=1)
    
    assert ext_res.startswith("SUCCESS|")
    ext_path = Path(ext_res.split("|")[1])
    assert ext_path.exists()
    assert ext_path.suffix == ".png"
    
    # Clean up
    if Path(pdf_path).exists():
        Path(pdf_path).unlink()
    if ext_path.exists():
        ext_path.unlink()

def test_slide_generator_preview_approval(dummy_marp_content):
    tool = SlideGeneratorTool()
    with patch("core.permission_gate.check_permission_sync", return_value=True) as mock_gate:
        res = tool._run(markdown_content=dummy_marp_content, output_format="pdf", theme_style="Scandinavian", bypass_preview=False)
        assert res.startswith("SUCCESS|")
        mock_gate.assert_called_once()
        out_path = Path(res.split("|")[1])
        if out_path.exists():
            out_path.unlink()

def test_slide_generator_preview_denial(dummy_marp_content):
    tool = SlideGeneratorTool()
    with patch("core.permission_gate.check_permission_sync", return_value=False) as mock_gate:
        res = tool._run(markdown_content=dummy_marp_content, output_format="pdf", theme_style="Scandinavian", bypass_preview=False)
        assert res == "FAILED|Persetujuan draf preview slide ditolak oleh Bima."
        mock_gate.assert_called_once()
