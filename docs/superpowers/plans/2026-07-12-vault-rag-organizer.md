# Vault RAG and Organizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membuat Agen Arsip menyimpan catatan baru secara konsisten dan aman, sekaligus mencapai retrieval hangat 1–3 detik dengan konteks yang lebih relevan.

**Architecture:** LanceDB, Qwen3 Embedding, dan BGE reranker tetap dipakai. `VaultSaveTool` menjadi enforcement boundary untuk schema, folder, metadata, deduplikasi, dan update; node Arsip hanya menerima upstream dari `temp_data`. Retrieval disederhanakan menjadi dense + BM25 cache, maksimal 10 kandidat reranker, relevance gate, dan ekspansi chunk tetangga.

**Tech Stack:** Python 3.10+, CrewAI BaseTool, LangGraph, LanceDB, sentence-transformers, rank-bm25, pytest.

---

## File Map

- Modify: `teams/t3_arsip.py` — save organizer, BM25 cache, retrieval pipeline, linker aman, prewarm.
- Modify: `core/langgraph_nodes/arsip.py` — membedakan hasil spesialis dari pesan Manager.
- Modify: `core/langgraph_nodes/intent_classifier.py` — frasa Arsip natural.
- Modify: `core/embedder.py` — API query embedding dengan prompt Qwen3.
- Create: `tests/test_arsip_organizer.py` — schema, folder, deduplikasi, update, linker.
- Create: `tests/test_arsip_routing.py` — fast-path dan upstream routing.
- Create: `tests/test_vault_retrieval.py` — cache, kandidat, threshold, neighbor, fallback.
- Create: `scripts/benchmark_vault_rag.py` — latency p50/p95 dan Recall@3 lokal.
- Modify: `error_solutions.md` — tambahkan hasil final hanya jika muncul kendala teknis baru.

## Guardrails

- Jangan membaca atau mengubah `.env`.
- Jangan memindahkan atau menulis ulang 54 file Vault existing.
- Semua test file-system memakai `tmp_path`, bukan Vault OneDrive.
- Full rebuild hanya mengganti tabel turunan `vault_index/vault`; file Markdown sumber tetap utuh.
- Jangan stage perubahan user yang sudah ada di worktree.

### Task 1: Perbaiki routing Arsip sebelum menyentuh storage

**Files:**
- Create: `tests/test_arsip_routing.py`
- Modify: `core/langgraph_nodes/arsip.py:20-47`
- Modify: `core/langgraph_nodes/intent_classifier.py:20-27`

- [ ] **Step 1: Tulis test gagal untuk intent natural dan upstream eksplisit**

```python
from core.langgraph_nodes.intent_classifier import classify_intent


def test_vault_natural_search_routes_to_arsip() -> None:
    teams, confidence, _ = classify_intent(
        "apa isi catatan preferensi musikku?", False
    )
    assert teams == ["arsip"]
    assert confidence >= 0.85


def test_short_save_command_routes_to_arsip() -> None:
    teams, confidence, _ = classify_intent("catat ini dong", False)
    assert teams == ["arsip"]
    assert confidence >= 0.85
```

Tambahkan test helper murni setelah helper dibuat:

```python
from core.langgraph_nodes.arsip import _get_upstream_data


def test_manager_message_is_not_upstream_data() -> None:
    state = {
        "messages": [type("Msg", (), {"content": "Aku teruskan ke Arsip"})()],
        "temp_data": {},
    }
    assert _get_upstream_data(state) == ""


def test_intel_result_is_upstream_data() -> None:
    state = {
        "messages": [],
        "temp_data": {"last_search_result": "hasil riset terverifikasi"},
    }
    assert _get_upstream_data(state) == "hasil riset terverifikasi"
```

- [ ] **Step 2: Jalankan test dan pastikan gagal pada perilaku lama**

Run:

```bash
source bima_env/bin/activate
pytest -q tests/test_arsip_routing.py
```

Expected: intent natural belum menuju Arsip dan `_get_upstream_data` belum tersedia.

- [ ] **Step 3: Implementasikan helper upstream dan regex minimal**

Di `core/langgraph_nodes/arsip.py`:

```python
def _get_upstream_data(state: BimaState, limit: int = 3000) -> str:
    temp_data = state.get("temp_data", {}) or {}
    for key in ("last_search_result", "last_browser_result"):
        value = str(temp_data.get(key, "")).strip()
        if value:
            return value[:limit]
    return ""
```

