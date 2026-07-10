import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_arsip_does_not_connect_to_lancedb_at_module_import() -> None:
    source = (PROJECT_ROOT / "teams" / "t3_arsip.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    top_level_connects = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute):
            continue
        if isinstance(value.func.value, ast.Name):
            if value.func.value.id == "lancedb" and value.func.attr == "connect":
                top_level_connects.append(node.lineno)

    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert top_level_connects == []
    assert "_get_db" in functions
