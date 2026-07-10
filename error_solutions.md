# Log Kesalahan dan Solusi (BIMA_CORE)

## Log 10: Bug Pathing pada scripts/healthcheck.py
* **Masalah**: Variabel `BASE_DIR` diatur menggunakan `Path(__file__).parent`, yang menghasilkan folder `scripts/` karena skrip berada di folder `scripts`. Hal ini menyebabkan semua pemeriksaan mencari `.env`, `main.py`, dan direktori output di dalam folder `scripts/` sehingga salah dideteksi sebagai `MISSING` atau `not found`.
* **Solusi**: Ubah definisi `BASE_DIR` menjadi `Path(__file__).parent.parent` agar merujuk ke root utama proyek, sehingga pencarian path menjadi akurat.

## Log 11: Setelan Fallback OCR Kurang Optimal pada core/ocr.py
* **Masalah**: Saat pemanggilan perintah `!ocr` di Discord, jika engine online (Gemini Vision) gagal, sistem melakukan fallback ke `easyocr` yang lambat dan boros resource. Padahal, sistem sudah memiliki `RapidOCR` yang terpasang dan jauh lebih cepat serta akurat di CPU.
* **Solusi**: Ubah kode fallback di `core/ocr.py` agar mengarah ke `extract_text_rapid_async` sebagai opsi utama cadangan offline sebelum beralih ke `easyocr`.

## Log 12: Potensi Crash/Segfault Whisper large-v3-turbo di CPU
* **Masalah**: Setelan default `.env` menggunakan model STT `small` karena model `large-v3-turbo` mengalami segfault di CPU saat dijalankan dengan tipe kompresi `int8` (karena keterbatasan pustaka ctranslate2 di CPU tertentu).
* **Solusi**:
  1. Ubah tipe kompresi `STT_COMPUTE_TYPE` ke `float32` jika ingin tetap menggunakan `large-v3-turbo` di CPU tanpa crash.
  2. Atau, arahkan STT ke GPU dengan menyetel `STT_DEVICE=cuda` dan `STT_COMPUTE_TYPE=float16` jika VRAM GPU RTX 3050 masih mencukupi.

## Log 13: Referensi claude.md Tidak Ditemukan Saat Audit Threads
* **Masalah**: `AGENTS.md` menyebut aturan lengkap ada di `claude.md`, tetapi file `claude.md` tidak ditemukan di root workspace saat audit upgrade prompt balasan Threads. Ini bisa bikin agent berikutnya gagal membaca sumber aturan yang direferensikan.
* **Solusi**: Pakai aturan yang sudah tercantum langsung di `AGENTS.md` sebagai sumber aktif. Untuk jangka panjang, tambahkan kembali `claude.md` atau ubah referensi di `AGENTS.md` ke file aturan yang benar.

## Log 14: Quoting Nested PowerShell ke WSL Gagal Saat Syntax Check
* **Masalah**: Command syntax check berbentuk `python3 -c "import ast; ..."` gagal saat dibungkus dari PowerShell ke `wsl bash -lc` karena nested quote dan tanda kurung diparse ulang oleh shell.
* **Solusi**: Untuk syntax check file Python dari PowerShell ke WSL, pakai command tanpa nested Python expression: `python3 -m py_compile core/threads_commands.py`.

## Log 15: Path Cache Skill Superpowers Berubah
* **Masalah**: Path skill `using-superpowers` dari sesi sebelumnya mengarah ke hash cache lama (`2f1a8948`) dan tidak ditemukan pada sesi terbaru.
* **Solusi**: Cari ulang file skill aktif dengan `Get-ChildItem -Path C:/Users/shint/.codex/plugins/cache -Recurse -Filter SKILL.md | Where-Object { $_.FullName -match 'using-superpowers' }`, lalu baca path hash terbaru.

## Log 16: apply_patch Gagal Karena Konteks Baris Mojibake
* **Masalah**: Patch pertama untuk `core/threads_commands.py` gagal karena konteks hunk menyertakan baris error berisi karakter mojibake, sehingga teks yang dicari tidak cocok persis.
* **Solusi**: Pecah patch menjadi hunk yang lebih kecil dan gunakan konteks ASCII/stabil di sekitar baris yang diedit.

