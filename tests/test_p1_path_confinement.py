import base64
from pathlib import Path
from unittest.mock import patch

from teams import t2_visual, t8_mekanik
from teams.t4_admin import data_analysis_tool
from teams.t7_html_templates import render_template


def test_file_saver_rejects_parent_traversal_before_approval(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "outputs"
    output.mkdir()
    monkeypatch.setattr(t8_mekanik, "OUTPUT_DIR", output)

    with patch("core.permission_gate.check_permission_sync") as gate:
        result = t8_mekanik.FileSaverTool()._run("../escape.txt|secret")

    assert result == "FAILED|Path tidak diizinkan"
    gate.assert_not_called()


def test_file_saver_approval_shows_resolved_output_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "outputs"
    output.mkdir()
    monkeypatch.setattr(t8_mekanik, "OUTPUT_DIR", output)

    with patch(
        "core.permission_gate.check_permission_sync",
        return_value=False,
    ) as gate:
        t8_mekanik.FileSaverTool()._run("hasil.txt|isi")

    assert str((output / "hasil.txt").resolve()) in gate.call_args.args[1]


def test_data_analysis_rejects_existing_csv_outside_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "outputs"
    output.mkdir()
    secret = tmp_path / "secret.csv"
    secret.write_text("x,y\na,1\n", encoding="utf-8")
    monkeypatch.setattr(data_analysis_tool, "OUTPUT_DIR", output)

    result = data_analysis_tool.DataAnalysisTool()._run(
        f"{secret}|bar|x|y|formal"
    )

    assert result == "FAILED|Path tidak diizinkan"


def test_image_analyzer_rejects_local_image_outside_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "outputs"
    output.mkdir()
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"secret")
    monkeypatch.setattr(t2_visual, "OUTPUT_DIR", output)

    with patch("openai.OpenAI") as client:
        result = t2_visual.ImageAnalyzerTool()._run(str(secret))

    assert result == "FAILED|Path tidak diizinkan"
    client.assert_not_called()


def test_image_to_code_rejects_local_image_outside_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "outputs"
    output.mkdir()
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"secret")
    monkeypatch.setattr(t2_visual, "OUTPUT_DIR", output)

    with patch("openai.OpenAI") as client:
        result = t2_visual.ImageToCodeTool()._run(str(secret))

    assert result == "FAILED|Path tidak diizinkan"
    client.assert_not_called()


def test_html_template_does_not_embed_image_outside_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from teams import t7_html_templates

    output = tmp_path / "outputs"
    output.mkdir()
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"secret")
    monkeypatch.setattr(t7_html_templates, "OUTPUT_DIR", output)

    html = render_template({"sections": [{"image_path": str(secret)}]})

    assert base64.b64encode(b"secret").decode() not in html