Ganti pembacaan `prev_messages`, `upstream_text`, dan `search_raw` dengan:

```python
upstream_text = _get_upstream_data(state)
has_upstream = bool(upstream_text)
```

Di `core/langgraph_nodes/intent_classifier.py`:

```python
_VAULT_SAVE = re.compile(
    r"\b(simpan|catat|arsipkan)\b(?:.{0,50}\b(vault|obsidian|catatan)\b)?",
    re.IGNORECASE,
)
_VAULT_SEARCH = re.compile(
    r"\b(cari|apa\s+isi|buka|ingat)\b.{0,50}\b(vault|obsidian|catatan)\b"
    r"|\b(vault|obsidian|catatan)\b.{0,50}\b(cari|apa\s+isi|buka|ingat)\b",
    re.IGNORECASE,
)
```

Pastikan `_VAULT_SEARCH` diperiksa sebelum `_VAULT_SAVE` agar kalimat pencarian yang mengandung kata “catatan” tidak salah simpan.

- [ ] **Step 4: Jalankan test routing**

```bash
pytest -q tests/test_arsip_routing.py
```

Expected: seluruh test PASS.

- [ ] **Step 5: Commit hanya file Task 1**

```bash
git add tests/test_arsip_routing.py core/langgraph_nodes/arsip.py core/langgraph_nodes/intent_classifier.py
git commit -m "fix: route vault searches and upstream data safely"
```

### Task 2: Jadikan VaultSaveTool enforcement boundary

**Files:**
- Create: `tests/test_arsip_organizer.py`
- Modify: `teams/t3_arsip.py:336-410`
- Modify: `core/langgraph_nodes/arsip.py:39-43`

- [ ] **Step 1: Tulis test gagal untuk validasi, folder, metadata, dan deduplikasi**

```python
import json
from pathlib import Path

import teams.t3_arsip as arsip


def _disable_reindex(monkeypatch) -> None:
    monkeypatch.setattr(arsip, "index_vault", lambda: None)


def test_save_rejects_empty_content(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(arsip, "OBSIDIAN_PATH", str(tmp_path))
    _disable_reindex(monkeypatch)
    result = arsip.VaultSaveTool()._run(
        json.dumps({"title": "Kosong", "content": "   "})
    )
    assert result.startswith("FAILED|")
    assert not list(tmp_path.rglob("*.md"))


def test_invalid_category_falls_back_to_inbox(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(arsip, "OBSIDIAN_PATH", str(tmp_path))
    _disable_reindex(monkeypatch)
    payload = {
        "title": "Material Kayu Jati",
        "content": "Catatan material.",
        "category": "../../luar",
        "tags": ["Kayu Jati", "Furniture"],
        "source": "Bima",
    }
    result = arsip.VaultSaveTool()._run(json.dumps(payload))
    saved = tmp_path / "Inbox" / "material-kayu-jati.md"
    assert result.startswith("SUCCESS|")
    assert saved.exists()
    text = saved.read_text(encoding="utf-8")
    assert 'category: "Inbox"' in text
    assert 'tags: ["kayu-jati", "furniture"]' in text
    assert "<!-- anisa:content-hash:" in text


def test_same_content_is_skipped_globally(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(arsip, "OBSIDIAN_PATH", str(tmp_path))
    _disable_reindex(monkeypatch)
    tool = arsip.VaultSaveTool()
    first = {"title": "Kursi A", "content": "Isi identik", "category": "Proyek"}
    second = {"title": "Nama Lain", "content": "Isi identik", "category": "Riset"}
    assert tool._run(json.dumps(first)).startswith("SUCCESS|")
    assert tool._run(json.dumps(second)).startswith("SKIPPED|")
    assert len(list(tmp_path.rglob("*.md"))) == 1


def test_same_title_appends_update_after_backup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(arsip, "OBSIDIAN_PATH", str(tmp_path))
    _disable_reindex(monkeypatch)
    backups: list[Path] = []
    monkeypatch.setattr(arsip, "backup_file", lambda path: backups.append(path))
    tool = arsip.VaultSaveTool()
    tool._run(json.dumps({"title": "BIMA Core", "content": "Versi awal"}))
    result = tool._run(json.dumps({"title": "BIMA Core", "content": "Versi baru"}))
    files = list(tmp_path.rglob("*.md"))
    assert result.startswith("SUCCESS|")
    assert len(files) == 1
    assert backups == [files[0]]
    assert "## Update " in files[0].read_text(encoding="utf-8")


def test_atomic_update_failure_keeps_old_file(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "note.md"
    path.write_text("isi lama", encoding="utf-8")
    monkeypatch.setattr(arsip.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("disk")))
    try:
        arsip._atomic_write(path, "isi baru")
    except OSError:
        pass
    assert path.read_text(encoding="utf-8") == "isi lama"
    assert not (tmp_path / "note.md.tmp").exists()
```

