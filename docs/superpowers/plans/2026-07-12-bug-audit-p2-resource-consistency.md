# BIMA_CORE P2 Resource and Consistency Remediation Plan

**Goal:** Menutup delapan temuan P2 audit: resume Canvas WA, false-success dan profile race Browser Use, penomoran footer akademik multi-page, penghapusan jadwal aman, race organizer, collision diagram, leak figure matplotlib, dan leak workbook openpyxl.

**Scope rule:** Perubahan surgical pada file audit. Tidak menambah dependency dan tidak mengubah `.env`.

## Task 1: Prove Canvas Resume Works for WhatsApp

**Files:** `core/langgraph_nodes/intent_classifier.py`, `core/langgraph_nodes/canvas.py`, `tests/test_p2_canvas_routing.py`

- [x] Tulis test RED/GREEN yang memanggil `intent_classifier_node()` dengan `source_channel='whatsapp'`, `discord_user_id=sender_id`, dan session aktif; hasil wajib `['canvas']`.
- [x] Pastikan `core/wa_server.py` tetap meneruskan `sender_id` sebagai identity session.
- [x] Ubah pesan fallback Canvas menjadi channel-neutral; field legacy `discord_user_id` dipertahankan agar diff minimal.
- [x] Jalankan `pytest tests/test_p2_canvas_routing.py tests/test_p0_thread_isolation.py -q`.

## Task 2: Browser Completion Truth and Marketplace Profile Lock

**Files:** `services/browser/worker.py`, `tests/test_browser_worker_completion.py`

- [x] Tulis test bahwa final text non-kosong tetap `ok=False` jika `history.is_done()` false atau `history.is_successful()` bukan `True`.
- [x] Tulis test bahwa history done+successful menghasilkan `ok=True`.
- [x] Tambahkan advisory file lock stdlib `fcntl.flock(LOCK_EX)` untuk seluruh lifecycle marketplace `BrowserProfile` + `Agent.run()`, sehingga profile persistent tidak dipakai paralel antar-worker.
- [x] Return error generik untuk task incomplete; detail tetap di stderr logger.
- [x] Jalankan `pytest tests/test_browser_worker_completion.py tests/test_browser_worker_isolation.py -q`.

## Task 3: Dynamic Academic Footer Phase

**Files:** `teams/t4_admin/pdf_tool.py`, `tests/test_p2_admin_resource_cleanup.py`

- [x] Tulis integration test PDF akademik dengan abstrak dan TOC yang masing-masing auto-paginate.
- [x] Ganti pra-hitung jumlah halaman dengan phase runtime `front`/`body`: footer front selalu Roman, body memakai offset dari halaman body aktual.
- [x] Set phase body setelah halaman body benar-benar dibuat; jangan mengandalkan asumsi satu halaman per bagian.
- [x] Verifikasi urutan footer hasil render melalui PyMuPDF.

## Task 4: Safe Schedule Deletion

**Files:** `teams/t6_lifestyle.py`, `tests/test_schedule_manager.py`

- [x] Tulis test isolated schedule file untuk `add`, `delete|query`, ambiguous match, dan `clear` denial.
- [x] Tambahkan `delete|kata kunci`; hanya hapus jika tepat satu item cocok.
- [x] Gate `delete` dan `clear` lewat `check_permission_sync`; denial tidak boleh memutasi file.
- [x] Tolak action/data kosong tanpa `IndexError`; update description agar agent tidak memetakan delete tunggal ke clear.
- [x] Jalankan `pytest tests/test_schedule_manager.py tests/test_p1_error_redaction.py -q`.

## Task 5: Race-Safe File Organizer

**Files:** `tools/file_organizer.py`, `tests/test_file_organizer.py`

- [x] Tulis test bahwa file lebih muda dari 5 menit tidak dipindah.
- [x] Tulis test satu move gagal tetapi file berikutnya tetap diproses.
- [x] Tambahkan `MIN_FILE_AGE_SECONDS=300`, `try/except` per-file, dan collision suffix nanosecond.
- [x] Return summary terstruktur agar test dapat membuktikan moved/skipped/errors tanpa parsing output.
- [x] Jalankan `pytest tests/test_file_organizer.py -q`.

## Task 6: Collision-Safe Diagram Output

**Files:** `tools/diagram_tool.py`, `tests/test_diagram_tool.py`

- [x] Tambah test dua konten berbeda pada timestamp sama menghasilkan path berbeda.
- [x] Tambah test title/code di-escape dan write failure mengembalikan error generik.
- [x] Bentuk filename dari SHA-256 title+Mermaid serta `time.time_ns()`.
- [x] Log exception lokal tanpa mengirim exception detail.
- [x] Jalankan `pytest tests/test_diagram_tool.py -q`.

## Task 7: Always Close Matplotlib Figures

**Files:** `teams/t4_admin/chart_utils.py`, `tests/test_p2_admin_resource_cleanup.py`

- [x] Tulis test `savefig` failure tidak menambah `plt.get_fignums()`.
- [x] Validasi `chart_type`/datasets sebelum `subplots()`.
- [x] Bungkus seluruh render setelah figure creation dengan `try/finally: plt.close(fig)`.

## Task 8: Always Close Excel Workbooks

**Files:** `teams/t2_visual.py`, `tests/test_p2_admin_resource_cleanup.py`

- [x] Tulis test workbook fake yang raise saat iterasi tetap menerima `close()`.
- [x] Inisialisasi `wb=None` dan tutup di `finally`, termasuk exception path.
- [x] Jalankan resource cleanup suite.

## Task 9: P2 Verification and Audit Log

- [x] Jalankan seluruh targeted P2 suite serta regression P0/P1 terkait.
- [x] Jalankan `python -m compileall -q core teams tools services tests` dan `git diff --check`.
- [x] Jalankan full `pytest -q`; baseline wajib tetap nol failure.
- [x] Restart `anisa-v3`, cek `/health`, PM2, dan fresh startup logs.
- [x] Catat root cause, solusi, dan hasil aktual di `error_solutions.md`.
