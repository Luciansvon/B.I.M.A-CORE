import pytest
from pathlib import Path
from tools import diagram_tool
from tools.diagram_tool import DiagramGeneratorTool


def test_diagram_generator_success():
    tool = DiagramGeneratorTool()
    res = tool._run(mermaid_code="graph TD;\nA-->B;\nA-->C;", title="Test Diagram")

    assert res.startswith("SUCCESS|")
    parts = res.split("|")
    out_path = Path(parts[1])

    assert out_path.exists()
    assert out_path.suffix == ".html"

    content = out_path.read_text(encoding="utf-8")
    assert "mermaid" in content.lower()
    assert "Test Diagram" in content
    assert "A--&gt;B" in content or "A-->B" in content

    out_path.unlink()


def test_diagram_generator_empty_code():
    tool = DiagramGeneratorTool()
    res = tool._run(mermaid_code="   ", title="Empty")
    assert res.startswith("FAILED|")


def test_different_diagrams_do_not_collide_at_same_timestamp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(diagram_tool, "_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(diagram_tool.time, "time", lambda: 1234)
    monkeypatch.setattr(diagram_tool.time, "time_ns", lambda: 1234, raising=False)
    tool = DiagramGeneratorTool()

    first = Path(tool._run("graph TD; A-->B", "First").split("|")[1])
    second = Path(tool._run("graph TD; A-->C", "Second").split("|")[1])

    assert first != second
    assert first.exists()
    assert second.exists()


def test_diagram_escapes_title_and_mermaid_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(diagram_tool, "_OUTPUT_DIR", tmp_path)

    result = DiagramGeneratorTool()._run(
        "graph TD; A[<script>alert(1)</script>]",
        "</h1><script>alert(2)</script>",
    )

    content = Path(result.split("|")[1]).read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in content
    assert "<script>alert(2)</script>" not in content
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content


def test_diagram_write_failure_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(diagram_tool, "_OUTPUT_DIR", tmp_path)

    def fail_write(*args: object, **kwargs: object) -> None:
        raise OSError("secret filesystem detail")

    monkeypatch.setattr(Path, "write_text", fail_write)

    result = DiagramGeneratorTool()._run("graph TD; A-->B", "Failure")

    assert result == (
        "FAILED|Gagal menulis file HTML diagram. Detail teknis dicatat di log."
    )