- [ ] **Step 2: Jalankan test dan pastikan gagal**

```bash
pytest -q tests/test_arsip_organizer.py
```

Expected: folder kategori, YAML, hash global, dan update file belum tersedia.

- [ ] **Step 3: Tambahkan helper organizer minimal di `teams/t3_arsip.py`**

```python
import hashlib

VAULT_CATEGORIES = {"Inbox", "Riset", "Proyek", "Personal", "Saham"}
_CONTENT_HASH_RE = re.compile(r"<!-- anisa:content-hash:([0-9a-f]{64}) -->")
_vault_save_lock = threading.Lock()


def _slug_words(value: str) -> str:
    words = re.findall(r"\w+", value.lower(), flags=re.UNICODE)
    return "-".join(words)[:100]


def _slugify(value: str) -> str:
    return _slug_words(value) or f"catatan-{datetime.now():%Y%m%d-%H%M%S}"


def _normalize_category(value: object) -> str:
    category = str(value or "Inbox").strip().title()
    return category if category in VAULT_CATEGORIES else "Inbox"


def _normalize_tags(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        tag = _slug_words(str(item))
        if tag and tag not in tags:
            tags.append(tag)
        if len(tags) == 8:
            break
    return tags


def _content_digest(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _find_existing_note(vault_dir: Path, slug: str, digest: str) -> tuple[Path | None, Path | None]:
    same_title = None
    duplicate = None
    marker = f"<!-- anisa:content-hash:{digest} -->"
    for path in vault_dir.rglob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if marker in text:
            duplicate = path
            break
        if _slug_words(path.stem) == slug:
            same_title = path
    return same_title, duplicate


def _refresh_frontmatter(text: str, timestamp: str, digest: str) -> str:
    if not text.startswith("---\n"):
        return text
    text = re.sub(
        r"(?m)^updated:.*$",
        f"updated: {json.dumps(timestamp)}",
        text,
        count=1,
    )
    return re.sub(
        r"(?m)^content_hash:.*$",
        f"content_hash: {json.dumps(digest)}",
        text,
        count=1,
    )
```

- [ ] **Step 4: Ganti isi `VaultSaveTool._run()` dengan alur tervalidasi**

Implementasi wajib mengikuti urutan ini:

```python
data = json.loads(input_json)
if not isinstance(data, dict):
    return "FAILED|Input harus objek JSON."
title = data.get("title")
content = data.get("content")
if not isinstance(title, str) or not title.strip():
    return "FAILED|Field 'title' wajib berupa string nonkosong."
if not isinstance(content, str) or not content.strip():
    return "FAILED|Field 'content' wajib berupa string nonkosong."

title = title.strip()
content = content.strip()
category = _normalize_category(data.get("category"))
tags = _normalize_tags(data.get("tags"))
source = str(data.get("source") or "Bima").strip()[:500]
slug = _slugify(title)
digest = _content_digest(content)
vault_dir = Path(OBSIDIAN_PATH).resolve()
target_dir = (vault_dir / category).resolve()
target_dir.relative_to(vault_dir)
target_dir.mkdir(parents=True, exist_ok=True)
same_title, duplicate = _find_existing_note(vault_dir, slug, digest)
if duplicate is not None:
    return f"SKIPPED|{duplicate}|Konten identik sudah ada."

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB")
marker = f"<!-- anisa:content-hash:{digest} -->"
if same_title is not None:
    backup_file(same_title)
    old = same_title.read_text(encoding="utf-8", errors="strict").rstrip()
    old = _refresh_frontmatter(old, timestamp, digest)
    updated = f"{old}\n\n## Update {timestamp}\n\n{marker}\n{content}\n"
    _atomic_write(same_title, updated)
    filepath = same_title
    status_msg = "diperbarui"
else:
    filepath = target_dir / f"{slug}.md"
    tags_json = json.dumps(tags, ensure_ascii=False)
    markdown_content = (
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"created: {json.dumps(timestamp)}\n"
        f"updated: {json.dumps(timestamp)}\n"
        f"category: {json.dumps(category)}\n"
        f"tags: {tags_json}\n"
        f"source: {json.dumps(source, ensure_ascii=False)}\n"
        f"content_hash: {json.dumps(digest)}\n"
        "---\n\n"
        f"# {title}\n\n{marker}\n{content}\n"
    )
    _atomic_write(filepath, markdown_content)
    status_msg = "baru"
```

