import os
import re
import logging
import math
import json
import hashlib
import shutil
import tempfile
import threading
import unicodedata
from pathlib import Path
from datetime import datetime
from crewai import Agent
from crewai.tools import BaseTool
from config import arsip_llm, OBSIDIAN_PATH
from core.embedder import get_embedder

logger = logging.getLogger('bima_core')

# Switch local/cloud via env EMBEDDING_BACKEND=local|cloud (default local).
# Cloud (bge-m3) dim=1024, local (all-MiniLM-L6-v2) dim=384 — kalau ganti backend,
# WAJIB drop & re-index folder vault_index/ supaya schema cocok.
embedder = get_embedder("arsip")
_db = None
_db_lock = threading.Lock()
_index_lock = threading.Lock()
_vault_save_lock = threading.Lock()


def _get_db():
    """Open LanceDB on first use, after MCP subprocess startup has completed."""
    global _db
    if _db is None:
        with _db_lock:
            if _db is None:
                import lancedb

                path = os.path.join(os.path.dirname(__file__), "../vault_index")
                _db = lancedb.connect(path)
    return _db

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        import torch
        from sentence_transformers import CrossEncoder
        # Reranker RAG search. Default GPU kalau tersedia — di CPU ~5x lebih lambat
        # (rerank 10 kandidat: ~4770ms CPU vs ~980ms GPU). Dengan F5-TTS dimatikan,
        # VRAM RTX 3050 4GB cukup buat embedder Qwen3 (~1.25GB) + reranker bareng.
        # Override manual via env RERANKER_DEVICE (mis. "cpu" kalau VRAM dipakai proses lain).
        # Model: bge-reranker-v2-m3 (multilingual) — recall RAG Indonesia jauh lebih baik.
        model = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        device = os.environ.get("RERANKER_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
        _reranker = CrossEncoder(model, device=device)
    return _reranker


def _chunk_markdown(text: str, target_size: int = 500, overlap: int = 100) -> list[dict]:
    if not text or not text.strip():
        return []

    section_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
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
    if not sections:
        sections = [("", text.strip())]

    chunks: list[dict] = []
    for heading, body in sections:
        if len(body) <= target_size:
            chunks.append({"heading": heading, "content": body})
            continue
        start = 0
        while start < len(body):
            end = min(start + target_size, len(body))
            if end < len(body):
                ws = body.rfind(" ", start, end)
                if ws > start + target_size // 2:
                    end = ws
            piece = body[start:end].strip()
            if piece:
                chunks.append({"heading": heading, "content": piece})
            if end >= len(body):
                break
            start = max(end - overlap, start + 1)
    return chunks


_NEW_SCHEMA_COLS = ("chunk_id", "heading", "mtime")


def _table_exists() -> bool:
    try:
        _get_db().open_table("vault")
        return True
    except Exception:
        return False


def _table_uses_new_schema() -> bool:
    if not _table_exists():
        return False
    try:
        df = _get_db().open_table("vault").to_pandas()
        return all(c in df.columns for c in _NEW_SCHEMA_COLS)
    except Exception:
        return False


def _drop_legacy_table_if_needed():
    if _table_exists() and not _table_uses_new_schema():
        try:
            _get_db().drop_table("vault")
            print("[ARSIP] Drop tabel skema lama (pre-chunking). Akan rebuild full.")
        except Exception as e:
            logger.warning(f"[ARSIP] Gagal drop tabel skema lama: {e}")


def _read_existing_mtime() -> dict:
    if not _table_uses_new_schema():
        return {}
    try:
        df = _get_db().open_table("vault").to_pandas()
        return df.groupby('path')['mtime'].max().to_dict()
    except Exception as e:
        logger.warning(f"[ARSIP] Gagal baca index existing: {e}")
        return {}


def _ensure_fts_index():
    try:
        tbl = _get_db().open_table("vault")
        tbl.create_fts_index("content", replace=True)
    except Exception as e:
        logger.warning(f"[ARSIP] FTS index ga tersedia (LanceDB versi lama?): {e}. Search akan dense-only.")


_bm25_index = None
_bm25_lock = threading.Lock()


def _document_embedding_text(filename: str, heading: str, content: str) -> str:
    """Teks yang di-embedding saat indexing: sertakan nama file + heading supaya
    query yang menyebut topik/judul lebih mudah menemukan bagian yang tepat."""
    return f"Document: {filename}\nSection: {heading}\nContent: {content}"


def _set_bm25_index(index) -> None:
    global _bm25_index
    with _bm25_lock:
        _bm25_index = index


def _get_bm25_index():
    """Cache BM25 di RAM; dimuat sekali, diinvalidasi lewat _set_bm25_index()
    setelah index_vault() membangun ulang. Kalau file hilang/rusak → None."""
    global _bm25_index
    if _bm25_index is None:
        with _bm25_lock:
            if _bm25_index is None:
                path = Path(__file__).parent.parent / "search_index" / "bm25.pkl"
                if path.exists():
                    from core.bm25_index import BM25Index
                    _bm25_index = BM25Index.load(path)
    return _bm25_index


def _index_vault_unlocked(full_rebuild: bool = False) -> None:
    vault = Path(OBSIDIAN_PATH)
    if not vault.exists():
        print(f"[ARSIP] Folder vault tidak ditemukan: {vault}")
        return

    _drop_legacy_table_if_needed()
    existing = {} if full_rebuild else _read_existing_mtime()
    new_docs: list[dict] = []
    paths_to_refresh: list[str] = []
    n_new, n_updated, n_skipped = 0, 0, 0

    for file in vault.rglob("*.md"):
        try:
            mtime = file.stat().st_mtime
            path_str = str(file)
            if path_str in existing and abs(existing[path_str] - mtime) < 1e-6:
                n_skipped += 1
                continue
            content = file.read_text(encoding="utf-8")
            if not content.strip():
                continue
            chunks = _chunk_markdown(content)
            if not chunks:
                continue
            for idx, ch in enumerate(chunks):
                embedding_text = _document_embedding_text(file.name, ch["heading"], ch["content"])
                vec = embedder.encode(embedding_text).tolist()
                new_docs.append({
                    "filename": file.name,
                    "path": path_str,
                    "chunk_id": idx,
                    "heading": ch["heading"],
                    "content": ch["content"],
                    "vector": vec,
                    "mtime": mtime,
                })
            if path_str in existing:
                paths_to_refresh.append(path_str)
                n_updated += 1
            else:
                n_new += 1
        except Exception as e:
            print(f"[ARSIP] Skip {file.name}: {e}")

    if full_rebuild:
        if not new_docs:
            print("[ARSIP] Vault kosong, full rebuild dibatalkan.")
            return
        try:
            _get_db().create_table("vault", data=new_docs, mode="overwrite")
            _rebuild_bm25_index()
            print(f"[ARSIP] Full rebuild selesai: {len(new_docs)} chunk.")
        except Exception as e:
            print(f"[ARSIP] Full rebuild gagal: {e}")
        return

    if not _table_exists():
        if not new_docs:
            print("[ARSIP] Vault kosong, belum ada catatan untuk diindex.")
            return
        try:
            _get_db().create_table("vault", data=new_docs, mode='overwrite')
            print(f"[ARSIP] {len(new_docs)} chunk dari {n_new} catatan berhasil diindex (full).")
            _rebuild_bm25_index()
        except Exception as e:
            print(f"[ARSIP] Gagal create tabel vault: {e}")
        return

    try:
        tbl = _get_db().open_table("vault")
        for p in paths_to_refresh:
            safe_p = p.replace("'", "''")
            try:
                tbl.delete(f"path = '{safe_p}'")
            except Exception as e:
                logger.warning(f"[ARSIP] Gagal delete chunks lama {p}: {e}")
        if new_docs:
            tbl.add(new_docs)
        print(f"[ARSIP] Re-index: {n_new} file baru, {n_updated} file diupdate, {n_skipped} file di-skip (unchanged).")
        _rebuild_bm25_index()
    except Exception as e:
        print(f"[ARSIP] Incremental update gagal: {e}")


def index_vault(full_rebuild: bool = False) -> None:
    with _index_lock:
        _index_vault_unlocked(full_rebuild)


def _rebuild_bm25_index():
    try:
        tbl = _get_db().open_table("vault")
        df = tbl.to_pandas()
        if not df.empty:
            items = []
            for _, row in df.iterrows():
                chunk = row['chunk_id'] if 'chunk_id' in row.index else 0
                items.append({
                    "id": f"{row['path']}::{chunk}",
                    "content": row['content']
                })
            from core.bm25_index import build_from_corpus
            bm25_idx = build_from_corpus(items)
            bm25_path = Path(os.path.dirname(__file__)) / "../search_index/bm25.pkl"
            bm25_idx.save(bm25_path)
            _set_bm25_index(bm25_idx)
            print(f"[ARSIP] BM25 index built and saved with {len(items)} items.")
    except Exception as e:
        print(f"[ARSIP] Gagal build BM25 index: {e}")



def _rrf_fuse(rankings: list[list[str]], k: int = 60) -> dict:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def _passes_relevance_gate(scores, threshold: float = 0.52) -> bool:
    """Gate berbasis skor reranker (logit -> sigmoid). Kalau kandidat terbaik pun
    di bawah ambang, retrieval dianggap tidak menemukan konteks yang relevan.
    Ambang 0.52 dipilih dari benchmark Vault: hit asli >=0.555, true-negative 0.500."""
    if len(scores) == 0:
        return False
    best = max(float(score) for score in scores)
    probability = 1.0 / (1.0 + math.exp(-best))
    return probability >= threshold


def _neighbor_chunk_ids(chunk_id: int) -> list[int]:
    return list(range(max(0, chunk_id - 1), chunk_id + 2))


def _fetch_neighbor_rows(tbl, row) -> list[dict]:
    """Ambil chunk tetangga (satu sebelum + satu sesudah) dari FILE yang sama
    sebagai konteks tambahan, tanpa menyeberang file."""
    chunk_id = int(row["chunk_id"])
    ids = _neighbor_chunk_ids(chunk_id)
    safe_path = str(row["path"]).replace("'", "''")
    condition = (
        f"path = '{safe_path}' AND chunk_id >= {ids[0]} "
        f"AND chunk_id <= {ids[-1]}"
    )
    frame = tbl.search().where(condition).limit(3).to_pandas()
    return frame.sort_values("chunk_id").to_dict("records")


def search_vault(query: str, top_k: int = 3) -> str:
    try:
        tbl = _get_db().open_table("vault")
    except Exception as e:
        logger.warning(f"[ARSIP] Tabel vault belum ada / tidak bisa dibuka: {e}")
        return "Vault belum diindex. Tidak ada catatan ditemukan."

    fetch_k = max(top_k * 3, 10)

    try:
        query_vec = embedder.encode_query(query).tolist()
        dense_df = tbl.search(query_vec).limit(fetch_k).to_pandas()
    except Exception as e:
        logger.error(f"[ARSIP] Dense search gagal: {e}", exc_info=True)
        return f"Pencarian vault gagal: {e}"

    def _doc_id(row) -> str:
        chunk = row['chunk_id'] if 'chunk_id' in row.index else 0
        return f"{row['path']}::{chunk}"

    bm25_hits = []
    bm25_idx = _get_bm25_index()
    if bm25_idx is not None:
        try:
            bm25_hits = bm25_idx.search(query, top_k=fetch_k)
        except Exception as e:
            logger.warning(f"[ARSIP] BM25 search gagal: {e}")

    vector_hits = []
    for _, r in dense_df.iterrows():
        dist = r.get('_distance', 0.0)
        score = 1.0 / (1.0 + dist)
        vector_hits.append((_doc_id(r), score))

    from core.bm25_index import hybrid_merge
    merged_hits = hybrid_merge(vector_hits, bm25_hits, w_vector=0.6, w_bm25=0.4, top_k=10)

    all_rows: dict = {}
    for _, r in dense_df.iterrows():
        all_rows[_doc_id(r)] = r

    for doc_id, _ in merged_hits:
        if doc_id not in all_rows:
            parts = doc_id.split("::")
            if len(parts) == 2:
                path_part, chunk_part = parts
                safe_path = path_part.replace("'", "''")
                try:
                    rows = tbl.search().where(f"path = '{safe_path}' AND chunk_id = {chunk_part}").limit(1).to_pandas()
                    if not rows.empty:
                        all_rows[doc_id] = rows.iloc[0]
                except Exception as e:
                    logger.warning(f"[ARSIP] Gagal query row {doc_id} dari DB: {e}")

    candidates = [all_rows[doc_id] for doc_id, _ in merged_hits if doc_id in all_rows]
    if not candidates:
        return "Tidak ada catatan relevan ditemukan di vault."

    gate_ok = True
    try:
        reranker = _get_reranker()
        pairs = [(query, str(c['content'])) for c in candidates]
        rerank_scores = reranker.predict(pairs)
        scored = sorted(zip(rerank_scores, candidates), key=lambda x: float(x[0]), reverse=True)
        top_scored = scored[:top_k]
        top = [c for _, c in top_scored]
        gate_ok = _passes_relevance_gate([s for s, _ in top_scored])
    except Exception as e:
        logger.warning(f"[ARSIP] Rerank gagal ({e}). Pakai urutan hybrid.")
        top = candidates[:top_k]

    if not gate_ok:
        return "Tidak ada catatan relevan ditemukan di vault."

    output: list[str] = []
    seen: set[tuple[str, int]] = set()
    remaining = 3000
    for primary in top:
        try:
            context_rows = _fetch_neighbor_rows(tbl, primary)
        except Exception as exc:
            logger.warning(f"[ARSIP] Neighbor lookup gagal: {exc}")
            context_rows = [primary.to_dict() if hasattr(primary, "to_dict") else primary]
        for row in context_rows:
            key = (str(row["path"]), int(row["chunk_id"]))
            if key in seen or remaining <= 0:
                continue
            seen.add(key)
            heading = str(row.get("heading", "") or "")
            label = f"File: {row['filename']}" + (f" / {heading}" if heading else "")
            block = f"{label}\n{str(row['content'])}"
            block = block[:remaining]
            output.append(block)
            remaining -= len(block)
    return "\n---\n".join(output)

# ============================================================
# Tool SIMPAN ke Vault (BARU!)
# ============================================================
_VAULT_CATEGORIES = {"Inbox", "Riset", "Proyek", "Personal", "Saham"}


def _normalize_category(value: object) -> str:
    if not isinstance(value, str):
        return "Inbox"
    category = value.strip().title()
    return category if category in _VAULT_CATEGORIES else "Inbox"


def _slug(value: str, limit: int = 100) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    if len(slug) <= limit:
        return slug
    suffix = hashlib.sha256(slug.encode("utf-8")).hexdigest()[:8]
    return f"{slug[:limit - 9].rstrip('-')}-{suffix}"


def _content_digest(content: str) -> str:
    normalized = " ".join(content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _atomic_write(filepath: Path, content: str) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=filepath.parent,
            prefix=f".{filepath.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, filepath)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _yaml_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _new_note(
    title: str,
    content: str,
    category: str,
    tags: list[str],
    source: str,
    digest: str,
    timestamp: str,
) -> str:
    return f"""---
title: {_yaml_value(title)}
created: {_yaml_value(timestamp)}
updated: {_yaml_value(timestamp)}
category: {_yaml_value(category)}
tags: {_yaml_value(tags)}
source: {_yaml_value(source)}
content_hash: {_yaml_value(digest)}
content_hashes: {_yaml_value([digest])}
---

# {title}

<!-- anisa:content-hash:{digest} -->

{content.strip()}
"""


def _split_frontmatter(content: str) -> tuple[str, str] | None:
    if not content.startswith("---\n"):
        return None
    frontmatter, separator, body = content[4:].partition("\n---\n")
    if not separator:
        return None
    return frontmatter, body


def _trusted_content_hashes(content: str) -> list[str]:
    split = _split_frontmatter(content)
    if split is None:
        return []
    frontmatter, _ = split
    hashes: list[str] = []
    for key in ("content_hash", "content_hashes"):
        match = re.search(rf"^{key}:\s*(.+)$", frontmatter, flags=re.MULTILINE)
        if match is None:
            continue
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            if (
                isinstance(item, str)
                and re.fullmatch(r"[0-9a-f]{64}", item)
                and item not in hashes
            ):
                hashes.append(item)
    return hashes


def _find_existing_note(
    vault_dir: Path, safe_title: str, digest: str
) -> tuple[Path | None, Path | None]:
    existing_note: Path | None = None
    for note in sorted(vault_dir.rglob("*.md")):
        old_content = note.read_text(encoding="utf-8", errors="ignore")
        if digest in _trusted_content_hashes(old_content):
            return note, existing_note
        if existing_note is None and _slug(note.stem) == safe_title:
            existing_note = note
    return None, existing_note


def _refresh_frontmatter(content: str, timestamp: str, digest: str) -> str:
    split = _split_frontmatter(content)
    if split is None:
        return content
    frontmatter, body = split
    hashes = _trusted_content_hashes(content)
    if digest not in hashes:
        hashes.append(digest)
    for key, value in (
        ("updated", timestamp),
        ("content_hash", digest),
        ("content_hashes", hashes),
    ):
        field = f"{key}: {_yaml_value(value)}"
        if re.search(rf"^{key}:.*$", frontmatter, flags=re.MULTILINE):
            frontmatter = re.sub(
                rf"^{key}:.*$", field, frontmatter, count=1, flags=re.MULTILINE
            )
        else:
            frontmatter = f"{frontmatter.rstrip()}\n{field}"
    return f"---\n{frontmatter}\n---\n{body}"


class VaultSaveTool(BaseTool):
    name: str = "Vault Save Tool"
    description: str = """Simpan catatan terorganisasi ke vault Obsidian Bima.
    Input wajib JSON: {"title":"...","content":"...","category":"Inbox|Riset|Proyek|Personal|Saham","tags":["..."],"source":"..."}.
    Category yang tidak valid otomatis menjadi Inbox."""

    def _run(self, input_json: str) -> str:
        try:
            try:
                data = json.loads(input_json)
            except (json.JSONDecodeError, TypeError):
                return "FAILED|JSON tidak valid."

            if not isinstance(data, dict):
                return "FAILED|Input harus objek JSON dengan field 'title' dan 'content'."

            title = data.get("title")
            content = data.get("content")
            if not isinstance(title, str) or not title.strip():
                return "FAILED|Field 'title' wajib string nonempty."
            if not isinstance(content, str) or not content.strip():
                return "FAILED|Field 'content' wajib string nonempty."
            title = title.strip()
            category = _normalize_category(data.get("category"))
            raw_tags = data.get("tags", [])
            tags: list[str] = []
            if isinstance(raw_tags, list):
                for item in raw_tags:
                    if not isinstance(item, str):
                        continue
                    tag = _slug(item)
                    if tag and tag not in tags:
                        tags.append(tag)
                    if len(tags) == 8:
                        break
            raw_source = data.get("source", "Bima")
            source = raw_source.strip()[:500] if isinstance(raw_source, str) else "Bima"
            source = source or "Bima"
            safe_title = _slug(title)
            if not safe_title:
                return "FAILED|Judul tidak menghasilkan nama file yang valid."

            vault_dir = Path(OBSIDIAN_PATH).resolve()
            filepath = (vault_dir / category / f"{safe_title}.md").resolve()
            try:
                filepath.relative_to(vault_dir)
            except ValueError:
                return "FAILED|Path target tidak aman."

            digest = _content_digest(content)
            timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
            with _vault_save_lock:
                vault_dir.mkdir(parents=True, exist_ok=True)
                duplicate_note, existing_note = _find_existing_note(
                    vault_dir, safe_title, digest
                )
                if duplicate_note is not None:
                    return (
                        f"SKIPPED|{duplicate_note}|"
                        "Konten yang sama sudah ada di vault."
                    )

                if existing_note is not None:
                    old_content = existing_note.read_text(encoding="utf-8", errors="ignore")
                    if backup_file(existing_note) is None:
                        return f"FAILED|Backup gagal; catatan lama tidak diubah: {existing_note}"
                    updated = _refresh_frontmatter(old_content, timestamp, digest).rstrip()
                    updated += (
                        f"\n\n## Update {timestamp}\n\n"
                        f"<!-- anisa:content-hash:{digest} -->\n\n{content.strip()}\n"
                    )
                    _atomic_write(existing_note, updated)
                    filepath = existing_note
                    status_msg = "update"
                else:
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    _atomic_write(
                        filepath,
                        _new_note(title, content, category, tags, source, digest, timestamp),
                    )
                    status_msg = "baru"

            try:
                index_vault()
            except Exception as e:
                logger.warning(f"[ARSIP] Re-index gagal setelah save: {e}")

            return f"SUCCESS|{filepath}|Data {status_msg} berhasil disimpan ke vault."
        except Exception as e:
            logger.error(f"[ARSIP] Gagal simpan ke vault: {e}")
            return "FAILED|Gagal simpan ke vault. Detail tersimpan di log lokal."

class VaultSearchTool(BaseTool):
    name: str = "Vault Search Tool"
    description: str = "Cari catatan di vault Obsidian pakai semantic search. Input: query string."

    def _run(self, query: str) -> str:
        return search_vault(query)

class VaultIndexTool(BaseTool):
    name: str = "Vault Index Tool"
    description: str = "Re-index semua catatan di vault. Gunakan kalau ada catatan baru."

    def _run(self, query: str = "") -> str:
        index_vault()
        return "Vault berhasil diindex ulang!"

def backup_file(filepath: Path) -> Path | None:
    backup_path: Path | None = None
    try:
        backup_dir = Path(__file__).parent.parent / "outputs" / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fd, backup_name = tempfile.mkstemp(
            prefix=f"{filepath.stem}_{timestamp}_",
            suffix=filepath.suffix,
            dir=backup_dir,
        )
        os.close(fd)
        backup_path = Path(backup_name)
        shutil.copyfile(filepath, backup_path)
        shutil.copystat(filepath, backup_path)
        logger.info(
            f"[LINKER] Backup dibuat untuk {filepath.name} -> {backup_path.name}"
        )
        return backup_path
    except Exception as e:
        if backup_path is not None:
            backup_path.unlink(missing_ok=True)
        logger.error(f"[LINKER] Gagal membuat backup file {filepath}: {e}")
        return None


_RELATED_START = "<!-- anisa:related:start -->"
_RELATED_END = "<!-- anisa:related:end -->"
_MARKED_RELATED = re.compile(
    re.escape(_RELATED_START) + r"[\s\S]*?" + re.escape(_RELATED_END)
)
# Blok "Catatan Terkait" lama tanpa marker yang isinya HANYA wiki link sampai
# akhir file — ini aman dibuang/migrasi. Konten manual (bukan wiki link) di
# bawah heading TIDAK cocok pola ini, jadi tidak akan terhapus.
_LEGACY_RELATED = re.compile(
    r"(?ms)\n*^#{2,3}\s+Catatan Terkait\s*$"
    r"(?:\n\s*-\s+\[\[[^\n]+\]\]\s*)+\Z"
)


def _replace_related_block(content: str, related_notes: list[str]) -> str:
    """Ganti HANYA blok "Catatan Terkait" milik Anisa (di antara marker), tanpa
    menyentuh konten manual di luar marker. Blok legacy link-only ikut dimigrasi."""
    lines = "\n".join(f"- [[{name}]]" for name in related_notes)
    block = f"{_RELATED_START}\n### Catatan Terkait\n{lines}\n{_RELATED_END}"
    if _MARKED_RELATED.search(content):
        return _MARKED_RELATED.sub(block, content, count=1)
    base = _LEGACY_RELATED.sub("", content).rstrip()
    return f"{base}\n\n{block}\n"


class VaultLinkerTool(BaseTool):
    name: str = "Vault Linker Tool"
    description: str = """Merapikan semua catatan di vault Obsidian Bima,
    menyisipkan internal wiki links [[Catatan]] antar catatan secara semantik,
    dan membersihkan spasi/baris kosong berlebih.
    Input: kosong atau deskripsi tindakan (tidak digunakan)."""

    def _run(self, query: str = "") -> str:
        vault_dir = Path(OBSIDIAN_PATH).resolve()
        if not vault_dir.exists():
            return f"FAILED|Folder vault tidak ditemukan: {vault_dir}"

        md_files = list(vault_dir.rglob("*.md"))
        if not md_files:
            return "SKIPPED|Tidak ada file markdown di vault untuk diproses."

        # Build maps
        title_map = {}
        path_map = {}
        for f in md_files:
            orig_title = f.stem
            if len(orig_title) < 3:
                continue
            title_map[orig_title.lower()] = orig_title
            clean_title_space = orig_title.lower().replace("_", " ").strip()
            if len(clean_title_space) >= 3:
                title_map[clean_title_space] = orig_title
            path_map[orig_title] = str(f)

        modified_count = 0
        total_links_added = 0

        # Pattern to split ignored blocks
        split_pattern = re.compile(
            r'(```[\s\S]*?```|`[^`\n]*?`|\[\[[\s\S]*?\]\]|\[[\s\S]*?\]\([\s\S]*?\)|<!--[\s\S]*?-->)',
            re.MULTILINE
        )

        for filepath in md_files:
            try:
                orig_content = filepath.read_text(encoding="utf-8", errors="ignore")
                content = orig_content
                
                # Normalize newlines
                content = content.replace("\r\n", "\n")

                # Parse existing links
                linked_in_note = set()
                existing_links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
                for link in existing_links:
                    clean_link = link.strip().lower().replace("_", " ")
                    if clean_link in title_map:
                        linked_in_note.add(title_map[clean_link])
                    elif link.strip() in path_map:
                        linked_in_note.add(link.strip())

                # Sort and filter keywords for this note
                current_title = filepath.stem
                current_titles = {current_title.lower(), current_title.lower().replace("_", " ").strip()}
                keywords_sorted = sorted([k for k in title_map.keys() if k not in current_titles], key=len, reverse=True)
                keywords_filtered = [k for k in keywords_sorted if len(k) >= 3]

                inline_links_added = 0
                if keywords_filtered:
                    pattern_str = r'\b(' + '|'.join(re.escape(k) for k in keywords_filtered) + r')\b'
                    kw_regex = re.compile(pattern_str, re.IGNORECASE)

                    def replace_func(match):
                        nonlocal inline_links_added
                        matched_text = match.group(0)
                        clean_match = matched_text.lower().strip()
                        target_title = title_map[clean_match]
                        
                        if target_title in linked_in_note:
                            return matched_text
                        
                        linked_in_note.add(target_title)
                        inline_links_added += 1
                        if matched_text == target_title:
                            return f"[[{target_title}]]"
                        else:
                            return f"[[{target_title}|{matched_text}]]"

                    chunks = split_pattern.split(content)
                    modified_chunks = False
                    for i in range(0, len(chunks), 2):
                        chunk = chunks[i]
                        new_chunk, count = kw_regex.subn(replace_func, chunk)
                        if count > 0:
                            chunks[i] = new_chunk
                            modified_chunks = True
                    
                    if modified_chunks:
                        content = "".join(chunks)

                # Get semantic related notes (vector search)
                related_notes = []
                try:
                    tbl = _get_db().open_table("vault")
                    query_vec = embedder.encode(content[:1000]).tolist()
                    df = tbl.search(query_vec).limit(8).to_pandas()
                    
                    seen_paths = {str(filepath.resolve())}
                    for _, row in df.iterrows():
                        p = str(Path(row['path']).resolve())
                        fname = row['filename']
                        t = Path(fname).stem
                        if p not in seen_paths and t not in linked_in_note:
                            seen_paths.add(p)
                            related_notes.append(t)
                            if len(related_notes) >= 3:
                                break
                except Exception as ex:
                    logger.debug(f"[LINKER] Skip semantic search for {filepath.name}: {ex}")

                # Segarkan blok "Catatan Terkait" HANYA di dalam marker Anisa;
                # konten manual di bawah marker tidak ikut terhapus.
                if related_notes:
                    content = _replace_related_block(content, related_notes)
                    inline_links_added += len(related_notes)

                # Organizer Formatting: Collapse blank lines & clean lines
                lines = [line.rstrip() for line in content.split("\n")]
                content = "\n".join(lines)
                content = re.sub(r'\n{3,}', '\n\n', content).strip() + "\n"

                # If content changed, save it
                if content != orig_content:
                    backup_file(filepath)
                    filepath.write_text(content, encoding="utf-8")
                    modified_count += 1
                    total_links_added += inline_links_added
            except Exception as e:
                logger.error(f"[LINKER] Gagal memproses file {filepath.name}: {e}")

        # Re-index vault
        if modified_count > 0:
            try:
                index_vault()
            except Exception as ex:
                logger.warning(f"[LINKER] Re-index gagal pasca link: {ex}")

        return f"SUCCESS|Vault Linker selesai. Memproses {len(md_files)} file, mengubah {modified_count} file, dan menyisipkan {total_links_added} links."

def _index_vault_safe():
    try:
        index_vault()
    except Exception as e:
        print(f"[ARSIP] ⚠️ Background index vault gagal: {e}")
    # Prewarm jalur retrieval biar query pertama tidak kena cold-start.
    try:
        embedder.encode_query("warmup")
        _get_reranker().predict([("warmup", "warmup")])
        _get_bm25_index()
    except Exception as e:
        logger.warning(f"[ARSIP] Prewarm retrieval gagal: {e}")


def start_vault_index_background():
    """Start vault indexing only after MCP subprocesses have finished forking."""
    threading.Thread(
        target=_index_vault_safe,
        daemon=True,
        name="arsip-index-startup",
    ).start()



arsip_agent = Agent(
    role='Chief Archivist & Memory Keeper',
    goal='Menyimpan, merapikan, dan mencari catatan di vault Obsidian Bima.',
    backstory="""Kamu adalah Mandor Database B.I.M.A Core.

    TUGAS UTAMA:
    1. SIMPAN data baru ke vault pakai VaultSaveTool
    2. CARI catatan lama pakai VaultSearchTool
    3. RE-INDEX vault pakai VaultIndexTool kalau perlu
    4. HUBUNGKAN & RAPIKAN catatan pakai VaultLinkerTool

    ATURAN WAJIB:
    - Kalau task description mengandung blok "DATA DARI TIM SEBELUMNYA" → kamu DILARANG panggil VaultSearchTool. Datanya sudah ada, langsung pakai VaultSaveTool.
    - Kalau diminta "simpan", "arsipkan", "catat" → LANGSUNG panggil VaultSaveTool.
    - Format input VaultSaveTool HARUS JSON: {"title":"...","content":"...","category":"Inbox|Riset|Proyek|Personal|Saham","tags":["..."],"source":"..."}
    - Pilih category dari allowlist sesuai isi catatan; kalau ragu pakai Inbox.
    - VaultSearchTool hanya dipakai kalau Bima eksplisit minta CARI di vault dan tidak ada data dari tim sebelumnya.
    - Hubungkan catatan menggunakan VaultLinkerTool jika Bima minta merapikan atau menyambungkan wiki link.
    - Jangan bilang "tidak bisa" — kamu PUNYA tool simpan!

    Kamu hafal semua catatan Bima dan selalu siap menyimpan yang baru.""",
    llm=arsip_llm,
    tools=[VaultSearchTool(), VaultIndexTool(), VaultSaveTool(), VaultLinkerTool()],
    allow_delegation=True,
    verbose=True
)