## Log 17: Staged Diff Gagal Karena Trailing Whitespace
* **Masalah**: `git diff --cached --check` gagal pada `error_solutions.md` karena ada trailing whitespace setelah bullet `* **Solusi**:`.
* **Solusi**: Hapus spasi sisa di akhir baris sebelum commit, lalu jalankan ulang `git diff --cached --check`.

## Log 18: Git Commit Gagal Karena Author Identity Belum Diset
* **Masalah**: `git commit` gagal dengan pesan `Author identity unknown` karena environment ini belum punya `user.name` dan `user.email`.
* **Solusi**: Untuk commit sekali jalan tanpa mengubah global config, jalankan `git -c user.name="Luciansvon" -c user.email="bimachaktiadi.s@gmail.com" commit ...`.

## Log 19: Git Maintenance Gagal Tulis Multi-Pack-Index Setelah Commit
* **Masalah**: Commit berhasil, tetapi proses maintenance Git setelah commit menampilkan `fatal: could not write multi-pack-index: Permission denied` dan `geometric-repack failed`.
* **Solusi**: Commit tetap valid. Untuk commit/amend lanjutan di environment ini, gunakan override per-command `-c maintenance.auto=false` agar auto maintenance tidak dipicu.

## Log 20: Belum Ada Jadwal MT Team Mekanik untuk Cek Anisa
* **Masalah**: Anisa sudah punya `observability_scheduler` untuk alert berkala, tetapi belum ada jadwal maintenance rutin bernama Team Mekanik yang mengirim laporan kondisi Anisa pada waktu Bima bisa membaca hasilnya.
* **Solusi**: Tambahkan `core/mekanik_maintenance_scheduler.py` dengan mode report-only pada Senin/Rabu/Jumat pukul 21:30 WIB. Scheduler mengecek CPU/RAM/disk, PM2, GPU VRAM, log error terbaru, dan audit MCP, lalu mengirim laporan ke `BOT_STATUS_CHANNEL_ID` tanpa auto-restart, tanpa write/delete, dan tanpa git action.
* **Verifikasi**: Test RED/GREEN `tests/test_mekanik_maintenance_scheduler.py`, syntax check `python3 -m py_compile core/discord_bot.py core/mekanik_maintenance_scheduler.py`, dan focused pytest setelah implementasi.

## Log 21: PM2 anisa-v3 Berjalan dari Worktree Lama
* **Masalah**: Setelah patch di root `/home/bima_lucian/BIMA_CORE`, `pm2 describe anisa-v3` menunjukkan proses aktif memakai script path `/home/bima_lucian/BIMA_CORE/.worktrees/anisa-desktop/main.py`. Restart biasa tidak mengaktifkan patch root karena PM2 tetap menjalankan worktree tersebut.
* **Solusi**: Mirror patch runtime minimal ke `.worktrees/anisa-desktop` yang sedang dipakai PM2, compile file di worktree, lalu restart `anisa-v3`. Untuk jangka panjang, samakan lagi PM2 process dengan `ecosystem.config.js` root atau putuskan worktree mana yang jadi production source.
* **Verifikasi**: `pm2 logs anisa-v3 --nostream` menampilkan `[MEKANIK_MT] Scheduler aktif: mon,wed,fri 21:30 WIB` pada startup baru.

## Log 22: Switch PM2 ke Root Berisiko Karena Branch Production Berbeda
* **Masalah**: Root repo berada di branch `feature/last30days`, sedangkan PM2 production aktif berada di `.worktrees/anisa-desktop` branch `feature/anisa-desktop`. Diff antar branch besar dan menyentuh desktop app/API, permission gate, threads, dan config, sehingga memaksa `anisa-v3` pindah ke root bisa menurunkan fitur production yang sedang dipakai.
* **Solusi**: Jangan switch runtime ke root dulu. Reload `anisa-v3` memakai `.worktrees/anisa-desktop/ecosystem.config.js`, lalu jalankan `pm2 save` agar PM2 dump persist ke source production aktif. Rencana switch/merge ke root perlu kerja terpisah setelah branch disatukan.
* **Verifikasi**: `pm2 describe anisa-v3` tetap menunjukkan script path `.worktrees/anisa-desktop/main.py`, `/home/bima_lucian/.pm2/dump.pm2` berisi path tersebut, dan log startup menampilkan `[MEKANIK_MT] Scheduler aktif: mon,wed,fri 21:30 WIB`.