Sesudah write berhasil, panggil `index_vault()` dalam blok error nonfatal yang sudah ada. Tangkap `json.JSONDecodeError`, `OSError`, dan error tak terduga menjadi status `FAILED|...` tanpa stack trace ke user.

Seluruh urutan `_find_existing_note()` sampai `_atomic_write()` berjalan di dalam `with _vault_save_lock:` agar request Discord/WhatsApp bersamaan tidak membuat duplikat.

- [ ] **Step 5: Perbarui schema pada description dan prompt agen**

Gunakan satu contoh konsisten:

```json
{"title":"...","content":"...","category":"Inbox|Riset|Proyek|Personal|Saham","tags":["..."],"source":"..."}
```

Instruksikan agen memilih kategori allowlist dan memakai `Inbox` saat ragu. Enforcement tetap berada di tool.

Di `core/langgraph_nodes/arsip.py`, contoh `VaultSaveTool` untuk data upstream wajib memakai schema yang sama dan mengisi `source` dengan `Intel` atau `Visual` sesuai field `temp_data` yang tersedia.

- [ ] **Step 6: Jalankan test organizer**

```bash
pytest -q tests/test_arsip_organizer.py
```

Expected: seluruh test PASS dan tidak ada file di luar `tmp_path`.

- [ ] **Step 7: Commit Task 2**

```bash
git add teams/t3_arsip.py tests/test_arsip_organizer.py
git commit -m "feat: enforce organized vault saves"
```

### Task 3: Amankan blok Catatan Terkait

**Files:**
- Modify: `tests/test_arsip_organizer.py`
- Modify: `teams/t3_arsip.py:535-566`

- [ ] **Step 1: Tambahkan test gagal untuk preservasi konten manual**

```python
def test_related_block_replacement_preserves_manual_tail() -> None:
    original = (
        "# Catatan\n\nIsi\n\n"
        "<!-- anisa:related:start -->\n"
        "### Catatan Terkait\n- [[Lama]]\n"
        "<!-- anisa:related:end -->\n\n"
        "## Lampiran Manual\nJangan hapus ini.\n"
    )
    result = arsip._replace_related_block(original, ["Baru"])
    assert "[[Lama]]" not in result
    assert "[[Baru]]" in result
    assert "## Lampiran Manual\nJangan hapus ini." in result


def test_unmarked_manual_related_section_is_not_deleted() -> None:
    original = "# Catatan\n\n### Catatan Terkait\nKomentar manual Bima.\n"
    result = arsip._replace_related_block(original, ["Baru"])
    assert "Komentar manual Bima." in result
    assert "<!-- anisa:related:start -->" in result
```

- [ ] **Step 2: Jalankan dua test baru dan pastikan gagal**

```bash
pytest -q tests/test_arsip_organizer.py -k related
```

Expected: `_replace_related_block` belum tersedia.

- [ ] **Step 3: Implementasikan pengganti blok marker**

```python
_RELATED_START = "<!-- anisa:related:start -->"
_RELATED_END = "<!-- anisa:related:end -->"
_LEGACY_RELATED = re.compile(
    r"(?ms)\n*^#{2,3}\s+Catatan Terkait\s*$"
    r"(?:\n\s*-\s+\[\[[^\n]+\]\]\s*)+\Z"
)


def _replace_related_block(content: str, related_notes: list[str]) -> str:
    lines = "\n".join(f"- [[{name}]]" for name in related_notes)
    block = f"{_RELATED_START}\n### Catatan Terkait\n{lines}\n{_RELATED_END}"
    marked = re.compile(
        re.escape(_RELATED_START) + r"[\s\S]*?" + re.escape(_RELATED_END)
    )
    if marked.search(content):
        return marked.sub(block, content, count=1)
    base = _LEGACY_RELATED.sub("", content).rstrip()
    return f"{base}\n\n{block}\n"
```

