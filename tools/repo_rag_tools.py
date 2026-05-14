"""CrewAI BaseTool wrappers untuk repo RAG. Dipake kodok_agent."""
from __future__ import annotations

import logging
from pathlib import Path

from crewai.tools import BaseTool

from tools.repo_rag import explain_path, search_repo, stats

logger = logging.getLogger("bima_core")

_MAX_CONTENT_PREVIEW = 800
_MAX_TOTAL_OUTPUT = 6000


def _fmt_chunk(row: dict, with_preview: bool = True) -> str:
    rel = row.get("rel_path", "?")
    kind = row.get("kind", "?")
    symbol = row.get("symbol", "?")
    s, e = row.get("start_line", 0), row.get("end_line", 0)
    loc = f":{s}-{e}" if s else ""
    head = f"[{kind}] {rel}{loc}  ·  {symbol}"
    if not with_preview:
        return head
    body = (row.get("content") or "").strip()
    if len(body) > _MAX_CONTENT_PREVIEW:
        body = body[:_MAX_CONTENT_PREVIEW] + "\n# ...[truncated]"
    return f"{head}\n```\n{body}\n```"


def _trim_output(lines: list[str]) -> str:
    out = "\n\n".join(lines)
    if len(out) <= _MAX_TOTAL_OUTPUT:
        return out
    return out[:_MAX_TOTAL_OUTPUT] + "\n\n... (output truncated)"


class RepoExplainTool(BaseTool):
    name: str = "Repo Explain Tool"
    description: str = """Jelasin isi sebuah file atau modul di repo BIMA_CORE.
    HANYA gunakan jika Bima minta penjelasan/summary file kode/dokumen tertentu di repo.
    Input: relative path file (mis. 'core/langgraph_engine.py' atau 'teams/t4_admin.py').
    Output: list chunk (function/class/section) dari file tersebut dengan preview kode."""

    def _run(self, path: str) -> str:
        path = (path or "").strip().strip('"').strip("'")
        if not path:
            return "FAILED|Path kosong"
        rows = explain_path(path, top_k=10)
        if not rows:
            return f"FAILED|Path '{path}' gak ketemu di index. Coba `build_index()` dulu atau cek typo."
        # Show file header
        header = f"## {rows[0]['rel_path']}\n_{len(rows)} chunk_"
        body = [_fmt_chunk(r) for r in rows]
        return _trim_output([header] + body)


class RepoSearchSymbolTool(BaseTool):
    name: str = "Repo Search Symbol Tool"
    description: str = """Cari fungsi/class/symbol/konsep di codebase BIMA_CORE pakai semantic search.
    HANYA gunakan jika Bima minta cari fungsi/class/di mana sesuatu dipakai/contoh implementasi.
    Input: query bebas. Contoh: "fungsi emit untuk event bus", "di mana semantic memory recall dipakai", "tool generate PDF".
    Output: top hasil dengan path:line + preview kode."""

    def _run(self, query: str) -> str:
        query = (query or "").strip()
        if not query:
            return "FAILED|Query kosong"
        rows = search_repo(query, top_k=6)
        if not rows:
            return f"FAILED|Gak ada hasil buat query '{query}'. Pastikan repo udah ke-index."
        body = [_fmt_chunk(r) for r in rows]
        return _trim_output([f"## Search: {query}", f"_{len(rows)} hasil_"] + body)


class RepoSummarizeTool(BaseTool):
    name: str = "Repo Summarize Tool"
    description: str = """Ringkas isi sebuah direktori — list file + symbol utama.
    HANYA gunakan jika Bima minta overview folder/modul tertentu.
    Input: relative path direktori (mis. 'core/langgraph_nodes/' atau 'teams/').
    Output: list file di dir + ringkasan symbol (function/class) per file."""

    def _run(self, dir_path: str) -> str:
        dir_path = (dir_path or "").strip().strip('"').strip("'").rstrip("/").rstrip("\\")
        if not dir_path:
            return "FAILED|Path direktori kosong"

        from tools.repo_rag import _connect_db, _table_exists, _TABLE_NAME
        try:
            db = _connect_db()
            if not _table_exists(db, _TABLE_NAME):
                return "FAILED|Index belum ada. Jalanin build_index() dulu."
            tbl = db.open_table(_TABLE_NAME)
            df = tbl.to_pandas()
        except Exception as e:
            return f"FAILED|{e}"

        needle = dir_path.replace("\\", "/").strip("/") + "/"
        subset = df[df["rel_path"].str.startswith(needle)]
        if subset.empty:
            # Try without trailing slash for exact dir name match
            alt = dir_path.replace("\\", "/").strip("/")
            subset = df[df["rel_path"].str.contains(f"^{alt}/", regex=True, na=False)]
        if subset.empty:
            return f"FAILED|Dir '{dir_path}' kosong atau gak ke-index."

        files = subset["rel_path"].unique()
        lines = [f"## Summary: `{dir_path}`", f"_{len(files)} file ke-index_\n"]
        for rel in sorted(files)[:30]:
            file_chunks = subset[subset["rel_path"] == rel]
            kinds = file_chunks["kind"].value_counts().to_dict()
            symbols = file_chunks[file_chunks["kind"].isin(["function", "class"])]["symbol"].tolist()
            kind_str = ", ".join(f"{k}={v}" for k, v in kinds.items())
            symbol_str = (", ".join(symbols[:8]) + ("..." if len(symbols) > 8 else "")) if symbols else "_(no top-level def)_"
            lines.append(f"- **{rel}** — {kind_str}\n  symbols: {symbol_str}")
        if len(files) > 30:
            lines.append(f"\n_... dan {len(files) - 30} file lagi._")
        return _trim_output(lines)


class RepoIndexStatsTool(BaseTool):
    name: str = "Repo Index Stats Tool"
    description: str = """Cek status index repo (jumlah file, chunk, breakdown by kind).
    Pakai kalau Bima nanya 'index udah jalan?' atau 'apa yang udah ke-index'.
    Input: kosongkan saja (string apa aja diabaikan)."""

    def _run(self, _ignored: str = "") -> str:
        s = stats()
        if not s.get("exists"):
            return f"Index belum ada. Jalanin `build_index()` dulu. Detail: {s.get('error', 'tidak ada error spesifik')}"
        lines = [
            f"## Repo Index Stats",
            f"- Files: **{s.get('files', 0)}**",
            f"- Chunks: **{s.get('chunks', 0)}**",
            f"- Kinds: {s.get('kinds', {})}",
        ]
        return "\n".join(lines)
