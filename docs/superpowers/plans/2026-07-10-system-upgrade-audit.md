# BIMA_CORE System Upgrade Audit Plan

> **For agentic workers:** Jalankan audit ini secara inline dan berurutan. Tidak memakai sub-agent karena tidak diminta Bima.

**Goal:** Menentukan bagian BIMA_CORE yang layak di-upgrade berdasarkan rilis paket dan repository resmi terbaru, tanpa mengubah runtime atau konfigurasi.

**Architecture:** Audit membandingkan inventaris lokal dengan sumber primer terbaru, lalu menyaring kandidat berdasarkan kemampuan yang sudah ada agar tidak terjadi duplikasi tool. Hasil akhir berupa prioritas P0-P3, manfaat konkret, risiko kompatibilitas, dan langkah uji.

**Tech Stack:** Python, LangGraph, CrewAI, FastAPI, Discord/WhatsApp, MCP, LanceDB, browser automation, STT/TTS, GitHub/PyPI/npm.

---

### Task 1: Bekukan baseline lokal

**Files:**
- Read: `requirements.txt`
- Read: `requirements-ci.txt`
- Read: `requirements-dev.txt`
- Read: `config_mcp.json`
- Read: `teams/*.py`
- Read: `tools/*.py`
- Read: `core/**/*.py`

- [x] Catat versi paket inti yang terpasang dan versi yang tersedia.
- [x] Petakan semua `BaseTool` serta assignment `tools=[...]` per agen.
- [x] Cek status proses, test, lint, security audit, dan dependensi usang secara read-only.

### Task 2: Verifikasi sumber terbaru

**Files:**
- Read: repository resmi dan release notes proyek kandidat.

- [x] Cek rilis resmi terbaru untuk dependency inti yang benar-benar dipakai.
- [x] Cari repository aktif yang menutup gap BIMA_CORE, bukan menduplikasi tool yang ada.
- [x] Catat tanggal rilis/commit, lisensi, aktivitas maintenance, dan breaking changes.

### Task 3: Nilai kandidat upgrade

**Files:**
- Read: call site lokal yang terdampak untuk tiap kandidat.

- [x] Nilai kandidat pada manfaat, effort, risiko, kebutuhan GPU/RAM, dan konflik tool.
- [x] Kelompokkan menjadi: upgrade sekarang, uji di branch, pantau, atau tolak.
- [x] Susun urutan P0-P3 dengan alasan yang bisa diuji.

### Task 4: Tulis laporan audit

**Files:**
- Create: `docs/audits/2026-07-10-system-upgrade-audit.md`
- Modify: `error_solutions.md`

- [x] Tulis tabel kondisi sekarang versus target, repo sumber, manfaat, risiko, dan verifikasi.
- [x] Tambahkan semua error audit beserta penyebab dan solusi ke `error_solutions.md`.
- [x] Pastikan laporan tidak berisi token, nilai `.env`, atau rekomendasi yang belum diverifikasi.

### Task 5: Verifikasi artefak

**Files:**
- Verify: `docs/audits/2026-07-10-system-upgrade-audit.md`
- Verify: `error_solutions.md`

- [x] Cek semua tautan sumber dapat dibuka dan mendukung klaim terkait.
- [x] Cek `git diff --check` serta pastikan hanya dua artefak audit yang berubah selain file plan.
- [x] Laporkan hasil maksimal lima baris dan minta pilihan kandidat yang ingin diimplementasikan.
