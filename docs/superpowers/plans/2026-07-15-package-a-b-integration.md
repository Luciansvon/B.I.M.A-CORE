# Package A + B Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tambahkan format Obsidian Base/Canvas, analitik DuckDB read-only, dan pemindaian Strix terisolasi; lalu dokumentasikan, verifikasi, commit, dan push.

**Architecture:** Arsip menulis file Obsidian tervalidasi ke vault OneDrive, Admin menganalisis CSV/Parquet melalui API terstruktur DuckDB, dan Mekanik menjalankan Strix terhadap snapshot source tersaring dalam Docker. Strix hanya menghasilkan report dan tidak menyentuh working tree.

**Tech Stack:** Python 3.10+ BIMA_CORE, CrewAI `BaseTool`, Pydantic, DuckDB 1.5.4, uv/uvx, Strix 1.1.0, Docker, pytest, Ruff, PM2.

**Status:** Implemented and verified on 2026-07-15. Strix end-to-end remains gated by the missing Docker CLI/daemon; its safe preflight and wrapper tests pass.

---

## Task 1: Rekam baseline dan tambah test Obsidian yang gagal

**Files:**
- Create: `tests/test_obsidian_formats.py`
- Inspect: `teams/t3_arsip.py`
- Inspect: `tools/__init__.py`

- [ ] Simpan `git status --short`, branch, dan diff file yang akan disentuh agar perubahan lama milik Bima tidak ikut ter-stage.
- [ ] Tulis test temp-vault untuk pembuatan `.base` valid, view allowlist, penolakan traversal, dan penolakan overwrite.
- [ ] Tulis test `.canvas` untuk note yang ada, ID 16-hex unik, edge valid, penolakan note hilang, traversal, dan overwrite.
- [ ] Jalankan `bima_env/bin/pytest tests/test_obsidian_formats.py -q` dan pastikan gagal karena modul belum ada.

## Task 2: Implementasi format Obsidian minimal

**Files:**
- Create: `tools/obsidian_formats.py`
- Modify: `teams/t3_arsip.py`
- Test: `tests/test_obsidian_formats.py`

- [ ] Implementasikan resolver vault/path yang menolak target di luar `OBSIDIAN_PATH`.
- [ ] Implementasikan `VaultBaseTool` dengan input JSON terstruktur, fixed schema, view `table/cards/list`, dan create-only atomic write.
- [ ] Implementasikan `VaultCanvasTool` dengan pencarian exact note, ID `secrets.token_hex(8)`, layout tetap, max 20 node, edge tervalidasi, dan create-only atomic write.
- [ ] Import dan daftarkan kedua tool pada agent Arsip; ubah backstory hanya bila perlu menjelaskan kapan tool dipakai.
- [ ] Jalankan `bima_env/bin/pytest tests/test_obsidian_formats.py -q` sampai lulus.
- [ ] Jalankan Ruff pada `tools/obsidian_formats.py`, `teams/t3_arsip.py`, dan test.

## Task 3: Arahkan runtime ke vault OneDrive

**Files:**
- Modify: `.env`
- Modify: `.env.example`

- [ ] Ubah `OBSIDIAN_PATH` lokal menjadi `/mnt/c/Users/shint/OneDrive/Dokumen/BIMA_VAULT/Penyimpanan`.
- [ ] Pertahankan `.env.example` sebagai contoh generik dan tambahkan catatan path WSL/OneDrive tanpa data rahasia.
- [ ] Jalankan import smoke Arsip dengan environment aktif dan pastikan resolver melihat vault yang memiliki 54 Markdown, 1 Base, dan 3 Canvas tanpa mengubahnya.

## Task 4: Tambah test DuckDB yang gagal

**Files:**
- Create: `tests/test_duckdb_tool.py`
- Inspect: `teams/t4_admin/data_analysis_tool.py`
- Inspect: `teams/t4_admin/agent.py`
- Inspect: `teams/t4_admin/__init__.py`

- [ ] Buat fixture CSV dan Parquet di output root sementara.
- [ ] Tulis test `count/sum/avg/min/max`, `group_by`, limit, dan output CSV turunan.
- [ ] Tulis test penolakan traversal, file di luar outputs, suffix lain, operasi lain, dan raw SQL.
- [ ] Jalankan `bima_env/bin/pytest tests/test_duckdb_tool.py -q` dan pastikan gagal karena modul belum ada.

## Task 5: Implementasi DuckDB read-only

**Files:**
- Create: `teams/t4_admin/duckdb_tool.py`
- Modify: `teams/t4_admin/agent.py`
- Modify: `teams/t4_admin/__init__.py`
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `uv.lock`
- Test: `tests/test_duckdb_tool.py`

