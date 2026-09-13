import pytest
from pathlib import Path
from tools.code_visualizer import CodebaseVisualizerTool

def test_codebase_visualizer():
    tool = CodebaseVisualizerTool()
    # Pindai subdirektori tools/ untuk pengujian cepat
    res = tool._run(target_dir="tools")
    
    assert res.startswith("SUCCESS|")
    parts = res.split("|")
    out_path = Path(parts[1])
    
    assert out_path.exists()
    assert out_path.suffix == ".html"
    
    # Verifikasi isi file html berisi Cytoscape script
    content = out_path.read_text(encoding="utf-8")
    assert "cytoscape" in content.lower()
    assert "elements" in content
    
    # Clean up
    if out_path.exists():
        out_path.unlink()


def test_codebase_visualizer_rejects_path_outside_workspace(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text(
        "SECRET = 'do-not-read'",
        encoding="utf-8",
    )

    result = CodebaseVisualizerTool()._run(str(outside))

    assert result == "FAILED|Direktori tidak diizinkan."
