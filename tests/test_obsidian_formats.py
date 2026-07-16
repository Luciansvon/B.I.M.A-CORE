import importlib
import importlib.util
import json
from pathlib import Path


def _module():
    assert importlib.util.find_spec("tools.obsidian_formats") is not None
    return importlib.import_module("tools.obsidian_formats")


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Projects").mkdir()
    (vault / "Projects" / "Chair.md").write_text("# Chair\n", encoding="utf-8")
    (vault / "Projects" / "Table.md").write_text("# Table\n", encoding="utf-8")
    return vault


def test_base_tool_creates_safe_base_file(tmp_path, monkeypatch):
    module = _module()
    vault = _vault(tmp_path)
    monkeypatch.setattr(module, "OBSIDIAN_PATH", str(vault))

    result = module.VaultBaseTool()._run(
        json.dumps(
            {
                "filename": "Furniture.base",
                "source_folder": "Projects",
                "view": "cards",
                "columns": ["file.name", "category", "status"],
            }
        )
    )

    target = vault / "Furniture.base"
    assert result == f"SUCCESS|{target}"
    content = target.read_text(encoding="utf-8")
    assert 'file.folder == "Projects"' in content
    assert "type: cards" in content
    assert "- file.name" in content
    assert "- category" in content
    assert "- status" in content


def test_base_tool_rejects_traversal_and_overwrite(tmp_path, monkeypatch):
    module = _module()
    vault = _vault(tmp_path)
    monkeypatch.setattr(module, "OBSIDIAN_PATH", str(vault))
    tool = module.VaultBaseTool()

    traversal = tool._run(json.dumps({"filename": "../escape.base"}))
    assert traversal.startswith("FAILED|")
    assert not (tmp_path / "escape.base").exists()

    target = vault / "Existing.base"
    target.write_text("original\n", encoding="utf-8")
    overwrite = tool._run(json.dumps({"filename": "Existing.base"}))
    assert overwrite.startswith("FAILED|")
    assert target.read_text(encoding="utf-8") == "original\n"


def test_base_tool_rejects_unknown_view_and_column(tmp_path, monkeypatch):
    module = _module()
    vault = _vault(tmp_path)
    monkeypatch.setattr(module, "OBSIDIAN_PATH", str(vault))
    tool = module.VaultBaseTool()

    assert tool._run(json.dumps({"filename": "Bad.base", "view": "graph"})).startswith(
        "FAILED|"
    )
    assert tool._run(
        json.dumps({"filename": "Bad.base", "columns": ["password"]})
    ).startswith("FAILED|")


def test_canvas_tool_creates_valid_canvas(tmp_path, monkeypatch):
    module = _module()
    vault = _vault(tmp_path)
    monkeypatch.setattr(module, "OBSIDIAN_PATH", str(vault))

    result = module.VaultCanvasTool()._run(
        json.dumps(
            {
                "filename": "Furniture Map.canvas",
                "notes": ["Chair", "Table"],
                "edges": [[0, 1]],
            }
        )
    )

    target = vault / "Furniture Map.canvas"
    assert result == f"SUCCESS|{target}"
    payload = json.loads(target.read_text(encoding="utf-8"))
    node_ids = {node["id"] for node in payload["nodes"]}
    assert len(node_ids) == 2
    assert all(len(node_id) == 16 for node_id in node_ids)
    assert all(set(node_id) <= set("0123456789abcdef") for node_id in node_ids)
    assert {node["file"] for node in payload["nodes"]} == {
        "Projects/Chair.md",
        "Projects/Table.md",
    }
    assert payload["nodes"][0]["x"] != payload["nodes"][1]["x"]
    assert payload["edges"][0]["fromNode"] in node_ids
    assert payload["edges"][0]["toNode"] in node_ids


def test_canvas_tool_rejects_missing_note_traversal_and_overwrite(
    tmp_path, monkeypatch
):
    module = _module()
    vault = _vault(tmp_path)
    monkeypatch.setattr(module, "OBSIDIAN_PATH", str(vault))
    tool = module.VaultCanvasTool()

    missing = tool._run(
        json.dumps({"filename": "Missing.canvas", "notes": ["Unknown"]})
    )
    assert missing.startswith("FAILED|")
    assert not (vault / "Missing.canvas").exists()

    traversal = tool._run(
        json.dumps({"filename": "../escape.canvas", "notes": ["Chair"]})
    )
    assert traversal.startswith("FAILED|")
    assert not (tmp_path / "escape.canvas").exists()

    target = vault / "Existing.canvas"
    target.write_text("{}", encoding="utf-8")
    overwrite = tool._run(
        json.dumps({"filename": "Existing.canvas", "notes": ["Chair"]})
    )
    assert overwrite.startswith("FAILED|")
    assert target.read_text(encoding="utf-8") == "{}"
