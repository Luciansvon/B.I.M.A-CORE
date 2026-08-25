# Error Solutions

Knowledge base untuk masalah teknis non-trivial yang sudah diinvestigasi. Sebelum mencoba solusi baru, cari berdasarkan pesan error, command, file, service, dependency, dan environment.

Setiap entry wajib memuat gejala, akar masalah, solusi atau mitigasi, serta verifikasi. Variasi kecil dengan akar masalah sama digabung ke entry lama.

ID `ERR-R*` berasal dari log root lama; ID `ERR-D*` berasal dari log `docs/` lama. ID yang digabung tetap dicatat pada field **Legacy IDs** agar referensi historis dapat dilacak.

## ERR-R10 — Healthcheck Menganggap `scripts/` sebagai Root
* **Legacy IDs**: ERR-R27.
* **Masalah**: `scripts/healthcheck.py` mencari `.env`, `main.py`, output, dan indeks di bawah `scripts/`, lalu menghasilkan false critical failure. Import modul juga langsung menjalankan check.
* **Root Cause**: `BASE_DIR` memakai parent langsung file dan eksekusi tidak dibungkus `main()`.
* **Solusi**: Gunakan `Path(__file__).resolve().parent.parent`, pindahkan eksekusi ke `main()`, dan pertahankan helper yang dapat diuji.
* **Verifikasi**: `tests/test_healthcheck.py` memverifikasi root resolution dan status indeks.

## ERR-R11 — Setelan Fallback OCR Kurang Optimal pada core/ocr.py
* **Masalah**: Saat pemanggilan perintah `!ocr` di Discord, jika engine online (Gemini Vision) gagal, sistem melakukan fallback ke `easyocr` yang lambat dan boros resource. Padahal, sistem sudah memiliki `RapidOCR` yang terpasang dan jauh lebih cepat serta akurat di CPU.
* **Solusi**: Ubah kode fallback di `core/ocr.py` agar mengarah ke `extract_text_rapid_async` sebagai opsi utama cadangan offline sebelum beralih ke `easyocr`.

## ERR-R12 — Potensi Crash/Segfault Whisper large-v3-turbo di CPU
* **Masalah**: Setelan default `.env` menggunakan model STT `small` karena model `large-v3-turbo` mengalami segfault di CPU saat dijalankan dengan tipe kompresi `int8` (karena keterbatasan pustaka ctranslate2 di CPU tertentu).
* **Solusi**:
  1. Ubah tipe kompresi `STT_COMPUTE_TYPE` ke `float32` jika ingin tetap menggunakan `large-v3-turbo` di CPU tanpa crash.
  2. Atau, arahkan STT ke GPU dengan menyetel `STT_DEVICE=cuda` dan `STT_COMPUTE_TYPE=float16` jika VRAM GPU RTX 3050 masih mencukupi.

## ERR-R13 — Aturan Agent Duplikat dan Saling Menunjuk
* **Legacy IDs**: ERR-R34.
* **Masalah**: `AGENTS.md`, `CLAUDE.md`, `.clauderules`, dan `user.md` mengulang workflow, safety, gaya respons, serta path error log. `AGENTS.md` mengaku canonical tetapi menunjuk `CLAUDE.md` sebagai aturan utama.
* **Root Cause**: Rules ditambah per tool tanpa satu owner dan tanpa memindahkan informasi domain ke dokumentasi khusus.
* **Solusi**: Jadikan `AGENTS.md` satu-satunya sumber aturan; ubah `CLAUDE.md` menjadi redirect; hapus rules/profile duplikat; pisahkan arsitektur, error knowledge base, dan worklog.
* **Verifikasi**: `.clauderules` dan `user.md` tidak ada; `CLAUDE.md` hanya tiga baris; tujuh dokumen aktif tidak memiliki link rusak atau referensi canonical lama.

## ERR-R14 — Command Rusak saat Melewati PowerShell, WSL, Bash, dan Python
* **Legacy IDs**: ERR-R30, ERR-R48, ERR-R51, ERR-R55, ERR-R67, ERR-R82, ERR-R90, ERR-R97, ERR-R101, ERR-R104, ERR-R106.
* **Masalah**: Nested quote, regex `|`, `$variable`, command substitution, redirect, loop, atau BOM berubah sebelum command mencapai shell tujuan.
* **Root Cause**: Satu command diparse ulang oleh beberapa shell dengan aturan escape dan encoding berbeda.
* **Solusi**: Pakai satu shell end-to-end. Dari Windows, jalankan operasi file langsung di PowerShell pada path UNC atau panggil executable WSL tanpa `bash -lc`; gunakan `python -m py_compile` untuk syntax check. Jika Bash wajib, kirim script UTF-8 tanpa BOM dan hindari interpolasi PowerShell.
* **Known Variations**: Polling loop pecah sebelum `curl`; `$p`/`$resolved` menjadi kosong karena diekspansi PowerShell; here-string PowerShell menambahkan BOM sehingga Bash membaca `set` sebagai command yang rusak.
* **Verifikasi**: Syntax check dan pemeriksaan dokumen berhasil setelah command dipisah per shell.

## ERR-R15 — Path Cache Skill Superpowers Berubah
* **Masalah**: Path skill `using-superpowers` dari sesi sebelumnya mengarah ke hash cache lama (`2f1a8948`) dan tidak ditemukan pada sesi terbaru.
* **Solusi**: Cari ulang file skill aktif dengan `Get-ChildItem -Path C:/Users/shint/.codex/plugins/cache -Recurse -Filter SKILL.md | Where-Object { $_.FullName -match 'using-superpowers' }`, lalu baca path hash terbaru.

## ERR-R16 — Patch Gagal karena Konteks Tidak Sama dengan File
* **Legacy IDs**: ERR-R54, ERR-R61, ERR-R105.
* **Masalah**: Patch gagal pada baris yang tampak sama karena mojibake/emoji, komentar aktual berbeda, atau regex di-escape berlebih.
* **Root Cause**: Hunk memakai konteks rapuh yang tidak identik secara byte dengan isi terbaru.
* **Solusi**: Baca ulang blok aktual, kecilkan hunk, dan gunakan konteks ASCII atau literal stabil yang benar-benar ada.
* **Known Variations**: Emoji tampil mojibake, komentar `.env.example` berbeda, dan bracket regex di-escape dua kali saat menambah log.
* **Verifikasi**: Patch pengganti diterapkan tanpa mengubah blok di luar target; catatan lama berhasil ditambahkan setelah konteks dibuat literal dan minimal.

## ERR-R17 — Staged Diff Gagal Karena Trailing Whitespace
* **Masalah**: `git diff --cached --check` gagal pada `error_solutions.md` karena ada trailing whitespace setelah bullet `* **Solusi**:`.
* **Solusi**: Hapus spasi sisa di akhir baris sebelum commit, lalu jalankan ulang `git diff --cached --check`.

## ERR-R18 — Git Commit Gagal Karena Author Identity Belum Diset
* **Masalah**: `git commit` gagal dengan pesan `Author identity unknown` karena environment ini belum punya `user.name` dan `user.email`.
* **Solusi**: Untuk commit sekali jalan tanpa mengubah global config, jalankan `git -c user.name="Luciansvon" -c user.email="bimachaktiadi.s@gmail.com" commit ...`.

## ERR-R19 — Git Maintenance Gagal Menulis Multi-Pack-Index di Checkout WSL
* **Legacy IDs**: ERR-R98.
* **Masalah**: Commit terbentuk, tetapi auto maintenance Git Windows pada checkout UNC WSL gagal dengan `could not write multi-pack-index: Permission denied`.
* **Root Cause**: Operasi pack lintas filesystem/ownership Windows–WSL gagal, bukan penulisan commit.
* **Solusi**: Verifikasi commit lebih dulu. Gunakan Git WSL untuk maintenance; untuk commit lanjutan yang aman gunakan `-c maintenance.auto=false` bila auto maintenance terus mengganggu.
* **Verifikasi**: Commit tetap ada dan object pack dapat dibaca oleh user WSL.