Di `VaultLinkerTool`, hapus regex yang memotong dari heading sampai EOF. Setelah `related_notes` dihitung, selalu panggil `_replace_related_block(content, related_notes)`. Jika daftar kosong, gunakan `[]` agar marker tetap deterministik tanpa wiki link palsu.

- [ ] **Step 4: Jalankan organizer tests**

```bash
pytest -q tests/test_arsip_organizer.py
```

Expected: seluruh test PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add teams/t3_arsip.py tests/test_arsip_organizer.py
git commit -m "fix: preserve manual vault content during linking"
```

### Task 4: Optimalkan retrieval tanpa mengganti database

**Files:**
- Create: `tests/test_vault_retrieval.py`
- Modify: `core/embedder.py:87-96`
- Modify: `teams/t3_arsip.py:60-334`

- [ ] **Step 1: Tulis test gagal untuk query prompt Qwen3**

```python
from core.embedder import Embedder


def test_local_arsip_query_uses_qwen_query_prompt(monkeypatch) -> None:
    embedder = Embedder("arsip")
    calls: list[dict] = []

    class FakeModel:
        def encode(self, text, **kwargs):
            calls.append({"text": text, **kwargs})
            return [0.0, 1.0]

    monkeypatch.setattr(embedder, "_get_local", lambda: FakeModel())
    embedder.backend = "local"
    embedder.encode_query("preferensi musik")
    assert calls == [{"text": "preferensi musik", "prompt_name": "query"}]
```

- [ ] **Step 2: Implementasikan API query embedding**

Di `core/embedder.py`:

```python
def encode_query(self, text: str) -> np.ndarray:
    if self.backend == "local" and self.domain == "arsip":
        return self._get_local().encode(text, prompt_name="query")
    return self.encode(text)
```

Pemanggil dokumen tetap memakai `encode()`; hanya query Arsip memakai `encode_query()`.

- [ ] **Step 3: Tulis test retrieval dengan fake table/embedder/reranker**

Test wajib membuktikan:

```python
def test_contextual_embedding_text() -> None:
    text = arsip._document_embedding_text("Preferensi.md", "Musik", "Suka jazz")
    assert text == "Document: Preferensi.md\nSection: Musik\nContent: Suka jazz"


def test_relevance_gate_rejects_weak_scores() -> None:
    assert arsip._passes_relevance_gate([-4.0, -5.0]) is False
    assert arsip._passes_relevance_gate([0.0, -5.0]) is True


def test_neighbor_ids_stay_in_same_file() -> None:
    assert arsip._neighbor_chunk_ids(0) == [0, 1]
    assert arsip._neighbor_chunk_ids(3) == [2, 3, 4]
```

Tambahkan fake BM25 loader untuk memanggil `_get_bm25_index()` dua kali dan assert loader hanya sekali; setelah `_set_bm25_index(new_index)`, assert cache mengembalikan object baru.

- [ ] **Step 4: Jalankan retrieval tests dan pastikan gagal**

```bash
pytest -q tests/test_vault_retrieval.py
```

Expected: helper retrieval dan cache belum tersedia.

- [ ] **Step 5: Implementasikan contextual document text dan BM25 cache**

Di `teams/t3_arsip.py`:

```python
_bm25_index = None
_bm25_lock = threading.Lock()


def _document_embedding_text(filename: str, heading: str, content: str) -> str:
    return f"Document: {filename}\nSection: {heading}\nContent: {content}"


def _set_bm25_index(index) -> None:
    global _bm25_index
    with _bm25_lock:
        _bm25_index = index


def _get_bm25_index():
    global _bm25_index
    if _bm25_index is None:
        with _bm25_lock:
            if _bm25_index is None:
                path = Path(__file__).parent.parent / "search_index" / "bm25.pkl"
                if path.exists():
                    from core.bm25_index import BM25Index
                    _bm25_index = BM25Index.load(path)
    return _bm25_index
