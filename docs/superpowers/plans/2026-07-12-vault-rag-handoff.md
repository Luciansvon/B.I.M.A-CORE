# Vault RAG & Organizer — Handoff (lanjutan kerja Codex)

> **Status per 2026-07-12:** Task 1–5 SELESAI + ter-commit di branch `vault-rag-organizer` (12 commit di atas main). Benchmark hangat LOLOS: p95 **2882 ms**, Recall@3 **1.00**, true-negative **1.00**. Full pytest: 293 passed; 6 failed HANYA di `test_slide_generator.py` (renderer node, PRE-EXISTING — sama persis di main, bukan regresi vault-rag).
>
> **✅ SUDAH MERGE + DEPLOY (2026-07-12).** Fast-forward ke `main` (HEAD `3a2552a`; perubahan user uncommitted tetap utuh). Indeks live di-backup → `outputs/backup/vault-index-before-rag-20260712.parquet` (897 rows), lalu di-rebuild (897 chunk, skema baru). `anisa-v3` restart: reranker load **cuda:0** + `[WARMUP] Cross-encoder reranker siap` TANPA OOM (F5-TTS mati). Bot online stabil (restarts=1, `/api/metrics` 200). Semua langkah DEPLOY di bawah ✅.

## Di mana kodenya

- **Branch:** `vault-rag-organizer` — 12 commit bersih di atas `main` (merge-base = tip main `9f61800`).
- **Worktree:** `/home/bima_lucian/.config/superpowers/worktrees/BIMA_CORE/vault-rag-organizer` (Windows: `\\wsl.localhost\Ubuntu\...`).
- Kerjaan ini **TIDAK ada di working tree `main`**. Cek: `git log --oneline main..vault-rag-organizer`.
- Plan: [2026-07-12-vault-rag-organizer.md](2026-07-12-vault-rag-organizer.md) · Spec: [../specs/2026-07-12-vault-rag-speed-quality-design.md](../specs/2026-07-12-vault-rag-speed-quality-design.md)

## Yang selesai (per task)

- **Task 1 — routing + negasi.** `core/langgraph_nodes/arsip.py`, `intent_classifier.py`. Test `tests/test_arsip_routing.py` (15 kasus negasi balik ke Manager).
- **Task 2 — VaultSaveTool enforcement.** `teams/t3_arsip.py` (allowlist kategori, slug, content-hash dedup, atomic write fsync, update=backup+append, lock). Test `tests/test_arsip_organizer.py`.
- **Task 3 — linker aman.** Commit `61d54b8`. `_replace_related_block()` + marker `anisa:related:start/end` + migrasi legacy. Konten manual tidak terhapus.
- **Task 4 — optimasi retrieval.** Commit `8a42a5f`. `encode_query()` (Qwen3 query prompt), contextual embedding, cache BM25 RAM, relevance gate, neighbor expansion, buang FTS, `index_vault(full_rebuild=)`, prewarm. Test `tests/test_vault_retrieval.py`.
- **Task 5 — benchmark + tuning.** Commit `3a2552a`. `scripts/benchmark_vault_rag.py`. Reranker default **GPU** (F5-TTS mati → VRAM cukup; rerank 10 kandidat ~4770ms CPU → ~980ms GPU), override `RERANKER_DEVICE`. Gate threshold **0.52** (dari benchmark: hit ≥0.555, true-neg 0.500). p95 2882ms.

## DEPLOY (langkah live — belum dijalankan, keputusan Bima)

Perubahan Task 4 mengganti skema embedding → indeks live WAJIB di-rebuild BARENG deploy kode, kalau tidak query vs dokumen mismatch. Urutan aman:

1. Merge/rebase `vault-rag-organizer` ke `main`.
2. Backup indeks turunan live dulu:
   `python -c "import lancedb; from pathlib import Path; o=Path('outputs/backup/vault-index-before-rag-20260712.parquet'); o.parent.mkdir(parents=True,exist_ok=True); lancedb.connect('vault_index').open_table('vault').to_pandas().to_parquet(o)"`
3. Rebuild indeks LIVE (dari main, ini yang overwrite `/home/bima_lucian/BIMA_CORE/vault_index`):
   `python -c "from teams.t3_arsip import index_vault; index_vault(full_rebuild=True)"`
4. Restart `anisa-v3` (pm2). Pastikan **F5-TTS tetap disabled** (reranker sekarang pakai GPU; kalau F5-TTS nyala lagi, set `RERANKER_DEVICE=cpu` atau atur VRAM).
5. Smoke test: query vault natural + cek latency wajar.

Catatan: config env resolve `OBSIDIAN_PATH` ke vault asli `/mnt/c/Users/shint/OneDrive/Dokumen/BIMA_VAULT/Penyimpanan` (via `.env` main); di lingkungan ini `OBSIDIAN_PATH` sempat fallback ke `Bima_Vault` kosong, jadi saat rebuild manual pastikan env-nya benar.

## Cara jalanin test / benchmark (venv di repo main)

```bash
cd /home/bima_lucian/.config/superpowers/worktrees/BIMA_CORE/vault-rag-organizer
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest tests/test_arsip_routing.py tests/test_arsip_organizer.py tests/test_vault_retrieval.py tests/test_hybrid_rag.py -q
# benchmark (butuh indeks sudah dibangun + OBSIDIAN_PATH ke vault asli):
env OBSIDIAN_PATH=/mnt/c/Users/shint/OneDrive/Dokumen/BIMA_VAULT/Penyimpanan \
  /home/bima_lucian/BIMA_CORE/bima_env/bin/python scripts/benchmark_vault_rag.py
```

## Gotcha lingkungan

- Git worktree dari path Windows → `dubious ownership`. Pakai `wsl.exe -d Ubuntu bash -lc 'git -C <linux-path> ...'`.
- `wsl.exe bash -lc '...'` multi-baris: assignment variabel kadang ke-mangle kosong → pakai path absolut penuh, atau `env VAR=... cmd`.
- Pipe `python ... | grep` MENYEMBUNYIKAN exit code python (jadi 0 palsu). Buat cek verdict, redirect ke file lalu `echo $?`.
- Worktree tidak punya `.env` → `OBSIDIAN_PATH` fallback ke folder kosong; embedder/reranker lokal jadi tidak butuh API key.

## Aturan yang dipegang

- TDD, commit per task, hanya file milik task-nya. Perubahan user lain di worktree TIDAK disentuh/di-stage.
- Rebuild indeks LIVE = destruktif, wajib izin + backup parquet. Sumber Markdown 54 file tidak boleh diubah.