## ERR-R20 — Belum Ada Jadwal MT Team Mekanik untuk Cek Anisa
* **Masalah**: Anisa sudah punya `observability_scheduler` untuk alert berkala, tetapi belum ada jadwal maintenance rutin bernama Team Mekanik yang mengirim laporan kondisi Anisa pada waktu Bima bisa membaca hasilnya.
* **Solusi**: Tambahkan `core/mekanik_maintenance_scheduler.py` dengan mode report-only pada Senin/Rabu/Jumat pukul 21:30 WIB. Scheduler mengecek CPU/RAM/disk, PM2, GPU VRAM, log error terbaru, dan audit MCP, lalu mengirim laporan ke `BOT_STATUS_CHANNEL_ID` tanpa auto-restart, tanpa write/delete, dan tanpa git action.
* **Verifikasi**: Test RED/GREEN `tests/test_mekanik_maintenance_scheduler.py`, syntax check `python3 -m py_compile core/discord_bot.py core/mekanik_maintenance_scheduler.py`, dan focused pytest setelah implementasi.

## ERR-R21 — PM2 anisa-v3 Berjalan dari Worktree Lama
* **Masalah**: Setelah patch di root `/home/bima_lucian/BIMA_CORE`, `pm2 describe anisa-v3` menunjukkan proses aktif memakai script path `/home/bima_lucian/BIMA_CORE/.worktrees/anisa-desktop/main.py`. Restart biasa tidak mengaktifkan patch root karena PM2 tetap menjalankan worktree tersebut.
* **Solusi**: Mirror patch runtime minimal ke `.worktrees/anisa-desktop` yang sedang dipakai PM2, compile file di worktree, lalu restart `anisa-v3`. Untuk jangka panjang, samakan lagi PM2 process dengan `ecosystem.config.js` root atau putuskan worktree mana yang jadi production source.
* **Verifikasi**: `pm2 logs anisa-v3 --nostream` menampilkan `[MEKANIK_MT] Scheduler aktif: mon,wed,fri 21:30 WIB` pada startup baru.

## ERR-R22 — Switch PM2 ke Root Berisiko Karena Branch Production Berbeda
* **Masalah**: Root repo berada di branch `feature/last30days`, sedangkan PM2 production aktif berada di `.worktrees/anisa-desktop` branch `feature/anisa-desktop`. Diff antar branch besar dan menyentuh desktop app/API, permission gate, threads, dan config, sehingga memaksa `anisa-v3` pindah ke root bisa menurunkan fitur production yang sedang dipakai.
* **Solusi**: Jangan switch runtime ke root dulu. Reload `anisa-v3` memakai `.worktrees/anisa-desktop/ecosystem.config.js`, lalu jalankan `pm2 save` agar PM2 dump persist ke source production aktif. Rencana switch/merge ke root perlu kerja terpisah setelah branch disatukan.
* **Verifikasi**: `pm2 describe anisa-v3` tetap menunjukkan script path `.worktrees/anisa-desktop/main.py`, `/home/bima_lucian/.pm2/dump.pm2` berisi path tersebut, dan log startup menampilkan `[MEKANIK_MT] Scheduler aktif: mon,wed,fri 21:30 WIB`.

## ERR-R23 — Pipeline `pm2 prettylist` Memicu EPIPE
* **Masalah**: Command eksplorasi `pm2 prettylist | python3 - <<'PY' ...` memutus pipe terlalu cepat sehingga proses Node PM2 menulis ke pipe tertutup dan melempar `Error: write EPIPE`.
* **Solusi**: Jangan pipe output PM2 besar ke heredoc Python kosong. Untuk inspeksi process metadata, gunakan `pm2 describe <name>`, `pm2 jlist > /tmp/pm2.json`, atau parse `pm2 jlist` dari file sementara.

## ERR-R24 — `bima-whatsapp` Crash Loop Karena Dependency Node Hilang
* **Masalah**: PM2 menampilkan `bima-whatsapp` status `waiting restart` dengan restart count tinggi. Log terbaru berulang kali menunjukkan `Error: Cannot find module 'whatsapp-web.js'` dari `/home/bima_lucian/BIMA_CORE/whatsapp/index.js:17`.
* **Root Cause**: `whatsapp/package.json` sudah mendeklarasikan `whatsapp-web.js`, tetapi folder `whatsapp/node_modules/` tidak ada. Syntax `whatsapp/index.js` valid, jadi crash berasal dari dependency runtime yang belum terinstall.
* **Solusi**: Setelah approval Bima, stop crash loop dengan `pm2 stop bima-whatsapp`, jalankan `npm ci` dari folder `whatsapp/`, lalu `pm2 restart bima-whatsapp --update-env` dan `pm2 save`. Jika session WA perlu login ulang, scan QR dari `outputs/wa_qr.png`.
* **Verifikasi**: `pm2 describe bima-whatsapp` status `online`, log baru menampilkan `Auth OK` dan `Anisa WA Bridge ONLINE`, `npm ls whatsapp-web.js --depth=0` menampilkan `whatsapp-web.js@1.34.7`, dan backend WA `/health` mengembalikan `{"status":"ok","busy":false}`.

## ERR-R25 — Dependency Transitive WhatsApp Berada di Vulnerable Range
* **Legacy IDs**: ERR-R29.
* **Masalah**: `npm audit` menemukan vulnerability pada `form-data`, `js-yaml`, dan `ws` di lockfile WhatsApp.
* **Root Cause**: Versi transitive terkunci pada range yang memiliki advisory.
* **Solusi**: Jangan mengubah lockfile saat recovery service. Dalam task dependency terpisah, jalankan `npm audit fix` tanpa `--force`, review diff, lalu uji bridge.
* **Verifikasi**: Lockfile terbarui ke `form-data@4.0.6`, `js-yaml@4.3.0`, dan `ws@8.21.0`; `npm audit --audit-level=moderate` bersih dan `node --check whatsapp/index.js` lulus.

## ERR-R26 — Path Linux Tidak Ditemukan di Environment Agent Windows
* **Masalah**: Pencarian atau pembacaan file dengan path `/Ubuntu/home/bima_lucian/BIMA_CORE` atau `/home/bima_lucian/BIMA_CORE` menghasilkan error karena sistem operasi host adalah Windows.
* **Solusi**: Gunakan path jaringan Windows `\\wsl.localhost\Ubuntu\home\bima_lucian\BIMA_CORE` untuk berinteraksi dengan workspace WSL dari host Windows.

## ERR-R28 — Agent Tidak Memiliki Snapshot Operasional Ringkas
* **Masalah**: Agent harus menjalankan banyak command atau scan folder untuk mengetahui kondisi Anisa.
* **Root Cause**: Status CPU/RAM/disk hanya tersedia on-demand dan tidak ada kontrak status tunggal yang persisten.
* **Solusi**: Tambahkan sidecar `anisa-status` yang menulis `runtime/anisa_status.json` secara atomic setiap 30 detik. Snapshot berisi PM2, resource, backend, indeks, Git, dan error tersanitasi; data dianggap stale setelah 90 detik.
* **Verifikasi**: `pytest tests/test_operational_status.py -q` menghasilkan 6 test lulus dan one-shot CLI menghasilkan JSON valid.

## ERR-R31 — status_collector.py Tidak Bisa Import core Saat Dijalankan Langsung
* **Masalah**: `python scripts/status_collector.py` gagal dengan `ModuleNotFoundError: No module named 'core'`.
* **Root Cause**: Saat file di folder `scripts/` dijalankan langsung, Python menempatkan folder `scripts/` sebagai import root, bukan root repository.
* **Solusi**: Resolusi `PROJECT_ROOT` dilakukan sebelum import internal, lalu root ditambahkan ke `sys.path`. Tambahkan mode `--once` untuk smoke test deterministik.
* **Verifikasi**: Regression test `test_status_collector_supports_one_shot_cli` gagal sebelum fix dan lulus setelah fix.

## ERR-R32 — Full Pytest Root Gagal pada Perubahan QC yang Belum Selesai
* **Masalah**: Setelah merge status collector, full suite menghasilkan 6 failure di `tests/test_qc_visual_diff.py`; 201 test lain lulus.
* **Root Cause**: Perubahan lokal QC mengubah signature `_change_mask()` agar membutuhkan argumen `valid`, tetapi `_diff_pair()` masih memanggilnya dengan dua argumen. Perubahan QC sudah ada sebelum task status collector dan tidak muncul di worktree terisolasi.
* **Solusi**: Setelah Bima menyetujui perbaikan QC, unpack hasil `_align()` menjadi `(gray_b_aligned, valid)`, teruskan validity mask ke `_change_mask()` dan `_anaglyph()`, lalu tambahkan ECC translation refinement untuk membersihkan residual subpixel setelah homography ORB.
* **Verifikasi**: Test QC fokus lulus 29/29 dan full suite WSL lulus 207/207 dengan 2 warning dependency baseline.

