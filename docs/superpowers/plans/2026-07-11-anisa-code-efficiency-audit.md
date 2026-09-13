# Anisa Code Efficiency Audit Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this audit inline. Do not dispatch subagents.

**Goal:** Mengukur duplikasi, kompleksitas, dead code, tumpang-tindih tool, dan beban runtime BIMA_CORE lalu memberi rekomendasi refactor serta skill/plugin berdasarkan bukti.

**Architecture:** Audit memisahkan source Anisa dari virtualenv, worktree, output, dan kode vendored. Hasil statis dikroscek dengan jalur runtime LangGraph/CrewAI supaya fungsi yang mirip nama tetapi berbeda tanggung jawab tidak salah ditandai sebagai duplikat.

**Tech Stack:** Python AST, Ruff, pytest, ripgrep, jscpd/Radon/Vulture secara read-only, Git, Ponytail skill catalog.

---

### Task 1: Tetapkan baseline dan batas audit

**Files:**
- Read: `core/**/*.py`
- Read: `teams/**/*.py`
- Read: `tools/**/*.py`
- Read: `services/**/*.py`
- Exclude: `services/browser/.venv/**`, `.kilo/worktrees/**`, `tools/last30days-skill/**`, `outputs/**`

- [ ] Catat jumlah file/LOC source Anisa, file terbesar, status Git, dan test baseline tanpa mengubah working tree.
- [ ] Pisahkan temuan source utama dari kode pihak ketiga/vendored.
- [ ] Gunakan existing test suite sebagai pagar agar saran penghapusan tidak memutus perilaku aktif.

### Task 2: Audit duplikasi dan kompleksitas

**Files:**
- Analyze: `core/**/*.py`
- Analyze: `teams/**/*.py`
- Analyze: `tools/**/*.py`

- [ ] Deteksi clone blok dengan `jscpd` atau analisis AST read-only; verifikasi manual setiap kandidat sebelum menyebutnya duplikat.
- [ ] Ukur cyclomatic complexity, jumlah branch, panjang fungsi, dan file di atas batas 800 baris.
- [ ] Cari dead code/import tidak terpakai dengan Ruff/Vulture; jangan auto-fix.
- [ ] Kelompokkan hasil menjadi: duplikat nyata, kemiripan wajar, kompleksitas perlu pecah, dan false positive.

### Task 3: Audit arsitektur agent dan tool

**Files:**
- Read: `core/langgraph_engine.py`
- Read: `core/langgraph_nodes/*.py`
- Read: `teams/**/*.py`
- Read: `tools/**/*.py`
- Read: `config_mcp.json`

- [ ] Petakan route user → classifier/manager → specialist → CrewAI tool.
- [ ] Bandingkan semua `BaseTool`, daftar `tools=[...]`, MCP tool injection, serta helper HTTP/file/search untuk menemukan kemampuan ganda.
- [ ] Tandai tool yang menambah prompt/tool-selection cost meski jarang atau tidak pernah diroute.
- [ ] Bedakan beban kode/maintenance dari beban runtime RAM, startup, token prompt, dan latency.

### Task 4: Verifikasi hotspot nyata

**Files:**
- Read: `core/threads_commands.py`
- Read: `core/furniture_qc.py`
- Read: `teams/t2_visual.py`
- Read: `teams/t5_intel.py`
- Read: file hotspot lain berdasarkan hasil Task 2

- [ ] Telusuri fungsi terbesar dan jalur panggilnya.
- [ ] Cek apakah wrapper retry, HTTP client, parsing file, dan output handling dibuat berulang.
- [ ] Prioritaskan hanya perubahan dengan gain terukur; hindari konsolidasi LangGraph/CrewAI tanpa bukti.

### Task 5: Evaluasi skill/plugin

**Files:**
- Read: `skills-lock.json`
- Read: skill directories user/project

- [ ] Verifikasi Ponytail terpasang atau tidak di project, Claude, dan Codex.
- [ ] Bandingkan `ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt`, dan `ponytail-gain` dengan kebutuhan BIMA_CORE.
- [ ] Nilai kandidat lain dari catalog berdasarkan fungsi, popularitas, keamanan, dan overlap dengan skill yang sudah ada.
- [ ] Rekomendasikan maksimal satu paket utama dan satu tool pelengkap agar tidak menambah decision paralysis.

### Task 6: Dokumentasi dan laporan

**Files:**
- Create: `docs/audits/2026-07-11-anisa-code-efficiency-audit.md`
- Modify: `error_solutions.md`

- [ ] Tulis temuan berurutan P0/P1/P2 dengan lokasi file, bukti, dampak, risiko, dan solusi minimal.
- [ ] Catat kegagalan command audit: Linux case-sensitive `CLAUDE.md`, regex PowerShell→WSL, Ruff tidak tersedia di `bima_env`, dan race cache `npx ENOTEMPTY`, berikut solusi reproducible.
- [ ] Berikan verdict singkat: bagian yang sudah efisien, bagian boros, serta urutan perbaikan.
- [ ] Jangan edit source code, dependency, environment, atau konfigurasi runtime dalam tahap audit ini.

### Verification

- [ ] Pastikan `git diff --stat` hanya berisi plan, laporan audit, dan tambahan `error_solutions.md` milik audit ini; jangan menimpa perubahan user/Claude yang sudah ada.
- [ ] Pastikan semua klaim memiliki referensi file/line atau output command.
- [ ] Pastikan rekomendasi instalasi belum dijalankan tanpa approval terpisah.
