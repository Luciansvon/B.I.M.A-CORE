"""B.I.M.A Core — Repo RAG indexer & retriever.

Walk codebase, chunk per fungsi/class (Python AST) atau per blok (file lain),
embed pakai SentenceTransformer (reuse dari t3_arsip), simpan ke LanceDB di
`repo_index/`. Search semantic dengan optional path filter.

Reuse:
- Embedder singleton dari teams.t3_arsip (lazy import biar avoid circular).
- LanceDB pattern dari t3_arsip.

Usage:
    from tools.repo_rag import build_index, search_repo, explain_path
    build_index()                          # full / incremental indexing
    chunks = search_repo("fungsi emit")    # semantic search
    summary = explain_path("core/event_bus.py")  # describe a file
"""
from __future__ import annotations

import ast
import logging
import os
import re
import time
from pathlib import Path
from typing import Iterable

import lancedb

logger = logging.getLogger("bima_core")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_INDEX_DIR = _PROJECT_ROOT / "repo_index"
_TABLE_NAME = "repo_chunks"
_DEFAULT_TARGET_CHARS = 1200
_MAX_CHUNK_CHARS = 4000

# Dir/file yang skip total saat walk (heuristik: dependency, output, binary, cache)
_IGNORE_DIRS = {
    "bima_env", ".git", "__pycache__", ".venv", "venv", "node_modules",
    "outputs", "logs", "repo_index", "search_index", "vault_index",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    "Bima_Vault", "bima_vault", "vault", ".cache",
}

# Ekstensi yang di-index. Sisanya di-skip.
_TEXT_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".rb",
    ".md", ".yml", ".yaml", ".toml", ".json", ".sh", ".bash", ".sql",
    ".html", ".css", ".env.example", ".txt",
}

# File patterns yang skip (lock files, large generated, binary disguised as text)
_SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "uv.lock", "Cargo.lock",
}

# --- Embedder reuse ---
_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        # Reuse model yang sama dengan t3_arsip — biar HF cache shared.
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def _connect_db():
    _INDEX_DIR.mkdir(exist_ok=True)
    return lancedb.connect(str(_INDEX_DIR))