## ERR-R35 — Dokumentasi Menunjuk Healthcheck yang Tidak Ada
* **Legacy IDs**: ERR-R66.
* **Masalah**: `python healthcheck.py` gagal karena file tidak ada di root.
* **Root Cause**: Implementasi berada di `scripts/healthcheck.py`, tetapi dokumentasi memakai path lama.
* **Solusi**: Gunakan `bima_env/bin/python scripts/healthcheck.py` dan validasi path command terhadap repository.
* **Verifikasi**: `AGENTS.md` dan `README.md` memakai path aktual; command dijalankan pada verification dokumentasi.

## ERR-R36 — Tool Dev Tidak Terpasang di Environment Production
* **Legacy IDs**: ERR-R33, ERR-R86.
* **Masalah**: `ruff` atau `pip-audit` tidak ditemukan di `bima_env` walau terdaftar sebagai dependency development.
* **Root Cause**: Environment production tidak memasang group `dev`; ini tidak berarti manifest atau source rusak.
* **Solusi**: Jangan install tool ke production hanya untuk satu check. Gunakan `uvx <tool>` secara terisolasi atau environment dev/CI yang disinkronkan dari lockfile; pakai `py_compile`, pytest, dan `git diff --check` bila itu gate yang tersedia.
* **Verifikasi**: `pyproject.toml` memiliki group `dev` dan CI memasangnya melalui group `ci`.

## ERR-R37 — Audit Dependency Outdated via pip Timeout
* **Masalah**: `pip list --outdated --format=json` tidak selesai dalam 60 detik.
* **Root Cause**: Environment memiliki ratusan paket ML/CUDA dan pip memeriksa metadata secara lambat.
* **Solusi**: Gunakan executable lokal `bima_env/bin/uv pip list --python bima_env/bin/python --outdated`; audit ini selesai sekitar 16 detik.

## ERR-R38 — GitHub API Date Gagal Diformat PowerShell
* **Masalah**: Pemanggilan `.ToString('yyyy-MM-dd')` pada tanggal GitHub API gagal.
* **Root Cause**: `Invoke-RestMethod` mengembalikan field tanggal sebagai string pada host PowerShell ini.
* **Solusi**: Perlakukan nilai sebagai string ISO dan ambil 10 karakter pertama, atau parse eksplisit dengan `[datetime]::Parse()`.

## ERR-R39 — uv audit Tidak Bisa Berjalan Tanpa Project Metadata
* **Masalah**: `uv audit --frozen` gagal dengan `No pyproject.toml found`.
* **Root Cause**: BIMA_CORE masih memakai requirements bebas versi dan belum menjadi project uv yang dapat dikunci.
* **Solusi**: Buat `pyproject.toml` + `uv.lock`, lalu jalankan `uv audit --frozen` di CI dan lokal.

## ERR-R40 — AgentMemory Mati Karena Cache npx Korup
* **Masalah**: Launcher mencatat AgentMemory berhasil di-spawn, tetapi port 3111 tidak listen dan semantic recall memakai fallback.
* **Root Cause**: `npx -y @agentmemory/agentmemory` berulang kali gagal rename cache dengan `ENOTEMPTY` pada `~/.npm/_npx/.../@agentmemory/agentmemory`.
* **Solusi**: Setelah approval instalasi, pasang dan pin `@agentmemory/agentmemory@0.9.27` sekali, jalankan executable sebagai proses PM2 terpisah, dan tambahkan readiness check sebelum dianggap sehat. Pembersihan cache npx bersifat destruktif dan hanya dilakukan dengan approval eksplisit.

## ERR-R41 — Dependency Terbaru Tidak Bisa Disatukan dalam Satu Environment
* **Masalah**: Dry-run CrewAI 1.15.2 + Browser Use 0.13.3 gagal diselesaikan; kombinasi dengan F5-TTS juga gagal.
* **Root Cause**: CrewAI meminta `openai>=2.30,<3`, Browser Use mengunci `openai==2.16.0`, serta Browser Use/F5-TTS bertabrakan pada `rich`, `cached-path`, dan `tqdm`.
* **Solusi**: Pisahkan `core-env`, `browser-env`, dan `voice-env`; pin masing-masing dengan lockfile. Hubungkan browser dan voice sebagai subprocess/service dengan kontrak sempit.

## ERR-R42 — Environment Aktif Memiliki Sembilan Konflik Dependency
* **Legacy IDs**: ERR-R77, ERR-R92.
* **Masalah**: `pip check`/`uv pip check` melaporkan incompatibility pada pyarrow, protobuf, lance-namespace, rich, fsspec, aiofiles, Starlette, dan Torch/Torchvision.
* **Root Cause**: `bima_env` dibentuk bertahap dan memuat package di luar metadata/lock aktif.
* **Solusi**: Jangan auto-sync production. Lengkapi metadata, bangun environment baru dari lockfile, lalu jalankan import smoke, feature-specific test, full pytest, dan service smoke sebelum switch PM2.
* **Verifikasi**: `uv lock --check` lulus, tetapi environment aktif tetap dilaporkan berbeda sampai migrasi terkontrol dilakukan.

## ERR-R43 — SQLite MCP Aktif Berasal dari Repo Arsip
* **Masalah**: `mcp-server-sqlite` aktif dan memberi tool write/create table, padahal upstream memindahkannya ke repository archived tanpa security update.
* **Root Cause**: `config_mcp.json` dibuat saat SQLite masih dicontohkan sebagai reference server dan tidak pernah diaudit ulang terhadap registry terbaru.
* **Solusi**: Nonaktifkan SQLite MCP, gunakan fungsi internal dengan query allowlist, serta pin semua package `npx`/`uvx` yang tetap digunakan.

## ERR-R44 — Git MCP Tidak Masuk ke Agen Kodok
* **Masalah**: Startup mencatat `[mcp_inject] agent 'kodok' tidak dikenal, skip` sehingga 12 Git tools tidak tersedia.
* **Root Cause**: `config_mcp.json` menargetkan `kodok`, tetapi `_AGENT_REGISTRY` di `main.py` tidak memiliki mapping `teams.t10_kodok:kodok_agent`.
* **Solusi**: Tambahkan mapping Kodok dan regression test untuk seluruh nilai `attach_to` agar selalu ada di registry.

## ERR-R45 — LanceDB Diinisialisasi Sebelum Fork Subprocess MCP
* **Legacy IDs**: ERR-R69, ERR-R72.
* **Masalah**: Startup menampilkan warning runtime LanceDB di-reset setelah fork; menunda thread index saja belum cukup.
* **Root Cause**: Import top-level `lancedb` menginisialisasi runtime native sebelum MCP child selesai dibuat.
* **Solusi**: Lazy-import `lancedb` di fungsi koneksi dan mulai re-index/warmup setelah startup MCP. Jika warning kembali, isolasi LanceDB ke proses `spawn`/`forkserver` yang diuji.
* **Verifikasi**: Startup setelah lazy import bersih dan index Arsip tetap menghasilkan 897 dokumen BM25.

## ERR-R46 — Scheduler Berulang Kali Terlambat
* **Masalah**: Observability, Threads scan, dan paper trading terlambat sekitar 23–77 detik pada banyak siklus.
* **Root Cause**: Event loop utama mengalami stall; audit belum membuktikan call site tunggal karena beberapa job CPU/sync berjalan bersamaan.
* **Solusi**: Tambahkan metrik event-loop lag dan profil dengan `pyinstrument` yang sudah terpasang. Pindahkan kerja CPU/sync terberat ke worker terpisah berdasarkan hasil profil, lalu set `coalesce`, `max_instances`, dan `misfire_grace_time` secara eksplisit.
* **Mitigasi Terverifikasi (2026-07-20)**: Scheduler saham memakai `misfire_grace_time=120`, `coalesce=True`, dan `max_instances=1`, sehingga tick yang terlambat sampai dua menit tetap dijalankan tanpa menumpuk. Setiap tick paper trader juga menulis log saat selesai tanpa transaksi.
* **Verifikasi**: Focused suite scheduler dan paper trader lulus `13 passed`; `anisa-v3` kembali online dari `/home/bima_lucian/BIMA_CORE/main.py`. Tick live 12:45 mengeksekusi BUY paper `ETH-USD`, tick IDX selesai tanpa transaksi, dan tidak ada warning `_paper_trading_tick ... was missed` setelah patch. Event-loop stall umum belum dinyatakan selesai dan tetap perlu profiling.

