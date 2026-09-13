import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz
import pytest

from tools import slide_generator
from tools.slide_generator import (
    SlideGeneratorInput,
    SlideGeneratorTool,
    extract_pdf_page_to_png,
)


@pytest.fixture
def dummy_marp_content() -> str:
    return """---
marp: true
---
# Meja Kayu Scandinavian
---
## Detail Material
- Oak solid wood
"""


def test_public_schema_has_no_preview_bypass() -> None:
    assert "bypass_preview" not in SlideGeneratorInput.model_fields


def test_pdf_always_requires_preview_approval(
    dummy_marp_content: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = SlideGeneratorTool()
    preview = tmp_path / "preview.001.png"
    final_pdf = tmp_path / "final.pdf"
    calls: list[str] = []

    def fake_compile(markdown: str, output_format: str, theme: str) -> str:
        calls.append(output_format)
        if output_format == "png":
            preview.write_bytes(b"png")
            return f"SUCCESS|{preview}|preview"
        final_pdf.write_bytes(b"pdf")
        return f"SUCCESS|{final_pdf}|final"

    monkeypatch.setattr(tool, "_compile", fake_compile, raising=False)
    with patch("core.permission_gate.check_permission_sync", return_value=True) as gate:
        result = tool._run(dummy_marp_content, "pdf", "Scandinavian")

    assert result.startswith(f"SUCCESS|{final_pdf}")
    assert calls == ["png", "pdf"]
    assert not preview.exists()
    gate.assert_called_once()


def test_preview_denial_never_compiles_final(
    dummy_marp_content: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = SlideGeneratorTool()
    preview = tmp_path / "preview.001.png"
    calls: list[str] = []

    def fake_compile(markdown: str, output_format: str, theme: str) -> str:
        calls.append(output_format)
        preview.write_bytes(b"png")
        return f"SUCCESS|{preview}|preview"

    monkeypatch.setattr(tool, "_compile", fake_compile, raising=False)
    with patch("core.permission_gate.check_permission_sync", return_value=False):
        result = tool._run(dummy_marp_content, "pdf", "Scandinavian")

    assert result == "FAILED|Persetujuan draf preview slide ditolak oleh Bima."
    assert calls == ["png"]
    assert not preview.exists()


def test_png_compiles_once_without_recursive_preview(
    dummy_marp_content: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = SlideGeneratorTool()
    calls: list[str] = []

    def fake_compile(markdown: str, output_format: str, theme: str) -> str:
        calls.append(output_format)
        return "SUCCESS|preview.png|png"

    monkeypatch.setattr(tool, "_compile", fake_compile, raising=False)

    assert tool._run(dummy_marp_content, "png") == "SUCCESS|preview.png|png"
    assert calls == ["png"]


def test_find_chrome_prefers_linux_puppeteer_over_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chrome = tmp_path / ".cache" / "puppeteer" / "chrome" / "linux-1" / "chrome"
    chrome.parent.mkdir(parents=True)
    chrome.write_text("#!/bin/sh\n", encoding="utf-8")
    chrome.chmod(0o755)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr(slide_generator.shutil, "which", lambda _: None)

    assert slide_generator._find_chrome() == chrome


def test_compiler_passes_resolved_chrome_path(
    dummy_marp_content: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chrome = tmp_path / "chrome"
    chrome.write_text("#!/bin/sh\n", encoding="utf-8")
    chrome.chmod(0o755)
    captured_env: dict[str, str] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> SimpleNamespace:
        captured_env.update(kwargs["env"])
        out_path = Path(cmd[cmd.index("-o") + 1])
        out_path.write_bytes(b"pdf")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(slide_generator, "_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(slide_generator, "_find_chrome", lambda: chrome)
    monkeypatch.setattr(slide_generator.subprocess, "run", fake_run)

    result = SlideGeneratorTool()._compile(dummy_marp_content, "pdf", "default")

    assert result.startswith("SUCCESS|")
    assert captured_env["CHROME_PATH"] == str(chrome)


def test_extract_pdf_page_uses_real_temporary_pdf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "source.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "BIMA")
    document.save(pdf_path)
    document.close()
    monkeypatch.setattr(slide_generator, "_OUTPUT_DIR", tmp_path)

    result = extract_pdf_page_to_png(str(pdf_path), page_num=1)

    assert result.startswith("SUCCESS|")
    assert Path(result.split("|")[1]).exists()
