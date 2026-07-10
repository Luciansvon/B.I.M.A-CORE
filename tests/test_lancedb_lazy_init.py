import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _top_level_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    return imports


def test_arsip_does_not_connect_to_lancedb_at_module_import() -> None:
    source = (PROJECT_ROOT / "teams" / "t3_arsip.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    top_level_connects = []
    top_level_imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports.extend(alias.name for alias in node.names)
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute):
            continue
        if isinstance(value.func.value, ast.Name):
            if value.func.value.id == "lancedb" and value.func.attr == "connect":
                top_level_connects.append(node.lineno)

    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "lancedb" not in top_level_imports
    assert top_level_connects == []
    assert "_get_db" in functions


def test_arsip_startup_index_is_explicitly_started_after_mcp() -> None:
    arsip_source = (PROJECT_ROOT / "teams" / "t3_arsip.py").read_text(encoding="utf-8")
    main_source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(arsip_source)

    top_level_thread_starts = []
    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if isinstance(call.func, ast.Attribute) and call.func.attr == "start":
            top_level_thread_starts.append(node.lineno)

    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert top_level_thread_starts == []
    assert "start_vault_index_background" in functions
    assert main_source.index("_inject_mcp_tools(mcp_mgr)") < main_source.index(
        "start_vault_index_background()"
    )


def test_repo_rag_does_not_import_lancedb_at_module_import() -> None:
    imports = _top_level_imports(PROJECT_ROOT / "tools" / "repo_rag.py")

    assert "lancedb" not in imports