## ERR-R47 — Prefix Dashboard API Token Masuk Log
* **Masalah**: Startup menulis delapan karakter awal `DASHBOARD_API_TOKEN` ke log.
* **Root Cause**: `core/dashboard_server.py` menggunakan `_API_TOKEN[:8]` untuk indikator token loaded.
* **Solusi**: Log hanya status boolean/token source tanpa karakter token dan rotasi token bila log pernah dibagikan ke pihak lain.

## ERR-R49 — Test MCP yang Diasumsikan Ternyata Tidak Ada
* **Masalah**: Pembacaan `tests/test_mcp_client_manager.py` gagal karena file belum ada.
* **Root Cause**: Audit mengasumsikan MCP manager sudah punya unit test berdasarkan nama modul production.
* **Solusi**: Cari test dengan `rg --files tests | rg 'mcp'` sebelum membaca; buat test baru hanya setelah memastikan coverage memang belum ada.

## ERR-R50 — Instalasi AgentMemory Melewati Timeout Tool
* **Masalah**: `npm install` melewati 60 detik dan tool mengembalikan timeout, tetapi proses WSL tetap berjalan di background.
* **Root Cause**: AgentMemory menarik dependency ONNX/transformers besar; wrapper timeout Windows tidak langsung menghentikan child WSL.
* **Solusi**: Periksa PID, log npm, dan keberadaan lockfile sebelum retry. Instalasi akhirnya menghasilkan `package-lock.json` dan AgentMemory 0.9.27 tanpa menjalankan install kedua.

## ERR-R52 — Sinkronisasi Voice Environment Sangat Lama
* **Masalah**: `uv sync` voice-env berjalan lebih dari 15 menit dan menulis beberapa GB cache sebelum dihentikan.
* **Root Cause**: F5-TTS + PyTorch CUDA membutuhkan wheel besar, sementara beberapa proses download berjalan bersamaan.
* **Solusi**: Jalankan satu sync besar pada satu waktu, gunakan cache uv yang sudah terisi, dan beri window eksekusi khusus. Jangan switch PM2 ke voice-env sebelum executable F5 dan import smoke terverifikasi.

## ERR-R53 — AgentMemory `--instance 1` Tidak Merelokasi Engine
* **Masalah**: CLI menunggu health port 3211, tetapi iii-engine tetap membuka 3111/49134 dari config statis lalu smoke test timeout.
* **Root Cause**: AgentMemory 0.9.27 tidak menerapkan offset instance ke port eksplisit di bundled `iii-config.yaml` pada setup ini.
* **Solusi**: Deployment BIMA memakai default port 3111. Smoke test default berhasil `healthy`; proses uji kemudian dihentikan dengan `agentmemory stop --force` agar state di-flush.

## ERR-R56 — CI Lock Bersih Belum Memuat Runtime Import Test
* **Masalah**: Test dari environment CI terisolasi gagal collection pada lima modul walau `uv pip check` bersih.
* **Root Cause**: CrewAI OpenRouter membutuhkan `litellm` yang tidak tercantum langsung, dan test paper trading mengimpor `yfinance` yang sebelumnya dikeluarkan dari subset CI.
* **Solusi**: Tambahkan dependency eksplisit `litellm` ke core/CI serta `yfinance` ke group CI, lock ulang, lalu jalankan full test dari `.venv`. Jangan menyatakan CI pulih sebelum 207+ test lulus dari environment bersih.

## ERR-R57 — Patch Dependency CI Memakai Konteks Versi Lama
* **Masalah**: Patch awal `pyproject.toml` gagal menemukan baris LanceDB dan MCP yang diharapkan.
* **Root Cause**: Konteks patch berasal dari ringkasan versi sebelumnya, sedangkan file aktual sudah memakai `lancedb==0.34.0` dan `mcpadapt`.
* **Solusi**: Baca ulang file aktual lalu sisipkan dependency berdasarkan baris `mcpadapt` dan batas group CI yang benar.

## ERR-R58 — Full Test CI Menemukan Import pandas-ta Berikutnya
* **Masalah**: Setelah `litellm` dan `yfinance` tersedia, collection full test masih berhenti pada `ModuleNotFoundError: pandas_ta` dari `teams/t9_saham.py`.
* **Root Cause**: `pandas-ta` ada di dependency runtime utama tetapi belum dimasukkan ke subset dependency group CI.
* **Solusi**: Tambahkan pin `pandas-ta==0.4.71b0` ke group CI, lock dan sync ulang, lalu ulang full test. Perubahan ditahan sampai kegagalan baru ini disetujui sesuai verification gate repo.

## ERR-R59 — Pemeriksaan Cache Voice Gabungan Timeout
* **Masalah**: Setelah sync voice melewati batas tool, command pemeriksaan `pgrep`, dua `du`, dan `df` ikut timeout tanpa hasil.
* **Root Cause**: `du` rekursif pada cache uv yang besar membuat pemeriksaan gabungan melewati batas waktu, sehingga status proses tidak terlihat.
* **Solusi**: Jangan gabungkan scan cache besar dengan pemeriksaan proses. Cek PID dan filesystem memakai command terpisah, lalu lanjutkan sync dengan mekanisme yield yang tidak mematikan proses.

## ERR-R60 — PowerShell Select-Object Range Tidak Diparentesiskan
* **Masalah**: Pembacaan potongan `.env.example` gagal karena `Select-Object -Index 100..130` dianggap satu string.
* **Root Cause**: PowerShell membutuhkan ekspresi range dibungkus kurung saat dipakai sebagai nilai parameter.
* **Solusi**: Gunakan `Select-Object -Index (100..130)` atau `sed -n` melalui WSL.

## ERR-R62 — Gate Paralel Kehilangan Output karena Git Windows pada UNC Worktree
* **Masalah**: Eksekusi gate paralel batal saat `git diff --check` lewat Git Windows menganggap worktree UNC bukan repository; output test paralel ikut tidak terkumpul.
* **Root Cause**: Worktree dibuat di filesystem WSL, tetapi satu command Git dijalankan dari host Windows.
* **Solusi**: Jalankan semua command Git worktree melalui `wsl.exe --cd`, cek proses pytest yang tertinggal, lalu ulang full test secara tunggal agar exit code dan jumlah test tercatat.

## ERR-R63 — Installer Runtime Paralel Melewati Timeout Wrapper
* **Masalah**: `uv sync` browser dan `npm ci` AgentMemory melewati timeout parent 120 detik sehingga output gabungan hilang.
* **Root Cause**: Instalasi npm tetap berjalan sebagai proses WSL setelah wrapper host berhenti menunggu.
* **Solusi**: Cek PID sebelum retry. Browser diverifikasi dari metadata environment; proses npm ditunggu sampai selesai lalu diverifikasi dengan `npm ls`.

## ERR-R64 — browser_use Tidak Memiliki Atribut __version__
* **Masalah**: Smoke test import browser gagal ketika membaca `browser_use.__version__`.
* **Root Cause**: Paket Browser Use 0.13.3 tidak mengekspos atribut versi pada modul top-level.
* **Solusi**: Baca versi terpasang memakai `importlib.metadata.version('browser-use')`; hasilnya Browser Use 0.13.3 dan OpenAI 2.16.0.

## ERR-R65 — AgentMemory Membawa Vulnerability Transitive
* **Masalah**: `npm audit --audit-level=high` menemukan 15 vulnerability: 10 moderate, 4 high, dan 1 critical.
* **Root Cause**: `@agentmemory/agentmemory@0.9.27` membawa rantai `iii-sdk`, OpenTelemetry lama, serta `@xenova/transformers`/`onnxruntime-web` dengan `protobufjs` rentan.
* **Solusi**: Jangan start AgentMemory di PM2. Tahan service sampai versi upstream aman atau dependency override tervalidasi; backend utama tetap dapat berjalan dengan status degraded.
* **Verifikasi 2026-07-15**: 0.9.27 masih versi terbaru, `AGENTMEMORY_ENABLED` tidak disetel, dan `npm audit fix --dry-run --json` tetap menyisakan 15 vulnerability. Package AgentMemory membawa override `protobufjs`, tetapi npm hanya menerapkan `overrides` dari root project; uji root override atau versi upstream baru di environment terpisah sebelum service diaktifkan.

