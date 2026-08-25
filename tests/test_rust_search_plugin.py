from pathlib import Path

from tools.plugins import rust_search


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_rust_search_paths_stay_in_project_root() -> None:
    assert rust_search.PROJECT_ROOT == PROJECT_ROOT
    assert rust_search.SOURCE_DIR == PROJECT_ROOT
    assert rust_search.SEARCH_INDEX_DIR == PROJECT_ROOT / "search_index"
    assert rust_search.BIMA_SEARCH_BIN == (
        PROJECT_ROOT / "tools" / "bima_search" / "target" / "release" / "bima_search"
    )


def test_rust_search_rejects_directory_as_binary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(rust_search, "BIMA_SEARCH_BIN", tmp_path)

    result = rust_search.RustSearchTool()._run("manager_node")

    assert "belum dikompilasi" in result
