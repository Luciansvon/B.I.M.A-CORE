# BIMA_CORE Bug Audit Remediation Design

**Tanggal:** 2026-07-12  
**Sumber:** `docs/audits/2026-07-12-full-codebase-bug-audit.md` dan lampiran audit Bima  
**Scope:** Semua temuan P0, P1, P2, dan P3; dikerjakan bertahap berdasarkan severity.

## Tujuan

Menutup seluruh bug dan miss-logic pada audit tanpa menimpa perubahan uncommitted Bima. Setiap tahap harus berdiri sendiri, memakai regression test, dan berhenti bila verifikasi gagal.

## Prinsip Implementasi

1. Urutan tetap `P0 → P1 → P2 → P3`.
2. TDD per perilaku: tulis test yang mereproduksi bug, pastikan gagal karena bug tersebut, tambal minimal, lalu jalankan test terkait dan regression suite.
3. Reuse pola aman yang sudah ada. Helper bersama hanya dibuat bila satu root cause muncul di banyak caller.
4. Input path ditolak bila keluar dari root yang diizinkan; nama output disanitasi menjadi basename aman.
5. Detail exception hanya masuk log lokal. Respons Discord/WhatsApp menerima pesan generik.
6. Perubahan existing di worktree dipertahankan. Tidak ada refactor, dependency baru, migrasi, restart, atau push di luar scope.
7. Kendala dan solusi non-trivial dicatat ke `error_solutions.md` setelah tahap terkait terverifikasi.

## Tahap 1 — P0 Security

### 1.1 Path confinement

Buat helper kecil di `core/path_security.py` untuk dua kebutuhan berbeda:

- `safe_output_path(...)`: menghasilkan nama output aman di dalam root tujuan; separator, absolute path, `..`, control character, dan stem kosong tidak boleh memengaruhi direktori.
- `resolve_allowed_path(...)`: resolve file input yang sudah ada, lalu wajib berada di salah satu root yang diizinkan dan memiliki ekstensi yang sesuai.

Pemakaian:

- `teams/t4_admin/excel_tool.py`, `pdf_tool.py`, `word_tool.py`: nama file hasil selalu berada di `OUTPUT_DIR`.
- `tools/code_visualizer.py`: `target_dir` hanya boleh berada di workspace BIMA_CORE.
- `tools/image_gen_tool.py`: reference image hanya boleh berasal dari `outputs/` dan berekstensi gambar.
- Helper yang sama menjadi dasar perbaikan P1 pada `FileSaverTool`, data analysis, dan image embedding.

Path input yang melanggar confinement menghasilkan `FAILED|Path tidak diizinkan`; detail absolut dicatat lokal dan tidak dikirim ke user.

### 1.2 Isolasi thread WhatsApp dan Discord

Pisahkan konsep jenis channel dari scope percakapan:

- `source_channel`: tetap `discord` atau `whatsapp` untuk logika fitur.
- `conversation_id`: ID chat/channel nyata untuk checkpoint dan callback.
- `discord_user_id`: dipakai sebagai ID user lintas channel demi kompatibilitas state lama.

Alur WhatsApp:

```text
senderId di whatsapp/index.js
  → POST /chat sender_id
  → ChatRequest.sender_id
  → run_langgraph_engine(discord_user_id=sender_id, conversation_id=sender_id)
  → thread_id unik per sender
```

Alur Discord:

```text
message.author.id + message.channel.id
  → run_langgraph_engine(..., conversation_id=channel.id)
  → thread_id unik per user dan channel/DM
```

`core/langgraph_nodes/state.py` memakai pembentuk thread ID yang sama dengan engine agar registry callback dan checkpoint tidak berbeda key. Sender WhatsApp kosong ditolak di bridge, bukan jatuh ke `anon_whatsapp`.

### 1.3 XSS dashboard

`ActivityPanel` tidak boleh merender `l.text` sebagai HTML. Teks log dirender sebagai React text node. Formatting internal berbasis `<span>` diubah menjadi data/string biasa agar tidak membutuhkan `dangerouslySetInnerHTML`.

Test membuktikan payload `<img src=x onerror=...>` tetap menjadi teks dan tidak masuk ke DOM sebagai elemen HTML.

## Tahap 2 — P1 Functional/Safety

### 2.1 Sisa path traversal

Terapkan helper Tahap 1 pada:

- `teams/t8_mekanik.py`: approval menampilkan resolved path dan penulisan wajib di `OUTPUT_DIR`.
- `teams/t4_admin/data_analysis_tool.py`: hanya membaca CSV/Excel dari root input yang diizinkan.
- `teams/t2_visual.py` dan `teams/t7_html_templates.py`: image embedding hanya dari root aman dan ekstensi gambar.

### 2.2 WhatsApp sanitizer

Tokenizer ringan melindungi fenced code dan inline code sebelum transformasi bold/header/link. Fence tidak tertutup diperlakukan sebagai code sampai akhir pesan. Parser link mempertahankan URL dengan kurung seimbang. Isi code dikembalikan tanpa perubahan.

### 2.3 Error disclosure

Tambahkan helper respons error generik dan gunakan pada direct Discord command serta tool-team yang diaudit (`t4_admin`, `t5_intel`, `t6_lifestyle`, `t8_mekanik`, `t9_saham`). Exception lengkap tetap `logger.exception(...)`; chat hanya menerima kode/konteks aman tanpa path, traceback, token, atau payload internal.

### 2.4 Setup Threads

`scripts/setup_threads.py` memvalidasi HTTP status, payload error, dan `access_token` non-empty sebelum menyentuh `.env`. Pesan sukses hanya dicetak setelah token valid berhasil ditulis. Path `.env` diturunkan dari root repo, bukan current working directory.