# --- Walker ---
def _iter_repo_files(root: Path) -> Iterable[Path]:
    """Yield path file yang relevan, skip ignored dirs & non-text."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Mutasi dirnames in-place untuk skip subtree
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS and not d.startswith(".")]
        for fname in filenames:
            if fname in _SKIP_FILENAMES:
                continue
            p = Path(dirpath) / fname
            ext = p.suffix.lower()
            if ext in _TEXT_EXTS or fname in {"Dockerfile", "Makefile", ".gitignore"}:
                yield p


# --- Python AST chunker ---
def _chunk_python(text: str, path: str) -> list[dict]:
    """Split per top-level fungsi/class. Module-level code → 1 chunk awal."""
    chunks: list[dict] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        logger.warning(f"[repo_rag] AST parse gagal {path}: {e}. Fallback ke chunk_text.")
        return _chunk_text(text, path, language="python")

    lines = text.splitlines()
    seen_end = 0

    def _add(kind: str, name: str, start: int, end: int):
        nonlocal seen_end
        body = "\n".join(lines[start - 1:end]).strip()
        if not body:
            return
        if len(body) > _MAX_CHUNK_CHARS:
            body = body[:_MAX_CHUNK_CHARS] + "\n# ...[truncated]"
        chunks.append({
            "kind": kind,
            "symbol": name,
            "content": body,
            "start_line": start,
            "end_line": end,
        })
        seen_end = max(seen_end, end)

    # Module docstring + import header sebelum top-level def/class
    first_def_lineno = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first_def_lineno = node.lineno
            break

    if first_def_lineno and first_def_lineno > 1:
        header = "\n".join(lines[: first_def_lineno - 1]).strip()
        if header:
            chunks.append({
                "kind": "module_header",
                "symbol": Path(path).stem,
                "content": header[:_MAX_CHUNK_CHARS],
                "start_line": 1,
                "end_line": first_def_lineno - 1,
            })

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _add("function", node.name, node.lineno, getattr(node, "end_lineno", node.lineno))
        elif isinstance(node, ast.ClassDef):
            _add("class", node.name, node.lineno, getattr(node, "end_lineno", node.lineno))

    if not chunks:
        return _chunk_text(text, path, language="python")
    return chunks


# --- Generic text chunker ---
def _chunk_text(text: str, path: str, language: str = "") -> list[dict]:
    """Heuristik split — heading markdown atau blank-line block."""
    text = text.strip()
    if not text:
        return []

    if path.lower().endswith(".md"):
        section_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        sections: list[tuple[str, str]] = []
        last_end = 0
        last_heading = ""
        for m in section_pattern.finditer(text):
            body = text[last_end:m.start()].strip()
            if body:
                sections.append((last_heading, body))
            last_heading = m.group(2).strip()
            last_end = m.end()
        tail = text[last_end:].strip()
        if tail:
            sections.append((last_heading, tail))
        if sections:
            return [
                {"kind": "section", "symbol": h or "intro", "content": b[:_MAX_CHUNK_CHARS], "start_line": 0, "end_line": 0}
                for h, b in sections
            ]

    # Fallback: sliding window chunk
    chunks = []
    pos = 0
    n = len(text)
    while pos < n:
        end = min(pos + _DEFAULT_TARGET_CHARS, n)
        if end < n:
            # try break at newline
            nl = text.rfind("\n", pos, end)
            if nl > pos + _DEFAULT_TARGET_CHARS // 2:
                end = nl
        chunks.append({
            "kind": "block",
            "symbol": f"{Path(path).stem}_p{len(chunks)}",
            "content": text[pos:end],
            "start_line": 0,
            "end_line": 0,
        })
        pos = end
    return chunks


def _chunk_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        logger.debug(f"[repo_rag] skip {path}: {e}")
        return []

    if path.suffix.lower() == ".py":
        return _chunk_python(text, str(path))
    return _chunk_text(text, str(path))


# --- Indexer ---
def _table_exists(db, name: str) -> bool:
    try:
        return name in db.table_names()
    except Exception:
        return False


def build_index(full_rebuild: bool = False) -> dict:
    """Index seluruh repo. Incremental by default (skip file dengan mtime sama).

    Return: dict ringkasan {indexed, updated, skipped, deleted, elapsed_s}.
    """
    t0 = time.time()
    embedder = _get_embedder()
    db = _connect_db()
    project_root = _PROJECT_ROOT

    if full_rebuild and _table_exists(db, _TABLE_NAME):
        db.drop_table(_TABLE_NAME)

    existing_mtimes: dict[str, float] = {}
    if _table_exists(db, _TABLE_NAME):
        try:
            tbl = db.open_table(_TABLE_NAME)
            df = tbl.to_pandas()
            existing_mtimes = dict(zip(df["path"], df["mtime"]))
        except Exception as e:
            logger.warning(f"[repo_rag] gagal baca tabel existing: {e}")

    new_docs: list[dict] = []
    paths_to_refresh: list[str] = []
    n_new, n_updated, n_skipped = 0, 0, 0
    n_chunks = 0

    scanned_paths: set[str] = set()
    for file in _iter_repo_files(project_root):
        try:
            mtime = file.stat().st_mtime
            path_str = str(file)
            scanned_paths.add(path_str)

            if path_str in existing_mtimes and abs(existing_mtimes[path_str] - mtime) < 1e-6:
                n_skipped += 1
                continue

            chunks = _chunk_file(file)
            if not chunks:
                continue

            rel = file.relative_to(project_root).as_posix()
            for idx, ch in enumerate(chunks):
                vec = embedder.encode(ch["content"]).tolist()
                new_docs.append({
                    "path": path_str,
                    "rel_path": rel,
                    "filename": file.name,
                    "chunk_id": idx,
                    "kind": ch["kind"],
                    "symbol": ch["symbol"],
                    "start_line": int(ch.get("start_line", 0)),
                    "end_line": int(ch.get("end_line", 0)),
                    "content": ch["content"],
                    "vector": vec,
                    "mtime": mtime,
                })
                n_chunks += 1

            if path_str in existing_mtimes:
                paths_to_refresh.append(path_str)
                n_updated += 1
            else:
                n_new += 1
        except Exception as e:
            logger.warning(f"[repo_rag] error {file}: {e}")

    deleted_paths = [p for p in existing_mtimes if p not in scanned_paths]

    if not _table_exists(db, _TABLE_NAME):
        if not new_docs:
            logger.info("[repo_rag] gak ada file ke-index")
            return {"indexed": 0, "updated": 0, "skipped": 0, "deleted": 0, "elapsed_s": time.time() - t0}
        db.create_table(_TABLE_NAME, data=new_docs, mode="overwrite")
        elapsed = time.time() - t0
        logger.info(f"[repo_rag] index dibuat: {n_chunks} chunks dari {n_new} file ({elapsed:.1f}s)")
        return {"indexed": n_new, "updated": 0, "skipped": 0, "deleted": 0, "chunks": n_chunks, "elapsed_s": elapsed}

    tbl = db.open_table(_TABLE_NAME)
    try:
        for p in paths_to_refresh + deleted_paths:
            safe = p.replace("'", "''")
            try:
                tbl.delete(f"path = '{safe}'")
            except Exception as e:
                logger.debug(f"[repo_rag] delete {p} gagal: {e}")
        if new_docs:
            tbl.add(new_docs)
    except Exception as e:
        logger.error(f"[repo_rag] incremental update gagal: {e}")

    elapsed = time.time() - t0
    logger.info(
        f"[repo_rag] incremental: new={n_new}, updated={n_updated}, skipped={n_skipped}, "
        f"deleted={len(deleted_paths)}, chunks_added={n_chunks} ({elapsed:.1f}s)"
    )
    return {
        "indexed": n_new,
        "updated": n_updated,
        "skipped": n_skipped,
        "deleted": len(deleted_paths),
        "chunks_added": n_chunks,
        "elapsed_s": elapsed,
    }


# --- Retriever ---
def search_repo(query: str, top_k: int = 5, path_filter: str | None = None) -> list[dict]:
    """Semantic search. `path_filter` substring matched against rel_path."""
    if not query or not query.strip():
        return []
    try:
        db = _connect_db()
        if not _table_exists(db, _TABLE_NAME):
            return []
        tbl = db.open_table(_TABLE_NAME)
    except Exception as e:
        logger.warning(f"[repo_rag] connect db gagal: {e}")
        return []

    embedder = _get_embedder()
    try:
        query_vec = embedder.encode(query).tolist()
        df = tbl.search(query_vec).limit(top_k * 4).to_pandas()
    except Exception as e:
        logger.error(f"[repo_rag] search gagal: {e}", exc_info=True)
        return []

    rows = df.to_dict("records")
    if path_filter:
        pf = path_filter.lower().replace("\\", "/")
        rows = [r for r in rows if pf in r["rel_path"].lower()]
    return rows[:top_k]


def explain_path(rel_or_abs_path: str, top_k: int = 6) -> list[dict]:
    """Return semua chunk untuk path tertentu. Filter exact match dulu, fallback substring."""
    try:
        db = _connect_db()
        if not _table_exists(db, _TABLE_NAME):
            return []
        tbl = db.open_table(_TABLE_NAME)
        df = tbl.to_pandas()
    except Exception as e:
        logger.warning(f"[repo_rag] explain_path connect gagal: {e}")
        return []

    needle = rel_or_abs_path.replace("\\", "/").strip("/")
    # Try exact match by rel_path
    exact = df[df["rel_path"] == needle]
    if not exact.empty:
        out = exact.sort_values("start_line").head(top_k).to_dict("records")
        return out
    # Fallback substring match
    substr = df[df["rel_path"].str.contains(re.escape(needle), case=False, na=False)]
    return substr.sort_values(["rel_path", "start_line"]).head(top_k).to_dict("records")


def stats() -> dict:
    """Snapshot status index."""
    try:
        db = _connect_db()
        if not _table_exists(db, _TABLE_NAME):
            return {"exists": False}
        tbl = db.open_table(_TABLE_NAME)
        df = tbl.to_pandas()
        return {
            "exists": True,
            "chunks": len(df),
            "files": df["path"].nunique() if "path" in df else 0,
            "kinds": df["kind"].value_counts().to_dict() if "kind" in df else {},
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print("=== build_index ===")
    print(build_index())
    print()
    print("=== stats ===")
    print(stats())