- [ ] Tambahkan pin `duckdb==1.5.4` ke dependency runtime dan CI, lalu sinkronkan requirements dan lockfile.
- [ ] Implementasikan `DuckDBAnalysisTool` dengan model input terstruktur dan root `OUTPUT_DIR` yang tervalidasi.
- [ ] Gunakan API relasi DuckDB; jangan sediakan field raw SQL.
- [ ] Batasi operasi ke `count/sum/avg/min/max`, validasi identifier kolom dari schema file, dan batasi jumlah row hasil.
- [ ] Simpan hasil turunan hanya ke CSV bernama aman di `outputs/` bila diminta.
- [ ] Export dan daftarkan tool pada Admin.
- [ ] Jalankan `bima_env/bin/pytest tests/test_duckdb_tool.py -q` sampai lulus.
- [ ] Jalankan Ruff pada file DuckDB/Admin/test yang tersentuh.

## Task 6: Tambah test Strix wrapper yang gagal

**Files:**
- Create: `tests/test_strix_scanner.py`
- Inspect: `teams/t8_mekanik.py`

- [ ] Tulis test gate `STRIX_ENABLED=false`, uvx hilang, Docker CLI hilang, dan Docker daemon mati.
- [ ] Tulis test snapshot hanya menyalin allowlist serta mengecualikan `.env`, vault, log, outputs, index, venv, `node_modules`, secret-name, dan symlink.
- [ ] Tulis test command memakai versi/image pinned, target snapshot lokal, telemetry off, HOME sementara, budget allowlist, dan tanpa shell.
- [ ] Tulis test exit code `0` sebagai bersih, `2` sebagai findings, serta sanitasi API key dari output.
- [ ] Jalankan `bima_env/bin/pytest tests/test_strix_scanner.py -q` dan pastikan gagal karena modul belum ada.

## Task 7: Implementasi Strix terisolasi

**Files:**
- Create: `tools/strix_scanner.py`
- Modify: `teams/t8_mekanik.py`
- Modify: `.env.example`
- Test: `tests/test_strix_scanner.py`

- [ ] Implementasikan `StrixScannerTool` dengan target fixed BIMA_CORE dan mode/budget allowlist.
- [ ] Tambahkan preflight `uvx`, `docker version`, dan API key tanpa menampilkan nilai secret.
- [ ] Buat snapshot sementara dari `git ls-files --cached --others --exclude-standard` memakai allowlist root/file, path containment, dan penolakan symlink.
- [ ] Jalankan argv `uvx --from strix-agent==1.1.0 strix -n -t <snapshot> --scan-mode quick` dengan image pinned, child-only env, `STRIX_TELEMETRY=false`, serta HOME sementara.
- [ ] Arahkan report ke `outputs/security/`, hapus snapshot/HOME sementara pada `finally`, sanitasi output, dan petakan exit `2` sebagai findings.
- [ ] Daftarkan tool pada Mekanik tanpa mengubah scanner lama; stage nanti hanya hunk baru karena file sudah kotor sebelum task.
- [ ] Tambahkan contoh `STRIX_ENABLED=false`, model, image, dan max-budget ke `.env.example`; reuse `OPENROUTER_API_KEY` tanpa key baru.
- [ ] Jalankan `bima_env/bin/pytest tests/test_strix_scanner.py -q` sampai lulus.
- [ ] Jalankan Ruff pada wrapper, Mekanik, dan test.

## Task 8: Integrasi dan dokumentasi

**Files:**
- Modify: `README.md`
- Modify: `error_solutions.md`

- [ ] Tambahkan README untuk Base/Canvas, DuckDB, konfigurasi vault OneDrive WSL, Strix opt-in, prerequisite Docker, report path, dan batas report-only.
- [ ] Catat setiap error baru beserta root cause, solusi, dan verifikasinya di `error_solutions.md`.
- [ ] Pastikan README tidak mengklaim scan Strix end-to-end bila Docker masih belum tersedia.

## Task 9: Verifikasi penuh

**Files:**
- Verify all files from Tasks 1–8

- [ ] Jalankan targeted tests untuk Obsidian, DuckDB, dan Strix.
- [ ] Jalankan `bima_env/bin/pytest -q`.
- [ ] Jalankan Ruff hanya pada seluruh file Python yang disentuh.
- [ ] Jalankan `uv lock --check` dan `uv pip check --python bima_env/bin/python`.
- [ ] Jalankan AST/import smoke untuk tool baru dan `python scripts/healthcheck.py`.
- [ ] Jalankan Strix preflight; bila Docker tidak ada, rekam sebagai prerequisite eksternal dan jangan menyebut E2E lulus.
- [ ] Restart `pm2 restart anisa-v3 --update-env`, lalu periksa status/log dan smoke backend.
- [ ] Jalankan `git diff --check` hanya pada file/hunk task dengan Git Windows untuk menghindari mismatch CRLF WSL yang sudah tercatat.

## Task 10: Commit dan push terkontrol

**Files:**
- Stage only files/hunks produced by Tasks 1–9

- [ ] Gunakan skill `github:yeet` untuk pemeriksaan publikasi.
- [ ] Bandingkan diff akhir dengan baseline; jangan stage perubahan lama milik Bima.
- [ ] Stage file bersih secara utuh dan gunakan patch staging untuk `teams/t8_mekanik.py` serta `error_solutions.md` yang sudah kotor sebelum task.
- [ ] Buat satu commit dengan pesan yang merangkum Paket A+B.
- [ ] Push branch aktif setelah commit dan laporkan branch serta commit SHA.