```

Saat indexing, ganti input embedding menjadi:

```python
embedding_text = _document_embedding_text(file.name, ch["heading"], ch["content"])
vec = embedder.encode(embedding_text).tolist()
```

Sesudah BM25 dibangun dan disimpan, panggil `_set_bm25_index(bm25_idx)`.

Tambahkan parameter rebuild tanpa menghapus folder:

```python
def index_vault(full_rebuild: bool = False) -> None:
    vault = Path(OBSIDIAN_PATH)
    if not vault.exists():
        print(f"[ARSIP] Folder vault tidak ditemukan: {vault}")
        return
    _drop_legacy_table_if_needed()
    existing = {} if full_rebuild else _read_existing_mtime()
```

Setelah semua `new_docs` terkumpul dan sebelum branch incremental:

```python
if full_rebuild:
    if not new_docs:
        print("[ARSIP] Vault kosong, full rebuild dibatalkan.")
        return
    _get_db().create_table("vault", data=new_docs, mode="overwrite")
    _rebuild_bm25_index()
    print(f"[ARSIP] Full rebuild selesai: {len(new_docs)} chunk.")
    return
```

- [ ] **Step 6: Sederhanakan `search_vault()`**

Perubahan wajib:

```python
fetch_k = max(top_k * 3, 10)
query_vec = embedder.encode_query(query).tolist()
dense_df = tbl.search(query_vec).limit(fetch_k).to_pandas()
bm25_idx = _get_bm25_index()
bm25_hits = bm25_idx.search(query, top_k=fetch_k) if bm25_idx else []
merged_hits = hybrid_merge(
    vector_hits,
    bm25_hits,
    w_vector=0.6,
    w_bm25=0.4,
    top_k=10,
)
```

Hapus pemanggilan `query_type="fts"` dan jangan membuat ulang FTS dalam `index_vault()`. Reranker menerima paling banyak 10 kandidat unik.

Tambahkan relevance helper menggunakan sigmoid logit:

```python
def _passes_relevance_gate(scores, threshold: float = 0.2) -> bool:
    if len(scores) == 0:
        return False
    best = max(float(score) for score in scores)
    probability = 1.0 / (1.0 + math.exp(-best))
    return probability >= threshold


def _neighbor_chunk_ids(chunk_id: int) -> list[int]:
    return list(range(max(0, chunk_id - 1), chunk_id + 2))


def _fetch_neighbor_rows(tbl, row) -> list[dict]:
    chunk_id = int(row["chunk_id"])
    ids = _neighbor_chunk_ids(chunk_id)
    safe_path = str(row["path"]).replace("'", "''")
    condition = (
        f"path = '{safe_path}' AND chunk_id >= {ids[0]} "
        f"AND chunk_id <= {ids[-1]}"
    )
    frame = tbl.search().where(condition).limit(3).to_pandas()
    return frame.sort_values("chunk_id").to_dict("records")
```

Jika gate gagal, return `"Tidak ada catatan relevan ditemukan di vault."`. Bangun keluaran tetangga dengan batas keras:

```python
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
        heading = str(row.get("heading", ""))
        label = f"File: {row['filename']}" + (f" / {heading}" if heading else "")
        block = f"{label}\n{str(row['content'])}"
        block = block[:remaining]
        output.append(block)
        remaining -= len(block)
