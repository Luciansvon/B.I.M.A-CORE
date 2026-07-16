from pathlib import Path
from unittest.mock import patch

import pytest

from core.path_security import resolve_allowed_path, safe_output_path


def test_safe_output_path_keeps_traversal_inside_root(tmp_path: Path) -> None:
    output = tmp_path / "outputs"
    output.mkdir()

    result = safe_output_path(
        output,
        "../../../../home/bima/.bashrc",
        default_stem="dokumen",
        suffix=".pdf",
        timestamp="20260712_120000",
    )

    assert result.parent == output.resolve()
    assert result.name == "bashrc_20260712_120000.pdf"


def test_resolve_allowed_path_rejects_absolute_outside_root(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "outputs"
    allowed.mkdir()
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"not-an-image")

    with pytest.raises(ValueError, match="Path tidak diizinkan"):
        resolve_allowed_path(secret, (allowed,), allowed_suffixes={".png"})


def test_resolve_allowed_path_rejects_symlink_escape(tmp_path: Path) -> None:
    allowed = tmp_path / "outputs"
    allowed.mkdir()
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"secret")
    link = allowed / "reference.png"
    link.symlink_to(secret)

    with pytest.raises(ValueError, match="Path tidak diizinkan"):
        resolve_allowed_path(link, (allowed,), allowed_suffixes={".png"})


def test_resolve_allowed_path_accepts_existing_file_in_root(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "outputs"
    allowed.mkdir()
    image = allowed / "reference.png"
    image.write_bytes(b"image")

    result = resolve_allowed_path(image, (allowed,), allowed_suffixes={".png"})

    assert result == image.resolve()


@pytest.mark.parametrize(
    ("requested", "suffix"),
    [
        ("../../outside", ".xlsx"),
        ("/etc/passwd", ".pdf"),
        (r"..\..\Windows\win.ini", ".docx"),
    ],
)
def test_document_output_names_cannot_change_parent(
    tmp_path: Path,
    requested: str,
    suffix: str,
) -> None:
    output = tmp_path / "outputs"
    output.mkdir()

    result = safe_output_path(
        output,
        requested,
        default_stem="dokumen",
        suffix=suffix,
        timestamp="20260712_120000",
    )

    assert result.parent == output.resolve()
    assert ".." not in result.name


def test_image_gen_rejects_reference_outside_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import image_gen_tool

    output = tmp_path / "outputs"
    output.mkdir()
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"secret")
    monkeypatch.setattr(image_gen_tool, "_OUTPUT_DIR", output)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    with patch("openai.OpenAI") as client:
        result = image_gen_tool.ImageGenTool()._run(
            "buat variasi",
            [str(secret)],
        )

    assert result == "FAILED|Reference image tidak diizinkan"
    client.assert_not_called()
