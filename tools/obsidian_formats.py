"""Create-only Obsidian Base and JSON Canvas files for the Arsip agent."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from crewai.tools import BaseTool

from config import OBSIDIAN_PATH

_ALLOWED_VIEWS = {"table", "cards", "list"}
_ALLOWED_COLUMNS = {
    "file.name",
    "file.folder",
    "file.mtime",
    "file.ctime",
    "file.size",
    "category",
    "tags",
    "status",
}
_MAX_CANVAS_NOTES = 20


def _parse_payload(input_str: str) -> dict[str, Any]:
    payload = json.loads(input_str)
    if not isinstance(payload, dict):
        raise ValueError("Input harus JSON object.")
    return payload


def _vault_root() -> Path:
    vault = Path(OBSIDIAN_PATH).expanduser().resolve()
    if not vault.is_dir():
        raise ValueError(f"Vault tidak ditemukan: {vault}")
    return vault


def _safe_target(vault: Path, filename: Any, suffix: str) -> Path:
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename wajib diisi.")
    clean = filename.strip()
    if Path(clean).name != clean or Path(clean).suffix.lower() != suffix:
        raise ValueError(f"filename harus nama file {suffix} tanpa folder.")
    target = (vault / clean).resolve()
    if target.parent != vault:
        raise ValueError("Target harus berada di root vault.")
    if target.exists():
        raise FileExistsError(f"File sudah ada: {target.name}")
    return target


def _safe_relative_folder(vault: Path, raw_folder: Any) -> str:
    if raw_folder in (None, ""):
        return ""
    if not isinstance(raw_folder, str):
        raise ValueError("source_folder harus string.")
    relative = Path(raw_folder.strip())
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("source_folder harus berada di dalam vault.")
    source = (vault / relative).resolve()
    if source != vault and vault not in source.parents:
        raise ValueError("source_folder harus berada di dalam vault.")
    if not source.is_dir():
        raise ValueError(f"Folder tidak ditemukan: {raw_folder}")
    return relative.as_posix().strip("./")


def _write_create_only(target: Path, content: str) -> None:
    try:
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        if target.exists() and target.stat().st_size == 0:
            target.unlink()
        raise


def _base_yaml(source_folder: str, view: str, columns: list[str]) -> str:
    lines: list[str] = []
    if source_folder:
        expression = f'file.folder == "{source_folder}"'.replace("'", "''")
        lines.extend(["filters:", "  and:", f"    - '{expression}'"])
    lines.extend(
        [
            "views:",
            f"  - type: {view}",
            f"    name: {view.title()}",
            "    order:",
        ]
    )
    lines.extend(f"      - {column}" for column in columns)
    return "\n".join(lines) + "\n"


class VaultBaseTool(BaseTool):
    name: str = "Obsidian Base Creator"
    description: str = (
        "Buat file .base baru di vault Obsidian. Input JSON: "
        '{"filename":"Nama.base","source_folder":"Projects",'
        '"view":"table|cards|list","columns":["file.name","category"]}. '
        "Tool tidak pernah menimpa file lama."
    )

    def _run(self, input_str: str) -> str:
        try:
            payload = _parse_payload(input_str)
            vault = _vault_root()
            target = _safe_target(vault, payload.get("filename"), ".base")
            source_folder = _safe_relative_folder(
                vault, payload.get("source_folder", "")
            )
            view = payload.get("view", "table")
            if view not in _ALLOWED_VIEWS:
                raise ValueError("view harus table, cards, atau list.")
            columns = payload.get("columns", ["file.name", "file.mtime"])
            if not isinstance(columns, list) or not columns:
                raise ValueError("columns harus list yang tidak kosong.")
            if any(column not in _ALLOWED_COLUMNS for column in columns):
                raise ValueError("columns mengandung properti yang tidak diizinkan.")
            _write_create_only(target, _base_yaml(source_folder, view, columns))
            return f"SUCCESS|{target}"
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            return f"FAILED|{exc}"


def _find_notes(vault: Path, names: list[str]) -> list[Path]:
    note_index: dict[str, list[Path]] = {}
    for path in vault.rglob("*.md"):
        if path.is_file():
            note_index.setdefault(path.stem.casefold(), []).append(path)

    resolved: list[Path] = []
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Setiap note harus berupa nama yang tidak kosong.")
        clean = name.strip()
        if Path(clean).name != clean or Path(clean).suffix:
            raise ValueError("Note harus memakai nama tanpa folder atau ekstensi.")
        matches = note_index.get(clean.casefold(), [])
        if not matches:
            raise ValueError(f"Note tidak ditemukan: {clean}")
        if len(matches) > 1:
            raise ValueError(f"Nama note ambigu: {clean}")
        resolved.append(matches[0])
    return resolved


def _canvas_payload(vault: Path, notes: list[Path], edges: Any) -> dict[str, Any]:
    node_ids = [secrets.token_hex(8) for _ in notes]
    nodes = [
        {
            "id": node_ids[index],
            "type": "file",
            "file": note.relative_to(vault).as_posix(),
            "x": (index % 4) * 420,
            "y": (index // 4) * 300,
            "width": 360,
            "height": 220,
        }
        for index, note in enumerate(notes)
    ]
    if not isinstance(edges, list):
        raise ValueError("edges harus list pasangan index node.")
    canvas_edges: list[dict[str, Any]] = []
    for edge in edges:
        if (
            not isinstance(edge, list)
            or len(edge) != 2
            or not all(isinstance(index, int) for index in edge)
        ):
            raise ValueError("Setiap edge harus berbentuk [from_index, to_index].")
        from_index, to_index = edge
        if not (0 <= from_index < len(nodes) and 0 <= to_index < len(nodes)):
            raise ValueError("Edge menunjuk index node yang tidak valid.")
        canvas_edges.append(
            {
                "id": secrets.token_hex(8),
                "fromNode": node_ids[from_index],
                "toNode": node_ids[to_index],
            }
        )
    return {"nodes": nodes, "edges": canvas_edges}


class VaultCanvasTool(BaseTool):
    name: str = "Obsidian Canvas Creator"
    description: str = (
        "Buat file .canvas baru dari note yang sudah ada. Input JSON: "
        '{"filename":"Peta.canvas","notes":["Note A","Note B"],'
        '"edges":[[0,1]]}. Maksimum 20 note dan tidak menimpa file lama.'
    )

    def _run(self, input_str: str) -> str:
        try:
            payload = _parse_payload(input_str)
            vault = _vault_root()
            target = _safe_target(vault, payload.get("filename"), ".canvas")
            names = payload.get("notes")
            if not isinstance(names, list) or not names:
                raise ValueError("notes harus list yang tidak kosong.")
            if len(names) > _MAX_CANVAS_NOTES:
                raise ValueError(f"Canvas maksimal {_MAX_CANVAS_NOTES} note.")
            notes = _find_notes(vault, names)
            canvas = _canvas_payload(vault, notes, payload.get("edges", []))
            content = json.dumps(canvas, ensure_ascii=False, indent=2) + "\n"
            _write_create_only(target, content)
            return f"SUCCESS|{target}"
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            return f"FAILED|{exc}"