return "\n---\n".join(output)
```

- [ ] **Step 7: Tambahkan prewarm dalam thread startup existing**

Sesudah `index_vault()` di `_index_vault_safe()`:

```python
embedder.encode_query("warmup")
_get_reranker().predict([("warmup", "warmup")])
_get_bm25_index()
```

Tangkap error prewarm sebagai warning; jangan membuat thread/service baru.

- [ ] **Step 8: Jalankan seluruh test retrieval dan regresi hybrid**

```bash
pytest -q tests/test_vault_retrieval.py tests/test_hybrid_rag.py
```

Expected: seluruh test PASS; baseline `test_hybrid_rag.py` tetap 27 PASS.

- [ ] **Step 9: Commit Task 4**

```bash
git add core/embedder.py teams/t3_arsip.py tests/test_vault_retrieval.py
git commit -m "perf: improve vault retrieval speed and relevance"
```

### Task 5: Benchmark, rebuild derived index, dan verifikasi akhir

**Files:**
- Create: `scripts/benchmark_vault_rag.py`
- Modify: `error_solutions.md` hanya jika ada error nontrivial baru.

- [ ] **Step 1: Buat benchmark dengan query sumber nyata**

Script harus memakai kasus berikut:

```python
CASES = [
    ("apa preferensi musik Bima", "Preferensi_Musik_Bima.md"),
    ("jelaskan arsitektur BIMA Core", "BIMA_CORE_Arsitektur.md"),
    ("berapa harga robux di Itemku", "Harga_Robux_Itemku_-_9_Mei_2026.md"),
    ("kriteria laptop Bima", "Kriteria_Laptop_Bima_-_6_Mei_2026.md"),
    ("resep ramen tonkotsu keluarga Bima", None),
]
```

Untuk tiap query: satu warmup global, tiga pengukuran `time.perf_counter()`, ekstrak baris `File:`, hit bila expected filename ada pada top-3, dan true-negative bila expected `None` menghasilkan pesan tidak ditemukan. Cetak p50, p95, Recall@3, dan true-negative rate. Exit 1 bila p95 > 3 detik, Recall@3 < 1.0, atau true-negative rate < 1.0.

- [ ] **Step 2: Jalankan syntax dan unit tests sebelum rebuild**

```bash
python -m py_compile teams/t3_arsip.py core/embedder.py core/langgraph_nodes/arsip.py core/langgraph_nodes/intent_classifier.py scripts/benchmark_vault_rag.py
pytest -q tests/test_arsip_routing.py tests/test_arsip_organizer.py tests/test_vault_retrieval.py tests/test_hybrid_rag.py
```

Expected: compile exit 0 dan seluruh test PASS. Jika gagal, berhenti dan laporkan tanpa auto-patch.

- [ ] **Step 3: Backup tabel turunan lalu full rebuild**

Plan approval menjadi izin untuk mengganti indeks turunan, bukan file Markdown. Gunakan export tabel sebelum overwrite:

```bash
python -c "import lancedb; from pathlib import Path; out=Path('outputs/backup/vault-index-before-rag-20260712.parquet'); out.parent.mkdir(parents=True, exist_ok=True); db=lancedb.connect('vault_index'); db.open_table('vault').to_pandas().to_parquet(out)"
python -c "from teams.t3_arsip import index_vault; index_vault(full_rebuild=True)"
```

`index_vault(full_rebuild: bool = False)` harus memakai `mode="overwrite"` saat `full_rebuild=True`, lalu membangun BM25 ulang. Jangan menghapus folder `vault_index`.

- [ ] **Step 4: Jalankan benchmark hangat**

```bash
python scripts/benchmark_vault_rag.py
```

Expected: p95 <= 3.0 detik, Recall@3 = 1.0, true-negative rate = 1.0. Jika salah satu gagal, berhenti dan laporkan angka aktual; jangan mengubah threshold/model otomatis.

- [ ] **Step 5: Jalankan full regression**

```bash
pytest -q
```

Expected: seluruh suite PASS. Jika ada baseline failure di file tidak terkait, laporkan file/test dan bedakan dari regresi task.

- [ ] **Step 6: Periksa diff dan source Vault**

```bash
git diff --check
git status --short
python -c "from pathlib import Path; p=Path(r'/mnt/c/Users/shint/OneDrive/Dokumen/BIMA_VAULT/Penyimpanan'); print(sum(1 for _ in p.rglob('*.md')))"
```

Expected: tidak ada whitespace error; jumlah Markdown existing tetap 54 sebelum user membuat catatan baru; tidak ada file Vault yang dimodifikasi oleh test/rebuild.

- [ ] **Step 7: Catat error nontrivial bila ada, lalu commit benchmark**

```bash
git add scripts/benchmark_vault_rag.py
git commit -m "test: benchmark vault retrieval quality and latency"
```

Jangan stage `error_solutions.md` karena file itu sudah memiliki perubahan user; laporkan bila log baru ditambahkan tetapi biarkan uncommitted.

## Final Acceptance

- [ ] Save selalu tervalidasi dan hanya menuju lima folder allowlist.
- [ ] Konten identik tidak menghasilkan file baru.
- [ ] Judul sama diperbarui setelah backup tanpa overwrite isi lama.
- [ ] Pesan Manager tidak pernah dianggap data Intel.
- [ ] Linker tidak menghapus konten manual.
- [ ] Retrieval hangat p95 <= 3 detik.
- [ ] Recall@3 dan true-negative benchmark masing-masing 100% pada lima kasus penerimaan.
- [ ] Full pytest tidak memiliki regresi baru.