## ERR-R68 — Parser Status Menganggap services Berbentuk List
* **Masalah**: Pembacaan snapshot berhasil mencetak `degraded`, lalu gagal saat memanggil `.get()` pada nama service.
* **Root Cause**: Field `services` adalah map `{nama: status}`, bukan list objek.
* **Solusi**: Baca map langsung. Snapshot membuktikan backend/WA/tunnel online dan AgentMemory unknown sehingga overall degraded.

## ERR-R70 — Audit Dry-run Membatalkan Output Investigasi Paralel
* **Masalah**: `npm audit fix --dry-run --json` exit 1 karena vulnerability belum terselesaikan, sehingga output query versi dan trace LanceDB dalam batch paralel tidak terkumpul.
* **Root Cause**: Orkestrasi batch menghentikan hasil agregat ketika salah satu command menghasilkan exit nonzero yang memang diharapkan dari audit.
* **Solusi**: Jalankan query versi dan trace satu per satu. Hasil resmi npm: AgentMemory 0.9.27 masih versi terbaru dan vulnerability direct tidak punya fix otomatis.

## ERR-R71 — Ruff main.py Menemukan E402 Baseline
* **Masalah**: Ruff pada semua file tersentuh menemukan empat E402 di `main.py`.
* **Root Cause**: `uvloop.install()`, Sentry, dan konfigurasi logging sengaja dijalankan sebelum import modul aplikasi; pola ini sudah ada sebelum perbaikan LanceDB.
* **Solusi**: Jangan memindahkan urutan startup hanya untuk lint. Jalankan Ruff pada file logika yang berubah; full pytest dan startup production menjadi gate untuk `main.py`.

## ERR-R73 — Alert Security Repo Publik Tidak Bisa Dibaca
* **Masalah**: Audit `modiqo/waggle` mendapat HTTP 403 saat meminta Code Scanning dan Dependabot alerts.
* **Root Cause**: Endpoint alert GitHub hanya dapat dibaca dengan izin admin repository; autentikasi lokal bukan pemilik repo tersebut.
* **Solusi**: Jangan menyimpulkan repo bebas vulnerability. Nilai source, workflow, dan release publik; minta maintainer mengekspor alert atau lakukan scanner lokal pada source yang dipin bila audit lebih lanjut disetujui.

## ERR-R74 — `jq` Tidak Tersedia di WSL
* **Masalah**: Parsing hasil benchmark Waggle gagal dengan `jq: command not found`.
* **Root Cause**: Environment WSL tidak memasang executable `jq`, meskipun `gh --jq` memiliki evaluator internal.
* **Solusi**: Gunakan `gh api ... --jq '<expression>'` langsung agar tidak membutuhkan dependency tambahan.

## ERR-R75 — `gh` Hilang dari PATH WSL Non-login
* **Masalah**: `wsl.exe -d Ubuntu -- gh api ...` gagal dengan `gh: command not found`, padahal command yang sama tersedia melalui shell login.
* **Root Cause**: Invocation WSL non-login tidak memuat konfigurasi PATH tempat GitHub CLI terpasang.
* **Solusi**: Jalankan `gh` melalui `wsl.exe -d Ubuntu -- bash -lc "gh api ..."` pada environment ini.

## ERR-R76 — Reader PM2 Observability Selalu Mengembalikan Kosong
* **Masalah**: `core/observability_scheduler._get_pm2_status()` mengembalikan `[]`, sehingga scheduler tidak dapat mendeteksi proses PM2 yang offline.
* **Root Cause**: `subprocess.run(["pm2", "jlist"], shell=True)` memakai list argumen bersama shell pada POSIX. `pm2` dijalankan tanpa subcommand `jlist`, output bukan JSON, lalu exception disembunyikan oleh safe-fail.
* **Solusi**: Hapus `shell=True`, pertahankan argv `['pm2', 'jlist']`, log warning saat command/JSON gagal, dan tambah regression test yang memastikan empat proses dapat diparse.
* **Verifikasi**: Reader observability menghasilkan `[]`; reader maintenance dengan command tanpa shell menghasilkan empat proses `stopped` pada PM2 yang sama.

## ERR-R78 — Audit Python Menemukan Tiga Package Rentan
* **Masalah**: `uv audit --frozen` menemukan 5 record advisory yang mewakili 3 package: `chromadb==1.1.1`, `diskcache==5.6.3`, dan `json-repair==0.25.2`.
* **Root Cause**: ChromaDB masuk transitif dari CrewAI dan belum punya patched release; DiskCache memakai pickle untuk cache lokal; json-repair versi lama rentan CPU DoS melalui circular schema `$ref`.
* **Solusi**: Jangan expose Chroma server dan tunggu/validasi upstream fix; batasi write access cache DiskCache serta rencanakan serializer aman; constraint json-repair ke `>=0.60.1` hanya setelah compatibility test CrewAI dan Furniture QC.
* **Verifikasi**: Dependency tree menunjukkan ChromaDB/json-repair dari `crewai==1.6.1`, sedangkan DiskCache adalah dependency langsung. Pemakaian json-repair di Furniture QC tidak memberi argumen schema, jadi jalur DoS spesifik tidak langsung terbuka di call site itu.

## ERR-R79 — Bandit Menemukan Security Debt pada Source
* **Masalah**: Bandit memindai 20.639 baris dan melaporkan 99 low, 13 medium, serta 7 high.
* **Root Cause**: Lima high MD5 dipakai hanya untuk slug filename dan merupakan false positive kriptografi. Risiko nyata mencakup `shell=True` di observability/cloud backup, pickle load indeks BM25, dan download model Hugging Face tanpa revision pin.
* **Solusi**: Perbaiki observability sesuai Log 76; ubah helper Git backup menjadi argv tanpa shell; pin commit model melalui `TTS_HF_REVISION`; dan rebuild/validasi indeks BM25 dari corpus tepercaya sebelum load. Jangan mass-suppress dengan `# nosec`.
* **Verifikasi**: Full pytest tetap lulus 299 test dan MCP audit secure; audit ini report-only sehingga source belum diubah.

## ERR-R80 — Git WSL Membaca 63 File Berubah karena Mismatch CRLF
* **Masalah**: `git diff --check` melalui Git WSL melaporkan trailing whitespace pada ribuan baris dan `git status` melihat 63 file berubah, sementara Git Windows hanya melihat 5 entry workspace.
* **Root Cause**: Git Windows memakai system config `core.autocrlf=true`; Git WSL tidak mempunyai nilai `core.autocrlf`. Perbedaan normalisasi line-ending membuat file CRLF lama terlihat berubah penuh dari WSL.
* **Solusi**: Jangan normalisasi massal dalam task maintenance. Gunakan Git Windows untuk gate worktree ini atau buat task terpisah untuk `.gitattributes` dan migrasi line-ending terkontrol.
* **Verifikasi**: `git diff --check -- error_solutions.md` via Git Windows bersih dan tiga dokumen audit tidak memiliki trailing spaces; mismatch global WSL tetap dilaporkan apa adanya.

## ERR-R83 — Glob `*.md` Tidak Diterima `rg` pada Path Windows
* **Masalah**: `rg ... docs *.md` menghasilkan error nama file/path tidak valid.
* **Root Cause**: Wildcard positional `*.md` tidak diekspansi seperti di Bash pada invocation PowerShell tersebut.
* **Solusi**: Gunakan filter ripgrep `-g '*.md'` dengan root pencarian eksplisit.

## ERR-R84 — Hasil `foreach` PowerShell Tidak Bisa Langsung Dipipe
* **Masalah**: Loop metadata GitHub diikuti `| Format-Table` menghasilkan `An empty pipe element is not allowed`.
* **Root Cause**: Statement `foreach (...) { ... }` tidak diperlakukan sebagai ekspresi pipeline pada bentuk command tersebut.
* **Solusi**: Simpan hasil loop ke variabel (`$rows = foreach (...) { ... }`), lalu pipe `$rows` ke formatter.

## ERR-R85 — Operator Null-Coalescing Tidak Didukung PowerShell Host
* **Masalah**: Audit schema memakai operator `??` dan berhenti dengan parser error.
* **Root Cause**: PowerShell host yang menjalankan command belum mendukung operator null-coalescing tersebut.
* **Solusi**: Gunakan pemeriksaan kompatibel `$keys.ContainsKey($k)` dan percabangan eksplisit sebagai pengganti `??`.
* **Verifikasi**: Audit schema berjalan setelah operator diganti tanpa mengubah data yang diperiksa.