## Log 23: Pipeline `pm2 prettylist` Memicu EPIPE
* **Masalah**: Command eksplorasi `pm2 prettylist | python3 - <<'PY' ...` memutus pipe terlalu cepat sehingga proses Node PM2 menulis ke pipe tertutup dan melempar `Error: write EPIPE`.
* **Solusi**: Jangan pipe output PM2 besar ke heredoc Python kosong. Untuk inspeksi process metadata, gunakan `pm2 describe <name>`, `pm2 jlist > /tmp/pm2.json`, atau parse `pm2 jlist` dari file sementara.

## Log 24: `bima-whatsapp` Crash Loop Karena Dependency Node Hilang
* **Masalah**: PM2 menampilkan `bima-whatsapp` status `waiting restart` dengan restart count tinggi. Log terbaru berulang kali menunjukkan `Error: Cannot find module 'whatsapp-web.js'` dari `/home/bima_lucian/BIMA_CORE/whatsapp/index.js:17`.
* **Root Cause**: `whatsapp/package.json` sudah mendeklarasikan `whatsapp-web.js`, tetapi folder `whatsapp/node_modules/` tidak ada. Syntax `whatsapp/index.js` valid, jadi crash berasal dari dependency runtime yang belum terinstall.
* **Solusi**: Setelah approval Bima, stop crash loop dengan `pm2 stop bima-whatsapp`, jalankan `npm ci` dari folder `whatsapp/`, lalu `pm2 restart bima-whatsapp --update-env` dan `pm2 save`. Jika session WA perlu login ulang, scan QR dari `outputs/wa_qr.png`.
* **Verifikasi**: `pm2 describe bima-whatsapp` status `online`, log baru menampilkan `Auth OK` dan `Anisa WA Bridge ONLINE`, `npm ls whatsapp-web.js --depth=0` menampilkan `whatsapp-web.js@1.34.7`, dan backend WA `/health` mengembalikan `{"status":"ok","busy":false}`.

## Log 25: `npm audit` WhatsApp Menemukan 3 Vulnerability Transitive
* **Masalah**: Setelah `npm ci`, `npm audit --audit-level=moderate` exit 1 dengan 3 vulnerability: `form-data` high, `js-yaml` moderate, dan `ws` high.
* **Dampak**: Ini dependency transitive di WA bridge stack. Service sudah online, tetapi ada residual supply-chain/security risk.
* **Solusi**: Jangan menjalankan `npm audit fix` otomatis saat recovery karena bisa mengubah lockfile dan dependency behavior. Jadwalkan fix terpisah: audit tree package yang menarik `form-data`, `js-yaml`, dan `ws`, lalu update lockfile/test WA bridge secara terkontrol.

## Log 26: Path Linux Tidak Ditemukan di Environment Agent Windows
* **Masalah**: Pencarian atau pembacaan file dengan path `/Ubuntu/home/bima_lucian/BIMA_CORE` atau `/home/bima_lucian/BIMA_CORE` menghasilkan error karena sistem operasi host adalah Windows.
* **Solusi**: Gunakan path jaringan Windows `\\wsl.localhost\Ubuntu\home\bima_lucian\BIMA_CORE` untuk berinteraksi dengan workspace WSL dari host Windows.

## Log 27: Healthcheck Memakai Folder scripts sebagai Root
* **Masalah**: `scripts/healthcheck.py` menghasilkan 12 false critical failure dan false warning bahwa indeks tidak tersedia.
* **Root Cause**: `BASE_DIR` memakai parent langsung file sehingga menunjuk `scripts/`. Seluruh pemeriksaan juga berjalan otomatis saat modul di-import.
* **Solusi**: Gunakan `Path(__file__).resolve().parent.parent`, pindahkan eksekusi ke `main()`, dan sediakan helper `index_status()` yang dapat diuji.
* **Verifikasi**: `pytest tests/test_healthcheck.py -q` menghasilkan 2 test lulus. Verifikasi root production dilakukan lagi setelah integrasi branch.

