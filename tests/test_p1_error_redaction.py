import ast
from pathlib import Path

from core.public_errors import public_failure, public_message


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGETS = (
    "core/discord_bot.py",
    "core/saham_commands.py",
    "core/arsip_commands.py",
    "teams/t4_admin/data_analysis_tool.py",
    "teams/t4_admin/excel_tool.py",
    "teams/t4_admin/pdf_tool.py",
    "teams/t4_admin/word_tool.py",
    "teams/t5_intel.py",
    "teams/t6_lifestyle.py",
    "teams/t8_mekanik.py",
    "teams/t9_saham.py",
)


def test_public_error_helpers_never_include_exception_detail() -> None:
    assert public_failure("Gagal membuat PDF") == (
        "FAILED|Gagal membuat PDF. Detail teknis dicatat di log."
    )
    assert public_message("Gagal memproses permintaan") == (
        "❌ Gagal memproses permintaan. Detail teknis dicatat di log."
    )


def _contains_name(node: ast.AST | None, name: str) -> bool:
    return bool(node) and any(
        isinstance(child, ast.Name) and child.id == name
        for child in ast.walk(node)
    )


def test_exception_details_are_not_returned_or_replied_to_chat() -> None:
    leaks: list[str] = []
    for relative in TARGETS:
        path = PROJECT_ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for handler in (
            node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)
        ):
            if not handler.name:
                continue
            for node in ast.walk(handler):
                if isinstance(node, ast.Return) and _contains_name(
                    node.value,
                    handler.name,
                ):
                    leaks.append(f"{relative}:{node.lineno}:return")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "reply" and any(
                        _contains_name(arg, handler.name) for arg in node.args
                    ):
                        leaks.append(f"{relative}:{node.lineno}:reply")
                    if node.func.attr == "append" and _contains_name(
                        node,
                        handler.name,
                    ):
                        leaks.append(f"{relative}:{node.lineno}:append")

    assert leaks == []
    mekanik = (PROJECT_ROOT / "teams/t8_mekanik.py").read_text(encoding="utf-8")
    assert "traceback.format_exc()" not in mekanik