## ERR-R87 — Filter Obsidian Base Menghasilkan Escape YAML Berlebih
* **Masalah**: Test `.base` menemukan expression folder tersimpan dengan backslash escape sehingga bentuknya tidak mengikuti format Base yang mudah dibaca.
* **Root Cause**: Expression YAML dibungkus memakai `json.dumps`, sehingga quote di dalam expression ikut di-escape.
* **Solusi**: Tulis scalar YAML dengan single quote dan escape single quote YAML secara eksplisit.
* **Verifikasi**: Lima test Obsidian lulus, termasuk view, traversal, overwrite, Canvas ID, dan edge.

## ERR-R88 — DuckDB Grouping Tidak Mengembalikan Kolom Grup
* **Masalah**: Agregasi `sum` per kategori hanya mengembalikan kolom `value`, bukan `category` dan `value`.
* **Root Cause**: `DuckDBPyRelation.aggregate()` memakai argumen kedua hanya sebagai group expression; kolom grup tetap harus dicantumkan pada projection agregasi.
* **Solusi**: Masukkan identifier grup tervalidasi ke expression hasil sekaligus ke `group_expr`.
* **Verifikasi**: Sembilan test DuckDB lulus untuk CSV, Parquet, lima operasi allowlist, group, output CSV, path, schema, dan limit.

## ERR-R89 — Ruff Gate Terhalang Lint Debt Lama Mekanik
* **Masalah**: Ruff pada semua file tersentuh melaporkan tujuh error.
* **Root Cause**: Enam error sudah ada pada `teams/t8_mekanik.py` di HEAD sebelum task; satu error baru adalah import `os` yang tidak terpakai di test Strix.
* **Solusi**: Hapus hanya import baru milik task dan jangan melakukan drive-by cleanup pada enam error lama.
* **Verifikasi**: Seluruh file Python baru dan file registrasi selain Mekanik lulus Ruff; scan terhadap versi HEAD Mekanik mereproduksi enam error yang sama.

## ERR-R91 — Docker CLI Belum Tersedia untuk Strix
* **Masalah**: Preflight Strix aktual mengembalikan `Docker CLI belum terpasang di WSL`.
* **Root Cause**: Host WSL belum mempunyai Docker CLI/daemon yang dapat dipakai Strix.
* **Solusi**: Pertahankan `STRIX_ENABLED=false`; pasang/aktifkan Docker secara terpisah sebelum scan end-to-end pertama.
* **Verifikasi**: Wrapper berhenti aman sebelum snapshot dikirim atau API dipanggil; tujuh unit test Strix tetap lulus.

## ERR-R93 — Healthcheck Salah Menandai Vault OneDrive WSL
* **Masalah**: Healthcheck menganggap setiap path `/mnt/c/` sebagai konfigurasi Windows yang salah walau vault OneDrive dapat diakses.
* **Root Cause**: `_check_vault()` memeriksa prefix mount sebelum memeriksa keberadaan path.
* **Solusi**: Nilai kesehatan vault dari akses filesystem; path mount WSL yang ada dinyatakan sehat.
* **Verifikasi**: Regression test baru lulus dan healthcheck melaporkan `Vault accessible` pada vault OneDrive aktif.

## ERR-R94 — `uv lock` Menulis Ulang Marker CUDA yang Tidak Terkait
* **Masalah**: Penambahan DuckDB ikut mengubah marker platform optional CUDA pada package lain.
* **Root Cause**: Versi `uv` saat ini menormalisasi ulang marker lama ketika lockfile dibuat ulang.
* **Solusi**: Kembalikan marker CUDA ke isi sebelumnya dan pertahankan hanya entry DuckDB beserta referensinya.
* **Verifikasi**: Diff lockfile tidak lagi membawa perubahan marker CUDA dan `uv lock --check` tetap lulus.

## ERR-R95 — DuckDB Melempar Exception pada Agregasi Tipe String
* **Masalah**: Operasi `sum` terhadap kolom VARCHAR melempar `BinderException` keluar dari tool dan dapat memutus eksekusi agent.
* **Root Cause**: Error DuckDB tidak termasuk dalam tuple exception yang dikonversi menjadi respons `FAILED`.
* **Solusi**: Import DuckDB sebagai dependency runtime dan tangkap `duckdb.Error` bersama error input/path.
* **Verifikasi**: Regression test kolom string gagal sebelum perbaikan lalu lulus; total test DuckDB menjadi 10.

## ERR-R96 — PM2 Tidak Mempunyai Process `anisa-v3`
* **Masalah**: `pm2 restart anisa-v3 --update-env` gagal dengan `Process or Namespace anisa-v3 not found`.
* **Root Cause**: Daemon PM2 aktif tetapi process list kosong, sehingga tidak ada process yang dapat di-restart.
* **Solusi**: Jalankan deklarasi resmi `pm2 start ecosystem.config.js`, bukan membuat command process manual.
* **Verifikasi**: `anisa-v3`, `bima-tunnel`, `bima-whatsapp`, dan `anisa-status` online tanpa restart loop; endpoint 8000 dan 8001 merespons.

## ERR-R99 — JSON PM2 Mengandung UTF-8 BOM
* **Masalah**: Parser Python gagal membaca output `pm2 jlist` dengan `JSONDecodeError: Unexpected UTF-8 BOM`.
* **Root Cause**: Pipeline PowerShell/WSL meneruskan BOM di awal stream JSON, sedangkan `json.load(sys.stdin)` memakai decoder UTF-8 biasa.
* **Solusi**: Untuk status singkat gunakan `pm2 status`, atau decode byte stream dengan `utf-8-sig` sebelum `json.loads`.
* **Verifikasi**: Status PM2 sebelumnya menunjukkan empat process online; smoke endpoint port 8000 dan 8001 tetap sukses pada pemeriksaan yang sama.

## ERR-R100 — WhatsApp Bridge Mengirim `❌ Error: r` Berulang
* **Masalah**: Satu kegagalan WhatsApp Web memicu ratusan balasan `❌ Error: r` melalui event `message_create`.
* **Root Cause**: Handler memanggil `msg.getChat()` sebelum menyaring event balasan bot. Saat `getChat()` melempar `r`, blok `catch` membalas error; balasan itu memicu `message_create` baru dan mengulang siklus.
* **Solusi**: Saring prefix atau armed voice sebelum operasi async WhatsApp, pertahankan detail error hanya di log, dan kirim pesan generik ke user.
* **Verifikasi**: Unit test filter, syntax check Node, restart PM2, health endpoint, dan log startup WA tanpa kemunculan baru `❌ [WA] r`.

## ERR-R102 — Pemeriksaan Checklist PLAN Memberi False Positive
* **Masalah**: Verifikasi akhir menganggap PLAN masih memiliki step kosong walau semua task sudah dicentang.
* **Root Cause**: Pencarian substring `- [ ]` juga cocok dengan contoh sintaks checkbox di header PLAN.
* **Solusi**: Cari hanya checkbox pada awal baris memakai regex `^- \[ \]`.
* **Verifikasi**: Pemeriksaan berbasis baris tidak menemukan task yang belum dicentang.

## ERR-R103 — `realpath` Windows Tidak Mengenali Path WSL
* **Masalah**: Validasi path sebelum menghapus worktree berhenti dengan `UNSAFE PATH` dan path kosong.
* **Root Cause**: Perintah dijalankan oleh Bash Windows, bukan Bash distro Ubuntu, sehingga path `/home/bima_lucian/...` tidak tersedia.
* **Solusi**: Jalankan validasi dan `git worktree remove` sepenuhnya di WSL Ubuntu.
* **Verifikasi**: Tidak ada worktree yang terhapus saat validasi gagal; keduanya masih tercantum di `git worktree list`.

## ERR-D1 — Capability Browser Diusulkan Padahal Sudah Ada
* **Masalah**: Agent mengusulkan integrasi browser baru tanpa memeriksa tool lokal.
* **Root Cause**: Audit hanya melihat daftar MCP/dependency dan tidak memeriksa custom `BaseTool` serta assignment `tools=[...]`.
* **Solusi**: Sebelum mengusulkan tool, cari implementasi dan seluruh pendaftarannya di `tools/`, `teams/`, dan `core/`.
* **Verifikasi**: `tools/browser_use_tool.py` mendefinisikan `BrowserUseTool` dan `teams/t5_intel.py` sudah mendaftarkannya.