## Log 28: Agent Tidak Memiliki Snapshot Operasional Ringkas
* **Masalah**: Agent harus menjalankan banyak command atau scan folder untuk mengetahui kondisi Anisa.
* **Root Cause**: Status CPU/RAM/disk hanya tersedia on-demand dan tidak ada kontrak status tunggal yang persisten.
* **Solusi**: Tambahkan sidecar `anisa-status` yang menulis `runtime/anisa_status.json` secara atomic setiap 30 detik. Snapshot berisi PM2, resource, backend, indeks, Git, dan error tersanitasi; data dianggap stale setelah 90 detik.
* **Verifikasi**: `pytest tests/test_operational_status.py -q` menghasilkan 6 test lulus dan one-shot CLI menghasilkan JSON valid.

## Log 29: Dependency WhatsApp Berada di Vulnerable Range
* **Masalah**: `npm audit` menemukan 2 vulnerability high dan 1 moderate pada `form-data`, `js-yaml`, serta `ws`.
* **Root Cause**: Lockfile menahan `form-data@4.0.5`, `js-yaml@4.1.1`, dan `ws@8.20.0`.
* **Solusi**: Jalankan `npm audit fix` tanpa `--force` agar lockfile memakai `form-data@4.0.6`, `js-yaml@4.3.0`, dan `ws@8.21.0`.
* **Verifikasi**: `npm audit --audit-level=moderate` menghasilkan 0 vulnerability dan `node --check whatsapp/index.js` exit 0.

## Log 30: Nested Quote PowerShell ke WSL Gagal Saat One-shot Collector
* **Masalah**: Perintah verifikasi `python -c` yang berisi tanda kutip dan kurung gagal diparse saat dibungkus oleh PowerShell dan `wsl bash -lc`.
* **Root Cause**: Beberapa lapis shell menginterpretasikan ulang quote sebelum command sampai ke Python.
* **Solusi**: Pecah verifikasi menjadi command sederhana: `python -m py_compile`, CLI `--once`, lalu `python -m json.tool`.

## Log 31: status_collector.py Tidak Bisa Import core Saat Dijalankan Langsung
* **Masalah**: `python scripts/status_collector.py` gagal dengan `ModuleNotFoundError: No module named 'core'`.
* **Root Cause**: Saat file di folder `scripts/` dijalankan langsung, Python menempatkan folder `scripts/` sebagai import root, bukan root repository.
* **Solusi**: Resolusi `PROJECT_ROOT` dilakukan sebelum import internal, lalu root ditambahkan ke `sys.path`. Tambahkan mode `--once` untuk smoke test deterministik.
* **Verifikasi**: Regression test `test_status_collector_supports_one_shot_cli` gagal sebelum fix dan lulus setelah fix.

## Log 32: Full Pytest Root Gagal pada Perubahan QC yang Belum Selesai
* **Masalah**: Setelah merge status collector, full suite menghasilkan 6 failure di `tests/test_qc_visual_diff.py`; 201 test lain lulus.
* **Root Cause**: Perubahan lokal QC mengubah signature `_change_mask()` agar membutuhkan argumen `valid`, tetapi `_diff_pair()` masih memanggilnya dengan dua argumen. Perubahan QC sudah ada sebelum task status collector dan tidak muncul di worktree terisolasi.
* **Solusi**: Setelah Bima menyetujui perbaikan QC, unpack hasil `_align()` menjadi `(gray_b_aligned, valid)`, teruskan validity mask ke `_change_mask()` dan `_anaglyph()`, lalu tambahkan ECC translation refinement untuk membersihkan residual subpixel setelah homography ORB.
* **Verifikasi**: Test QC fokus lulus 29/29 dan full suite WSL lulus 207/207 dengan 2 warning dependency baseline.

## Log 33: Ruff Tidak Tersedia di Virtual Environment
* **Masalah**: Pemeriksaan lint `ruff check` gagal dengan `ruff: command not found`.
* **Root Cause**: Ruff tidak terpasang di `bima_env` dan proyek tidak mendeklarasikannya sebagai dependency development aktif.
* **Solusi**: Jangan memasang dependency baru hanya untuk cleanup. Gunakan `py_compile`, `git diff --check`, focused pytest, dan full pytest sebagai gate yang tersedia.
