# Offline Maintenance Anisa Audit Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to run this audit inline. Do not delegate or modify production runtime.

**Goal:** Memastikan source, test, dependency, dan konfigurasi keamanan Anisa sehat saat seluruh service tetap mati.

**Architecture:** Audit bersifat read-only terhadap source dan runtime. Test serta scanner lokal dijalankan dari `bima_env`; advisory dependency diambil dari registry Python/npm terbaru. Kegagalan hanya didiagnosis dan dicatat, tidak diperbaiki otomatis.

**Tech Stack:** Python 3.12, pytest, Ruff, Bandit, pip-audit, uv, npm audit, MCP security audit.

---

### Task 1: Baseline dan ketersediaan alat audit

**Files:**
- Read: `pyproject.toml`
- Read: `requirements-dev.txt`
- Read: `package.json`
- Read: `whatsapp/package.json`
- Read: `services/agentmemory/package.json`

- [x] **Step 1: Catat Git state tanpa menyentuh perubahan milik Bima**

Run: `git status --short --branch`

Expected: status terbaca; file dirty yang sudah ada dipertahankan.

- [x] **Step 2: Cek versi alat audit lokal**

Run: `bima_env/bin/pytest --version`, `bima_env/bin/ruff --version`, `bima_env/bin/bandit --version`, `bima_env/bin/pip-audit --version`, dan `bima_env/bin/uv --version`.

Expected: alat tersedia. Jika alat tidak ada, catat sebagai gap dan jangan install dependency.

### Task 2: Verifikasi test suite

**Files:**
- Test: `tests/`
- Read only: source yang diimpor test

- [x] **Step 1: Jalankan seluruh pytest**

Run: `bima_env/bin/pytest -q`

Expected: seluruh test lulus. Jika gagal, hentikan auto-fix dan kumpulkan traceback serta test terkait.

### Task 3: Audit kualitas dan keamanan source

**Files:**
- Scan: `main.py`, `config.py`, `core/`, `teams/`, `tools/`, `tests/`, `scripts/`
- Exclude: `tools/last30days-skill/`

- [x] **Step 1: Jalankan Ruff read-only** *(tool tidak terpasang; dicatat sebagai gap, tanpa instalasi)*

Run: `bima_env/bin/ruff check main.py config.py core teams tools tests scripts --exclude tools/last30days-skill --output-format concise`

Expected: exit 0 atau daftar lint debt yang dapat diaudit; tidak menjalankan `--fix`.

- [x] **Step 2: Jalankan Bandit read-only**

Run: `bima_env/bin/bandit -r main.py config.py core teams tools scripts -x tools/last30days-skill -q`

Expected: exit 0 atau daftar temuan keamanan dengan severity/confidence; tidak mengubah source.

- [x] **Step 3: Jalankan audit MCP existing**

Run: panggil `core.mcp_security.audit_mcp_config(MCP_CLIENTS_CONFIG)` dari Python venv.

Expected: status `secure` atau bukti issue konfigurasi.

### Task 4: Audit dependency terbaru

**Files:**
- Read: `pyproject.toml`, `uv.lock`, `package-lock.json`, `whatsapp/package-lock.json`, `services/agentmemory/package-lock.json`

- [x] **Step 1: Cek konsistensi environment Python**

Run: `bima_env/bin/uv pip check --python bima_env/bin/python`

Expected: seluruh dependency compatible.

- [x] **Step 2: Audit vulnerability Python dari advisory registry terbaru** *(memakai `uv audit --frozen` karena `pip-audit` tidak terpasang)*

Run: `bima_env/bin/pip-audit --progress-spinner off`

Expected: 0 vulnerability atau daftar package/CVE yang terverifikasi; jangan menjalankan auto-upgrade.

- [x] **Step 3: Audit vulnerability npm pada tiga lockfile aktif**

Run dari root, `whatsapp/`, dan `services/agentmemory/`: `npm audit --audit-level=moderate`.

Expected: 0 vulnerability atau daftar advisory; jangan menjalankan `npm audit fix`.

- [x] **Step 4: Ambil daftar Python package outdated**

Run: `bima_env/bin/uv pip list --python bima_env/bin/python --outdated`

Expected: daftar versi current/latest sebagai bahan maintenance; tidak melakukan upgrade.

### Task 5: Dokumentasi hasil

**Files:**
- Modify: `error_solutions.md`
- Modify: `docs/superpowers/plans/2026-07-15-offline-maintenance-anisa.md`

- [x] **Step 1: Catat hanya kesalahan yang terverifikasi**

Tambahkan masalah, root cause yang didukung bukti, solusi aman, dan hasil verifikasi. Status PM2 `stopped` tidak dicatat sebagai error karena Bima mematikannya sengaja.

- [x] **Step 2: Verifikasi diff audit** *(gate target bersih; gate global WSL terblokir mismatch CRLF dan dicatat di Log 80)*

Run: `git diff --check` dan `git status --short`.

Expected: tidak ada source/runtime/config yang berubah; hanya dokumen audit yang disengaja.

## Hasil Audit 2026-07-15

- PM2 tetap `stopped` sesuai keputusan Bima; tidak dinyalakan dan tidak dihitung sebagai error.
- Healthcheck lulus 50 cek dengan 2 warning nonfatal.
- Pytest lulus `299 passed` dengan 2 warning deprecation dependency.
- MCP audit: `secure`, 0 issue.
- Ruff dan pip-audit dideklarasikan tetapi executable tidak ada di `bima_env`; tidak diinstal.
- Bandit memindai 20.639 baris: 99 low, 13 medium, 7 high. Lima high adalah MD5 untuk slug nama file; dua high memakai `shell=True`.
- Reader PM2 lama pada `core/observability_scheduler.py` terkonfirmasi mengembalikan `[]`, sedangkan reader maintenance melihat empat proses.
- `uv pip check` menemukan 9 incompatibility pada environment aktif.
- `uv sync --active --frozen --dry-run` akan menghapus 163 package dan memasang 31 package; sync langsung tidak aman untuk production.
- `uv audit --frozen` menemukan 5 record advisory pada 3 package: ChromaDB, DiskCache, dan json-repair.
- npm audit root dan WhatsApp: 0 vulnerability.
- npm audit AgentMemory: 15 vulnerability (10 moderate, 4 high, 1 critical); service disabled dan dry-run tidak menyelesaikannya.
- Python outdated: 113 package; tidak ada upgrade dilakukan.
- Windows Git melihat 5 entry workspace, sedangkan Git WSL melihat 63 file berubah karena mismatch `core.autocrlf`; file lama tidak dinormalisasi.

## Prioritas Lanjutan

1. Perbaiki reader PM2 observability dan tambah regression test.
2. Pertahankan AgentMemory disabled sampai dependency tree aman dan tervalidasi.
3. Buat environment baru dari lock setelah dependency voice/browser yang wajib dimasukkan ke metadata project.
4. Patch json-repair melalui dependency constraint teruji; ChromaDB belum mempunyai versi patched.
5. Pin revision model Hugging Face TTS dan hilangkan `shell=True` dari cloud backup.