## ERR-D2 — Asersi Test MCP Tidak Sesuai Bahasa Output
* **Masalah**: Test mengharapkan pesan Inggris, sedangkan `core/mcp_security.py` mengembalikan pesan Indonesia.
* **Root Cause**: Test mengunci teks yang berbeda dari kontrak aktual.
* **Solusi**: Samakan asersi dengan output modul atau uji status/kode yang stabil bila wording bukan kontrak.
* **Verifikasi**: `tests/test_mcp_security.py` lulus pada focused verification 2026-07-16.

## ERR-D3 — Marp Tidak Menemukan Browser Headless di WSL
* **Masalah**: Export slide gagal dengan `No suitable browser found`; mencoba Chrome Windows dari WSL memicu kegagalan Puppeteer.
* **Root Cause**: Marp/Puppeteer membutuhkan browser yang dapat dieksekusi dari environment WSL yang sama.
* **Solusi**: Deteksi Chromium lokal dari cache Playwright dan teruskan sebagai `CHROME_PATH`; jangan mengandalkan executable Windows host.
* **Verifikasi**: `tools/slide_generator.py` mengatur `CHROME_PATH` dan `tests/test_slide_generator.py` lulus pada focused verification 2026-07-16.

## ERR-D4 — Mock Permission Gate Mengarah ke Modul yang Salah
* **Masalah**: Test slide gagal `AttributeError` saat patch `tools.slide_generator.check_permission_sync`.
* **Root Cause**: Function diimpor secara lokal dari `core.permission_gate`, bukan didefinisikan pada module slide generator.
* **Solusi**: Patch symbol pada sumbernya: `core.permission_gate.check_permission_sync`.
* **Verifikasi**: Target tersebut digunakan oleh `tests/test_slide_generator.py`; focused test lulus pada 2026-07-16.

## ERR-D5 — Threads Gagal Mengunduh Media dari Quick Tunnel
* **Masalah**: Threads API mengembalikan `400 Media download failed` karena public URL tunnel menghasilkan route yang salah.
* **Root Cause**: Quick tunnel memuat konfigurasi named tunnel lokal dan target `localhost` dapat resolve ke IPv6 yang tidak dilayani.
* **Solusi**: Jalankan `cloudflared tunnel --config /dev/null --protocol http2 --url http://127.0.0.1:8000`, lalu recreate process tunnel bila konfigurasi PM2 berubah.
* **Verifikasi**: Command tersebut menjadi deklarasi `bima-tunnel` di `ecosystem.config.js`.

## ERR-D6 — Pytest Mengoleksi Test dari Repository Vendored
* **Masalah**: Pytest root gagal collection karena masuk ke suite `tools/last30days-skill` atau clone lokal lain.
* **Root Cause**: Discovery default tidak mengenali boundary subproject.
* **Solusi**: Daftarkan folder vendored, venv, worktree, dan clone lokal pada `pytest.ini:norecursedirs`.
* **Verifikasi**: `pytest.ini` mengecualikan `tools/last30days-skill`, `agent-reach`, `bima_env`, `.kilo`, dan `.worktrees`; full suite mengoleksi serta meluluskan 324 test.

## ERR-D7 — Revisi Threads Diproses LLM Dua Kali
* **Masalah**: Draf yang sudah direvisi di listener Discord diproses ulang saat publish, menambah biaya, latency, dan risiko perubahan teks.
* **Root Cause**: Dua call site sama-sama menganggap nilai `_revised_texts` masih mentah.
* **Solusi**: Proses revisi sekali, lalu gunakan `final_text = revised if revised else draft_text` pada publish path.
* **Verifikasi**: Tiga publish path di `core/threads_commands.py` memakai assignment langsung tersebut.

## ERR-D8 — Tiga Bug Defensive pada Admin Document Tools
* **Masalah**: Footer muncul di cover PDF, file data relatif gagal ditemukan, dan Excel tidak menerima chart.
* **Root Cause**: Tidak ada cover guard, resolver hanya menerima satu bentuk path, dan kontrak chart belum diteruskan ke Excel.
* **Solusi**: Skip header/footer pada cover; resolve nama file di output root dengan containment check; dukung chart pada level document dan sheet.
* **Verifikasi**: `teams/t4_admin/pdf_tool.py` memiliki cover guard dan `teams/t4_admin/excel_tool.py` memproses chart document/sheet.

## ERR-D9 — Output Agent Terdengar seperti AI Slop
* **Masalah**: Chat, dokumen, dan Threads memakai pembuka, filler, serta frasa klise berulang.
* **Root Cause**: Prompt dan tool revisi tidak mempunyai aturan gaya yang konsisten.
* **Solusi**: Gunakan aturan anti-slop pada manager, revisi Threads, prompt Admin, dan `DeslopTool` bila editing khusus diperlukan.
* **Verifikasi**: Integrasi berada di `tools/deslop_tool.py`, `core/threads_commands.py`, `core/langgraph_nodes/manager.py`, dan prompt Admin.

## ERR-D11 — Build `agent-reach` dan Pemanggilan WSL Bersarang Gagal
* **Masalah**: Hatchling memasukkan file yang sama dua kali; backend yang sudah berjalan di WSL juga mencoba memanggil binary `wsl` lagi.
* **Root Cause**: `force-include` tumpang tindih dengan package target dan runtime salah mengira dirinya berada di Windows host.
* **Solusi**: Hilangkan include build yang redundan pada package sumber dan panggil CLI langsung melalui `shutil.which()` dengan argv tanpa shell.
* **Verifikasi**: `tools/agent_reach_tool.py` mencari binary `twitter` melalui `shutil.which()` dan menjalankannya langsung.

## ERR-D12 — Konfigurasi Threads Tertinggal di Sonnet 4.6
* **Masalah**: Fallback code dan konfigurasi runtime lama masih menunjuk model 4.6.
* **Root Cause**: Model slug disalin ke beberapa lokasi dan tidak diperbarui bersamaan.
* **Solusi**: Samakan fallback dan contoh konfigurasi ke slug yang dipilih; environment runtime tetap harus diverifikasi tanpa menampilkan nilainya.
* **Verifikasi**: Fallback `core/threads_commands.py` saat ini memakai `anthropic/claude-sonnet-5`.

## ERR-D13 — MiniLM Lemah untuk Dedup Semantik Bahasa Indonesia
* **Masalah**: Benchmark parafrase Indonesia memberi recall rendah dan margin negatif pada `all-MiniLM-L6-v2`.
* **Root Cause**: Model lokal tersebut English-skewed dan dimensi index lama tidak otomatis memaksa rebuild.
* **Solusi**: Gunakan `Qwen/Qwen3-Embedding-0.6B` untuk domain arsip dan rebuild table ketika dimensi berubah.
* **Verifikasi**: Benchmark historis naik dari recall 38% ke 96%; `core/embedder.py` memakai Qwen3 untuk domain arsip.

## ERR-D14 — Download Model Hugging Face Besar Stall di WSL
* **Masalah**: Download model besar berhenti lama karena request anonim dan koneksi CDN yang bursty.
* **Root Cause**: Rate limit serta read stall; kill/restart mengulang partial download.
* **Solusi**: Login HF di user cache, gunakan single stream, biarkan proses selesai tanpa watchdog kill, dan monitor ukuran blob. Jangan simpan token di repository.
* **Verifikasi**: Model Qwen3 berhasil dipakai setelah download uninterrupted; kondisi jaringan tetap dapat berubah.

## ERR-D15 — XReach Dapat Hang dan Meneruskan Input Tidak Tepercaya
* **Masalah**: CLI tanpa timeout dapat menahan worker; tweet mentah dan output tanpa cap masuk ke konteks LLM.
* **Root Cause**: Tidak ada timeout, sanitasi trust boundary, marker, atau batas output.
* **Solusi**: Gunakan timeout 20 detik, sanitasi control character/URL/mention, marker `[UNTRUSTED_TWEET]`, dan cap 4.000 karakter.
* **Verifikasi**: Implementasi ada di `tools/agent_reach_tool.py`; `tests/test_agent_reach.py` lulus pada focused verification 2026-07-16.

