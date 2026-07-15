# Package A + B Integration Design

**Tanggal:** 2026-07-15
**Status:** Disetujui untuk direncanakan
**Rujukan audit:** `docs/audits/2026-07-15-github-repo-integration-audit.md`

## Tujuan

Mengambil bagian yang berguna dari Obsidian Skills dan DuckDB ke runtime BIMA_CORE, lalu menambahkan Strix sebagai pemindai keamanan terisolasi. Implementasi harus kecil, tidak mengubah 54 note lama, tidak mengekspos secret, dan tidak memberi Strix hak mengubah source.

## Arsitektur

```text
Paket A
Arsip -> validator Markdown/Base/Canvas -> vault Obsidian OneDrive
Admin -> DuckDB read-only -> CSV/Parquet di outputs -> chart/report yang sudah ada

Paket B
Perintah eksplisit Bima -> wrapper aman -> snapshot source tersaring
                      -> uvx Strix + Docker -> report-only di outputs/security
```

## Paket A — Obsidian

- Vault aktif tetap di OneDrive: `/mnt/c/Users/shint/OneDrive/Dokumen/BIMA_VAULT/Penyimpanan`.
- `VaultSaveTool` lama tetap menangani Markdown dan tidak ditulis ulang.
- Modul baru `tools/obsidian_formats.py` menyediakan `VaultBaseTool` dan `VaultCanvasTool`.
- Kedua tool menerima JSON terstruktur, memvalidasi nama/path, memastikan target tetap di dalam vault, dan hanya membuat file baru. File lama tidak boleh ditimpa.
- Base memakai subset aman format `.base`: filter folder/kategori, kolom tetap, serta view `table`, `cards`, atau `list`.
- Canvas memakai JSON Canvas: note harus sudah ada, ID node 16 karakter hex, edge hanya boleh menunjuk node valid, layout dibuat tetap dan tidak bertumpuk.
- Versi pertama tidak memakai Obsidian CLI karena membutuhkan aplikasi Obsidian hidup dan tidak dibutuhkan untuk menulis format file.
- Tidak ada migrasi frontmatter massal. Sebanyak 54 note lama dibiarkan utuh.

## Paket A — DuckDB

- Tool baru `DuckDBAnalysisTool` diletakkan di `teams/t4_admin/duckdb_tool.py` dan didaftarkan ke Admin.
- Input berupa JSON terstruktur: path file, operasi agregasi, kolom nilai, kolom grup, dan limit.
- File sumber hanya `.csv` atau `.parquet` di dalam `outputs/`.
- Operasi yang diizinkan hanya `count`, `sum`, `avg`, `min`, dan `max`.
- Raw SQL tidak diterima. Tool memakai API relasi DuckDB dan mengembalikan hasil yang dibatasi agar tidak membanjiri konteks.
- Hasil turunan boleh disimpan kembali sebagai CSV di `outputs/` agar tool chart/report yang sudah ada dapat memakainya.
- Dependency dipin ke `duckdb==1.5.4`, lalu lockfile diperbarui.

## Paket B — Strix

- Strix tidak dipasang ke `bima_env` karena membutuhkan Python 3.12+ dan rentang OpenAI SDK-nya bentrok dengan BIMA_CORE.
- Runner memakai `uvx --from strix-agent==1.1.0` dengan Docker sandbox `ghcr.io/usestrix/strix-sandbox:1.0.0`.
- Tool baru `StrixScannerTool` berada di `tools/strix_scanner.py` dan hanya aktif bila `STRIX_ENABLED=true`.
- Target versi pertama hanya BIMA_CORE lokal. URL/arbitrary target ditolak.
- Sebelum scan, wrapper membuat snapshot sementara dari file Git yang aman. `.env`, vault, log, output lama, indeks, `node_modules`, virtualenv, key, credential, dan symlink tidak disalin.
- Child process mendapat HOME sementara. API key diteruskan hanya lewat environment child dan konfigurasi sementara dihapus setelah proses selesai.
- Telemetry dimatikan. Strix berjalan report-only, tanpa auto-fix, commit, push, atau perubahan pada working tree.
- Exit code `2` dibaca sebagai temuan kerentanan, bukan kegagalan infrastruktur.
- Report disimpan di `outputs/security/`.
- Docker belum tersedia saat desain dibuat. Implementasi tetap mencakup preflight dan unit test; scan end-to-end tidak boleh diklaim sampai Docker tersedia.

## Keamanan dan Batasan

- Tidak ada dependency install, perubahan `.env`, atau restart sebelum gate CODE disetujui.
- Path harus di-resolve dan diverifikasi berada di root yang diizinkan.
- Semua output subprocess disanitasi sebelum dikembalikan ke agen.
- Maksimum budget Strix berasal dari konfigurasi allowlist, bukan angka bebas dari prompt.
- Working tree sudah memiliki perubahan milik Bima. Commit akhir hanya memuat hunk/file dari implementasi ini.

## Verifikasi

- Obsidian: traversal, overwrite, note hilang, schema Base, keunikan ID Canvas, dan referensi edge.
- DuckDB: CSV/Parquet, semua agregasi allowlist, invalid path/suffix/operation, dan limit output.
- Strix: disabled gate, Docker/uvx preflight, filter secret, command pin, HOME sementara, sanitasi output, serta exit `0`/`2`.
- Gate akhir: targeted tests, full pytest, Ruff pada file tersentuh, lock check, dependency check, healthcheck, restart PM2, lalu smoke test.

## Hasil Akhir

README menjelaskan fitur, konfigurasi, prerequisite Docker, dan batas keamanan. Setelah seluruh gate yang tersedia lulus, perubahan di-commit dan di-push tanpa membawa perubahan lama milik Bima.
