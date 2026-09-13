from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable


_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._ -]+")
_KNOWN_DOCUMENT_SUFFIXES = (".pdf", ".docx", ".xlsx")


def safe_output_path(
    root: Path,
    requested_name: object,
    *,
    default_stem: str,
    suffix: str,
    timestamp: str,
) -> Path:
    root = root.resolve()
    raw = str(requested_name or "").strip().replace("\\", "/")
    leaf = raw.rsplit("/", 1)[-1]
    for known_suffix in _KNOWN_DOCUMENT_SUFFIXES:
        if leaf.lower().endswith(known_suffix):
            leaf = leaf[: -len(known_suffix)]
            break
    stem = _UNSAFE_FILENAME_CHARS.sub("_", leaf).strip(" ._-")
    if not stem:
        stem = default_stem
    stem = stem[:80]
    candidate = (root / f"{stem}_{timestamp}{suffix}").resolve()
    if candidate.parent != root:
        raise ValueError("Path tidak diizinkan")
    return candidate


def safe_named_output_path(
    root: Path,
    requested_name: object,
    *,
    default_name: str,
) -> Path:
    root = root.resolve()
    raw = str(requested_name or "").strip().replace("\\", "/")
    leaf = raw.rsplit("/", 1)[-1]
    if raw != leaf or raw in {".", ".."}:
        raise ValueError("Path tidak diizinkan")
    name = _UNSAFE_FILENAME_CHARS.sub("_", leaf).strip(" ._-")
    if not name:
        name = default_name
    candidate = (root / name[:120]).resolve()
    if candidate.parent != root:
        raise ValueError("Path tidak diizinkan")
    return candidate


def resolve_allowed_path(
    candidate: str | os.PathLike[str],
    allowed_roots: Iterable[Path],
    *,
    base_dir: Path | None = None,
    allowed_suffixes: set[str] | None = None,
) -> Path:
    roots = tuple(root.resolve() for root in allowed_roots)
    if not roots:
        raise ValueError("Path tidak diizinkan")

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = (base_dir or Path.cwd()) / path
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("Path tidak diizinkan") from exc

    if not any(resolved == root or root in resolved.parents for root in roots):
        raise ValueError("Path tidak diizinkan")
    if allowed_suffixes is not None and resolved.suffix.lower() not in allowed_suffixes:
        raise ValueError("Path tidak diizinkan")
    return resolved