## ERR-D16 — Repository Tidak Memiliki Gate CI
* **Masalah**: Perubahan pernah dapat di-push tanpa test otomatis; install seluruh ML stack juga terlalu berat untuk runner.
* **Root Cause**: Belum ada workflow dan dependency CI yang terpisah.
* **Solusi**: Gunakan workflow read-only pada push/PR, Python 3.12, lockfile uv, group CI, timeout, dan cancellation concurrency.
* **Verifikasi**: `.github/workflows/ci.yml` menjalankan `uv sync --locked --only-group ci` dan full pytest.

## ERR-D17 — Compiler Applied Ideas Tidak Membaca Lokasi Error Canonical
* **Masalah**: Script eksternal `update_ideas.py` hanya memindai `error_solutions.md` di root. Setelah konsolidasi, file itu hanya redirect sehingga menjalankan script dapat menghilangkan entry BIMA_CORE dari registry global.
* **Root Cause**: Daftar file sumber hardcoded dan parser tidak mengikuti link Markdown ke `docs/ERROR_SOLUTIONS.md`.
* **Solusi**: Jangan jalankan script lama setelah migrasi. Update script pada task terpisah agar ikut membaca `docs/ERROR_SOLUTIONS.md` dan mengenali heading `ERR-*`, lalu uji output sebelum menimpa registry global.
* **Verifikasi**: Inspeksi `update_ideas.py` menunjukkan `log_files` hanya berisi `errorandsolusion.md` dan `error_solutions.md`; script tidak dijalankan pada task ini untuk mencegah kehilangan data.

## ERR-D18 — Anisa Memakai RAM Lebih dari 3 GB dan Berulang Kali Direstart PM2
* **Masalah**: `anisa-v3` mencapai 3.0–4.0 GB saat startup sehingga melewati guardrail PM2 lama dan restart berulang; `VmmemWSL` terlihat mendekati 8 GB.
* **Root Cause**: Embedding Qwen3 0.6B dan CrossEncoder reranker dimuat lokal, dengan dua warmup reranker yang dapat berjalan bersamaan. Cache Linux juga tertahan karena `autoMemoryReclaim` berada di section `.wslconfig` yang salah.
* **Solusi**: Gunakan Qwen3 Embedding 8B melalui OpenRouter khusus domain arsip, kirim dokumen secara batch, matikan reranker lokal sambil mempertahankan vector+BM25, lindungi constructor reranker dengan lock, batasi PM2 2 GB, dan letakkan `autoMemoryReclaim=dropCache` di `[experimental]`.
* **Verifikasi**: Vault 897 chunk berhasil direbuild, live search berhasil, restart count PM2 tetap 0, dan RSS `anisa-v3` stabil sekitar 1.0–1.3 GB setelah warmup.

## ERR-D19 — WhatsApp Gagal Sebelum Pesan Sampai ke Bridge
* **Masalah**: User menerima error generik atau tidak melihat balasan walau WA FastAPI sehat.
* **Root Cause**: Lookup `msg.getChat()` dapat melempar error pendek `r`. Pada self-chat terbaru, command dari ponsel memakai pasangan PN `@c.us` → `@lid`, sedangkan `msg.reply()` membuat balasan ber-quote dari LID ke LID yang tercatat ACK 3 tetapi tidak tampil seperti balasan normal di ponsel.
* **Solusi**: Jadikan lookup chat/typing best-effort, resolve target LID melalui `getContactLidAndPhone()`, dan kirim seluruh teks/media memakai `client.sendMessage()` ke target PN tanpa quoted-message ID.
* **Verifikasi**: Store WhatsApp Web membuktikan mapping LID ke PN akun yang sama; regression test mapping dan fallback lulus 5/5, syntax check lulus, bridge login kembali, `/health` 200, dan self-test menghasilkan balasan gate baru ACK 3. Tampilan ponsel tetap perlu dikonfirmasi user.

## ERR-D20 — WhatsApp Self-Chat Tidak Menampilkan Status Anisa Sedang Memproses
* **Masalah**: Setelah command `/bot`, tidak ada indikator bahwa Anisa sedang bekerja sehingga user mengira bot diam.
* **Root Cause**: Indikator typing bergantung pada objek chat dari `msg.getChat()`, sedangkan lookup self-chat LID melempar error pendek `r`. WA FastAPI juga dipanggil melalui HTTP blocking tanpa progress callback ke bridge.
* **Solusi**: Kirim pesan langsung `ANISA lagi mikir` sebelum request backend, beri header `ANISA` pada jawaban final, edit preview secara best-effort, dan kirim final baru bila edit tidak didukung.
* **Verifikasi**: Live `/bot tes preview` menampilkan preview jam 11:21 dan final beridentitas Anisa jam 11:22; screenshot visual tersimpan di `outputs/wa-preview-anisa-identity.png`; 9 test Node dan syntax check lulus.

## ERR-D21 — Serper Kosong Dianggap Sukses sehingga Tavily Tidak Jalan
* **Masalah**: Pencarian berita mengembalikan `organic: []`, tetapi Anisa menyimpulkan tidak ada berita dan tidak menjalankan fallback Tavily.
* **Root Cause**: Keyword buatan LLM dibungkus tanda kutip sehingga terlalu exact. `SmartSearchTool` menganggap respons Serper sukses hanya karena panjang teks lebih dari 50 karakter; payload metadata kosong sepanjang 140 karakter lolos gate tersebut.
* **Solusi**: Lepas tanda kutip pembungkus sebelum pencarian dan validasi isi `organic`, `news`, atau kelompok hasil Serper lain. Jika seluruh kelompok kosong, lanjutkan ke Tavily.
* **Verifikasi**: Regression test membuktikan normalisasi query dan fallback Serper-kosong ke Tavily; smoke query yang sama menghasilkan 3.530 karakter dengan hasil organik terisi; focused test 5 lulus dan full suite 343 lulus.

## ERR-D22 — Pencarian Berita Mencampur Preview Basi dan Hasil Terbaru
* **Masalah**: Respons berita siang hari masih menyajikan tautan `LIVE/Jadwal Spanyol vs Argentina`, padahal pertandingan sudah selesai dini hari dan hasil akhirnya sudah terbit.
* **Root Cause**: Query berita memakai endpoint web umum Serper tanpa metadata tanggal, cache satu jam, dan tidak membedakan preview pertandingan dari laporan hasil. Tavily hanya menjadi fallback ketika Serper kosong sehingga tidak pernah menjadi pembanding.
* **Solusi**: Deteksi query berita lalu pakai endpoint Serper `news` berlokasi Indonesia, batasi hasil 24 jam, hapus preview yang cocok dengan laporan hasil, cross-check Tavily `topic=news` dengan `time_range=day`, saring relevansi, dan gunakan cache berita lima menit dengan namespace baru.
* **Verifikasi**: Delapan regression test lulus; smoke live menghasilkan mode `news`, rentang `24h`, 13 hasil relevan, tanpa preview Spanyol–Argentina yang basi dan tanpa hasil Tavily yang tidak terkait Indonesia.

## ERR-D23 — Post Threads Baru Mencampur Draf, Revisi, atau Konteks Lama
* **Masalah**: Request Threads baru dapat mempublikasikan revisi request sebelumnya atau memakai fakta/memori lama; scheduler juga dapat mengulang konteks dari database lokal.
* **Root Cause**: Revisi disimpan global berdasarkan user, state reject/timeout tidak membersihkannya, konteks draf disimpan lintas request, raw `VIRAL_PATTERN` selalu di-recall, tren tidak punya TTL, dan scheduler membaca konteks lama dari `scientific_facts.json`. Race Discord juga memungkinkan approve saat revisi belum selesai atau timeout mempublikasikan draf awal.
* **Solusi**: Scope draf/revisi ke `req_id`, pisahkan raw revision source dari wrapper UI, bersihkan semua state terminal, blok preview/reaksi lama, dan fail-closed bila timeout memiliki revisi. Gunakan Serper News maksimal 24 jam, cache tren lima menit sekali pakai, hilangkan raw memory dari prompt, serta jadikan data lokal scheduler hanya denylist judul; skip job bila konteks live kosong.
* **Verifikasi**: TDD merah-hijau; focused test 59 lulus; full suite runtime 385 lulus dengan dua warning dependency; review akhir tidak menemukan blocker; healthcheck 50 lulus/2 warning resource; `anisa-v3` direstart, online, dan `/api/metrics` kembali HTTP 200. Tidak ada publish Threads nyata saat verifikasi.