### 2.5 Slide approval

`bypass_preview` dihapus dari schema publik LLM. Bypass internal preview memakai method/helper privat, sehingga initial tool call untuk PDF/PPTX/HTML selalu melewati approval gate. PNG preview internal tidak memicu rekursi approval.

### 2.6 Cloud backup

`tools/cloud_backup.py` tidak boleh melakukan unattended commit/push ke repo development. Default hanya menyiapkan backup lokal dan melaporkan file yang benar-benar staged. Push memerlukan jalur approval eksplisit dan remote backup yang berbeda dari origin development; kondisi no-op tidak boleh dilaporkan sukses.

### 2.7 Browser timeout dan cleanup

Timeout caller harus lebih besar dari batas kerja worker dengan grace period. Worker dijalankan dalam process group baru; timeout menghentikan seluruh group agar Chromium child tidak orphan. `finally` tetap menutup browser pada exit normal.

### 2.8 Sherlock whitespace

Normalisasi `username.strip()` dilakukan sebelum truthiness dan token extraction. Input kosong/whitespace menghasilkan `FAILED|Username kosong`, bukan `IndexError`.

### 2.9 Discord checkpoint/callback collision

Perbaikan `conversation_id` Tahap 1 juga menutup temuan P1 Discord: channel/DM berbeda milik user yang sama tidak lagi berbagi checkpoint atau callback registry.

## Tahap 3 — P2 Correctness dan Resource Lifecycle

1. `services/browser/worker.py`: sukses hanya bila agent selesai dan `is_successful()` benar; result parsial dilaporkan gagal/unfinished.
2. Marketplace profile diberi lock lintas request agar satu profile Chromium tidak dibuka bersamaan.
3. `teams/t4_admin/pdf_tool.py`: body start page ditentukan dari page number aktual setelah front matter selesai render, bukan asumsi satu halaman per bagian.
4. `teams/t6_lifestyle.py`: tambah delete satu jadwal dengan target eksplisit; `clear` tetap operasi terpisah dan tidak menjadi fallback delete.
5. `tools/file_organizer.py`: hanya memindahkan file yang cukup tua, memproses per-file, dan mempertahankan file yang masih ditulis/dikunci.
6. `tools/diagram_tool.py`: nama output memakai timestamp resolusi tinggi atau hash konten agar dua call satu detik tidak collision; tambah test escape dan write failure.
7. `teams/t4_admin/chart_utils.py`: validasi sebelum membuat figure dan selalu `plt.close(fig)` lewat `finally` setelah figure ada.
8. `teams/t2_visual.py`: workbook openpyxl selalu ditutup lewat context/finally.
9. `core/langgraph_nodes/intent_classifier.py`: sesi canvas WhatsApp dapat resume setelah sender ID tersedia dari Tahap 1.

## Tahap 4 — P3 Consistency dan Performance

1. `core/langgraph_nodes/manager.py`: jumlah opsi prompt diselaraskan dengan menu aktual atau kalimat jumlah statis dihapus.
2. `core/langgraph_engine.py`: cache graph/checkpointer tidak bergantung pada `id(event_loop)` yang dapat reuse; lifecycle cache mengikuti object loop dan shutdown membersihkan entry.
3. `core/gen_rate_limit.py`: operasi sqlite sinkron dipindahkan ke thread pada caller async tanpa mengubah API sinkron yang dipakai caller non-async.
4. `scripts/setup_threads.py` dan `scripts/test_post_image.py`: `.env` selalu di-resolve dari root repo.
5. `services/agentmemory/package.json`: script `start` disamakan dengan `ecosystem.config.js` memakai `--tools core`.

## Testing dan Verification

### Test terarah

- Python security/path/thread: pytest dengan temporary directory dan mock engine; tidak membaca `.env` atau file sensitif nyata.
- WhatsApp sanitizer dan sender propagation: Node test untuk fungsi pure + mock axios payload.
- Dashboard XSS: test source/component atau renderer yang memastikan tidak ada HTML injection path.
- Tool approval/error/resource: unit test per tool dengan external process/API dimock hanya di boundary.
- Browser worker: fake agent/process untuk status selesai, timeout, lock, dan process-group cleanup.
- Collision/resource leak: temporary files, patched clock, `plt.get_fignums()`, dan workbook yang memverifikasi close.

### Gate tiap tahap

1. Jalankan test baru dan pastikan RED sebelum implementation.
2. Implementasi minimal satu perilaku.
3. Jalankan test baru sampai GREEN.
4. Jalankan test modul terkait.
5. Jalankan full `bima_env/bin/pytest` sebelum tahap dinyatakan selesai.
6. Bila test/lint gagal, berhenti dan laporkan; jangan auto-patch di luar plan.

## Batasan

- Tidak mengubah dependency, `.env`, CI/CD, database schema, atau layanan eksternal.
- Tidak menjalankan cloud backup, posting Threads, push Git, migration, atau restart service tanpa kebutuhan yang sudah disetujui.
- Tidak memperbaiki item “confirmed non-bug” dari audit.
- Tidak membersihkan atau memformat file yang tidak terkait.

## Definition of Done

- Semua temuan dalam audit memiliki regression test atau verifikasi deterministik.
- Tidak ada path audited yang dapat keluar dari root yang diizinkan.
- Thread WhatsApp dan Discord terisolasi sesuai user + conversation.
- Dashboard tidak merender log eksternal sebagai HTML.
- Approval, error redaction, backup, browser cleanup, dan lifecycle resource sesuai desain.
- Seluruh test terkait dan full pytest lulus.
- `error_solutions.md` berisi root cause, dampak, dan pencegahan untuk kendala non-trivial yang benar-benar ditemui.
