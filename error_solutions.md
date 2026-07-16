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

## Log 34: Nama File Aturan Bersifat Case-sensitive di WSL
* **Masalah**: Pembacaan `claude.md` gagal walau file aturan terlihat ada.
* **Root Cause**: File aktual bernama `CLAUDE.md`; filesystem Linux membedakan huruf besar dan kecil.
* **Solusi**: Jadikan `CLAUDE.md` satu-satunya sumber aturan rinci, seragamkan semua referensi ke nama persis tersebut, dan cari masalah terkait di file ini sebelum mengulang command gagal.
* **Verifikasi**: Guard canonical lulus; `Rules for agent.md` sudah tidak ada dan `AGENTS.md`/`.gitignore` tidak lagi memuat referensi lowercase.

## Log 35: Command Healthcheck di AGENTS.md Sudah Basi
* **Masalah**: `python healthcheck.py` gagal karena file tidak ada di root.
* **Root Cause**: Healthcheck sudah berada di `scripts/healthcheck.py`, tetapi dokumentasi masih menunjuk path lama.
* **Solusi**: Jalankan `bima_env/bin/python scripts/healthcheck.py` dan perbarui command di `AGENTS.md` pada task dokumentasi berikutnya.

## Log 36: Tool Dev Tidak Terpasang di bima_env
* **Masalah**: `ruff` dan `pip-audit` tidak dapat dijalankan walau tercantum di `requirements-dev.txt`.
* **Root Cause**: Environment production dibuat tanpa dependency development dan repo belum memiliki lockfile yang membedakan group production/dev.
* **Solusi**: Tambahkan group dev pada `pyproject.toml`, buat lockfile uv, dan instal group dev hanya pada CI/development dengan mode frozen.

## Log 37: Audit Dependency Outdated via pip Timeout
* **Masalah**: `pip list --outdated --format=json` tidak selesai dalam 60 detik.
* **Root Cause**: Environment memiliki ratusan paket ML/CUDA dan pip memeriksa metadata secara lambat.
* **Solusi**: Gunakan executable lokal `bima_env/bin/uv pip list --python bima_env/bin/python --outdated`; audit ini selesai sekitar 16 detik.

## Log 38: GitHub API Date Gagal Diformat PowerShell
* **Masalah**: Pemanggilan `.ToString('yyyy-MM-dd')` pada tanggal GitHub API gagal.
* **Root Cause**: `Invoke-RestMethod` mengembalikan field tanggal sebagai string pada host PowerShell ini.
* **Solusi**: Perlakukan nilai sebagai string ISO dan ambil 10 karakter pertama, atau parse eksplisit dengan `[datetime]::Parse()`.

## Log 39: uv audit Tidak Bisa Berjalan Tanpa Project Metadata
* **Masalah**: `uv audit --frozen` gagal dengan `No pyproject.toml found`.
* **Root Cause**: BIMA_CORE masih memakai requirements bebas versi dan belum menjadi project uv yang dapat dikunci.
* **Solusi**: Buat `pyproject.toml` + `uv.lock`, lalu jalankan `uv audit --frozen` di CI dan lokal.

## Log 40: AgentMemory Mati Karena Cache npx Korup
* **Masalah**: Launcher mencatat AgentMemory berhasil di-spawn, tetapi port 3111 tidak listen dan semantic recall memakai fallback.
* **Root Cause**: `npx -y @agentmemory/agentmemory` berulang kali gagal rename cache dengan `ENOTEMPTY` pada `~/.npm/_npx/.../@agentmemory/agentmemory`.
* **Solusi**: Setelah approval instalasi, pasang dan pin `@agentmemory/agentmemory@0.9.27` sekali, jalankan executable sebagai proses PM2 terpisah, dan tambahkan readiness check sebelum dianggap sehat. Pembersihan cache npx bersifat destruktif dan hanya dilakukan dengan approval eksplisit.

## Log 41: Dependency Terbaru Tidak Bisa Disatukan dalam Satu Environment
* **Masalah**: Dry-run CrewAI 1.15.2 + Browser Use 0.13.3 gagal diselesaikan; kombinasi dengan F5-TTS juga gagal.
* **Root Cause**: CrewAI meminta `openai>=2.30,<3`, Browser Use mengunci `openai==2.16.0`, serta Browser Use/F5-TTS bertabrakan pada `rich`, `cached-path`, dan `tqdm`.
* **Solusi**: Pisahkan `core-env`, `browser-env`, dan `voice-env`; pin masing-masing dengan lockfile. Hubungkan browser dan voice sebagai subprocess/service dengan kontrak sempit.

## Log 42: Environment Memiliki Sembilan Konflik Versi Laten
* **Masalah**: `python -m pip check` menemukan konflik protobuf, aiofiles, Starlette, lance-namespace, fsspec, rich, pyarrow, serta Torch/Torchvision.
* **Root Cause**: Paket dipasang bertahap tanpa lockfile, sehingga pip membiarkan dependency lama dan baru bercampur.
* **Solusi**: Jangan auto-upgrade environment aktif. Buat environment baru dari lockfile per subsistem, jalankan import smoke + full test, lalu pindahkan PM2 setelah verifikasi.

## Log 43: SQLite MCP Aktif Berasal dari Repo Arsip
* **Masalah**: `mcp-server-sqlite` aktif dan memberi tool write/create table, padahal upstream memindahkannya ke repository archived tanpa security update.
* **Root Cause**: `config_mcp.json` dibuat saat SQLite masih dicontohkan sebagai reference server dan tidak pernah diaudit ulang terhadap registry terbaru.
* **Solusi**: Nonaktifkan SQLite MCP, gunakan fungsi internal dengan query allowlist, serta pin semua package `npx`/`uvx` yang tetap digunakan.

## Log 44: Git MCP Tidak Masuk ke Agen Kodok
* **Masalah**: Startup mencatat `[mcp_inject] agent 'kodok' tidak dikenal, skip` sehingga 12 Git tools tidak tersedia.
* **Root Cause**: `config_mcp.json` menargetkan `kodok`, tetapi `_AGENT_REGISTRY` di `main.py` tidak memiliki mapping `teams.t10_kodok:kodok_agent`.
* **Solusi**: Tambahkan mapping Kodok dan regression test untuk seluruh nilai `attach_to` agar selalu ada di registry.

## Log 45: LanceDB Diinisialisasi Sebelum Fork Subprocess MCP
* **Masalah**: Setiap startup MCP menampilkan warning bahwa runtime async LanceDB di-reset setelah fork dan masih memiliki risiko deadlock.
* **Root Cause**: Koneksi LanceDB dibuat pada import module sebelum MCP adapter membuka subprocess.
* **Solusi**: Ubah koneksi LanceDB menjadi lazy-init setelah lifecycle subprocess selesai, atau jalankan komponen LanceDB pada proses terpisah dengan start method `spawn`/`forkserver` yang diuji.

## Log 46: Scheduler Berulang Kali Terlambat
* **Masalah**: Observability, Threads scan, dan paper trading terlambat sekitar 23–77 detik pada banyak siklus.
* **Root Cause**: Event loop utama mengalami stall; audit belum membuktikan call site tunggal karena beberapa job CPU/sync berjalan bersamaan.
* **Solusi**: Tambahkan metrik event-loop lag dan profil dengan `pyinstrument` yang sudah terpasang. Pindahkan kerja CPU/sync terberat ke worker terpisah berdasarkan hasil profil, lalu set `coalesce`, `max_instances`, dan `misfire_grace_time` secara eksplisit.

## Log 47: Prefix Dashboard API Token Masuk Log
* **Masalah**: Startup menulis delapan karakter awal `DASHBOARD_API_TOKEN` ke log.
* **Root Cause**: `core/dashboard_server.py` menggunakan `_API_TOKEN[:8]` untuk indikator token loaded.
* **Solusi**: Log hanya status boolean/token source tanpa karakter token dan rotasi token bila log pernah dibagikan ke pihak lain.

## Log 48: Format Git Log Dipecah Shell WSL
* **Masalah**: Format `git log --pretty=format:%h|%ad|%s` membuat `%ad` dan `%s` dibaca sebagai command terpisah.
* **Root Cause**: Karakter pipe melewati lapisan PowerShell ke `bash -lc` tanpa quoting yang bertahan sampai Git.
* **Solusi**: Gunakan `git log -5 --oneline` untuk eksplorasi ringkas atau jalankan format kompleks langsung di shell WSL interaktif.

## Log 49: Test MCP yang Diasumsikan Ternyata Tidak Ada
* **Masalah**: Pembacaan `tests/test_mcp_client_manager.py` gagal karena file belum ada.
* **Root Cause**: Audit mengasumsikan MCP manager sudah punya unit test berdasarkan nama modul production.
* **Solusi**: Cari test dengan `rg --files tests | rg 'mcp'` sebelum membaca; buat test baru hanya setelah memastikan coverage memang belum ada.

## Log 50: Instalasi AgentMemory Melewati Timeout Tool
* **Masalah**: `npm install` melewati 60 detik dan tool mengembalikan timeout, tetapi proses WSL tetap berjalan di background.
* **Root Cause**: AgentMemory menarik dependency ONNX/transformers besar; wrapper timeout Windows tidak langsung menghentikan child WSL.
* **Solusi**: Periksa PID, log npm, dan keberadaan lockfile sebelum retry. Instalasi akhirnya menghasilkan `package-lock.json` dan AgentMemory 0.9.27 tanpa menjalankan install kedua.

## Log 51: Redirect `/dev/null` Diparse PowerShell
* **Masalah**: Command `wsl ... 2>/dev/null` mencoba menulis ke path UNC `dev/null` dan gagal.
* **Root Cause**: Operator redirect diproses PowerShell sebelum command masuk WSL.
* **Solusi**: Hindari redirect shell pada command lintas PowerShell/WSL; tangani exit code atau jalankan seluruh pipeline di satu shell dengan quoting yang sudah diverifikasi.

## Log 52: Sinkronisasi Voice Environment Sangat Lama
* **Masalah**: `uv sync` voice-env berjalan lebih dari 15 menit dan menulis beberapa GB cache sebelum dihentikan.
* **Root Cause**: F5-TTS + PyTorch CUDA membutuhkan wheel besar, sementara beberapa proses download berjalan bersamaan.
* **Solusi**: Jalankan satu sync besar pada satu waktu, gunakan cache uv yang sudah terisi, dan beri window eksekusi khusus. Jangan switch PM2 ke voice-env sebelum executable F5 dan import smoke terverifikasi.

## Log 53: AgentMemory `--instance 1` Tidak Merelokasi Engine
* **Masalah**: CLI menunggu health port 3211, tetapi iii-engine tetap membuka 3111/49134 dari config statis lalu smoke test timeout.
* **Root Cause**: AgentMemory 0.9.27 tidak menerapkan offset instance ke port eksplisit di bundled `iii-config.yaml` pada setup ini.
* **Solusi**: Deployment BIMA memakai default port 3111. Smoke test default berhasil `healthy`; proses uji kemudian dihentikan dengan `agentmemory stop --force` agar state di-flush.

## Log 54: Patch Dashboard Gagal karena Konteks Emoji
* **Masalah**: Patch sanitasi token tidak menemukan baris logger walau teks terlihat sama.
* **Root Cause**: Emoji pada file UTF-8 tampil sebagai mojibake melalui PowerShell sehingga konteks patch berbeda byte.
* **Solusi**: Pecah patch menjadi hunk ASCII kecil dan gunakan karakter Unicode asli hanya pada baris yang memang harus diganti.

## Log 55: Command Kedua Kehilangan Prefix WSL
* **Masalah**: Setelah `wsl ... uv lock;`, path Linux untuk command pytest berikutnya dijalankan oleh PowerShell dan dianggap executable Windows.
* **Root Cause**: Tanda titik koma mengakhiri invocation WSL; command setelahnya kembali ke shell host.
* **Solusi**: Beri prefix `wsl.exe -d Ubuntu --cd ... --` pada setiap command atau jalankan satu command per tool call.

## Log 56: CI Lock Bersih Belum Memuat Runtime Import Test
* **Masalah**: Test dari environment CI terisolasi gagal collection pada lima modul walau `uv pip check` bersih.
* **Root Cause**: CrewAI OpenRouter membutuhkan `litellm` yang tidak tercantum langsung, dan test paper trading mengimpor `yfinance` yang sebelumnya dikeluarkan dari subset CI.
* **Solusi**: Tambahkan dependency eksplisit `litellm` ke core/CI serta `yfinance` ke group CI, lock ulang, lalu jalankan full test dari `.venv`. Jangan menyatakan CI pulih sebelum 207+ test lulus dari environment bersih.

## Log 57: Patch Dependency CI Memakai Konteks Versi Lama
* **Masalah**: Patch awal `pyproject.toml` gagal menemukan baris LanceDB dan MCP yang diharapkan.
* **Root Cause**: Konteks patch berasal dari ringkasan versi sebelumnya, sedangkan file aktual sudah memakai `lancedb==0.34.0` dan `mcpadapt`.
* **Solusi**: Baca ulang file aktual lalu sisipkan dependency berdasarkan baris `mcpadapt` dan batas group CI yang benar.

## Log 58: Full Test CI Menemukan Import pandas-ta Berikutnya
* **Masalah**: Setelah `litellm` dan `yfinance` tersedia, collection full test masih berhenti pada `ModuleNotFoundError: pandas_ta` dari `teams/t9_saham.py`.
* **Root Cause**: `pandas-ta` ada di dependency runtime utama tetapi belum dimasukkan ke subset dependency group CI.
* **Solusi**: Tambahkan pin `pandas-ta==0.4.71b0` ke group CI, lock dan sync ulang, lalu ulang full test. Perubahan ditahan sampai kegagalan baru ini disetujui sesuai verification gate repo.

## Log 59: Pemeriksaan Cache Voice Gabungan Timeout
* **Masalah**: Setelah sync voice melewati batas tool, command pemeriksaan `pgrep`, dua `du`, dan `df` ikut timeout tanpa hasil.
* **Root Cause**: `du` rekursif pada cache uv yang besar membuat pemeriksaan gabungan melewati batas waktu, sehingga status proses tidak terlihat.
* **Solusi**: Jangan gabungkan scan cache besar dengan pemeriksaan proses. Cek PID dan filesystem memakai command terpisah, lalu lanjutkan sync dengan mekanisme yield yang tidak mematikan proses.

## Log 60: PowerShell Select-Object Range Tidak Diparentesiskan
* **Masalah**: Pembacaan potongan `.env.example` gagal karena `Select-Object -Index 100..130` dianggap satu string.
* **Root Cause**: PowerShell membutuhkan ekspresi range dibungkus kurung saat dipakai sebagai nilai parameter.
* **Solusi**: Gunakan `Select-Object -Index (100..130)` atau `sed -n` melalui WSL.

## Log 61: Patch Flag Voice Gagal karena Komentar Env Berbeda
* **Masalah**: Patch gabungan STT/TTS gagal pada konteks komentar daftar ukuran model.
* **Root Cause**: Baris aktual juga memuat opsi `turbo`, sedangkan konteks patch tidak memuatnya.
* **Solusi**: Baca ulang blok `.env.example`, gunakan konteks aktual, lalu patch ulang. Regression test memastikan STT/TTS default tidak memuat worker/model.

## Log 62: Gate Paralel Kehilangan Output karena Git Windows pada UNC Worktree
* **Masalah**: Eksekusi gate paralel batal saat `git diff --check` lewat Git Windows menganggap worktree UNC bukan repository; output test paralel ikut tidak terkumpul.
* **Root Cause**: Worktree dibuat di filesystem WSL, tetapi satu command Git dijalankan dari host Windows.
* **Solusi**: Jalankan semua command Git worktree melalui `wsl.exe --cd`, cek proses pytest yang tertinggal, lalu ulang full test secara tunggal agar exit code dan jumlah test tercatat.

## Log 63: Installer Runtime Paralel Melewati Timeout Wrapper
* **Masalah**: `uv sync` browser dan `npm ci` AgentMemory melewati timeout parent 120 detik sehingga output gabungan hilang.
* **Root Cause**: Instalasi npm tetap berjalan sebagai proses WSL setelah wrapper host berhenti menunggu.
* **Solusi**: Cek PID sebelum retry. Browser diverifikasi dari metadata environment; proses npm ditunggu sampai selesai lalu diverifikasi dengan `npm ls`.

## Log 64: browser_use Tidak Memiliki Atribut __version__
* **Masalah**: Smoke test import browser gagal ketika membaca `browser_use.__version__`.
* **Root Cause**: Paket Browser Use 0.13.3 tidak mengekspos atribut versi pada modul top-level.
* **Solusi**: Baca versi terpasang memakai `importlib.metadata.version('browser-use')`; hasilnya Browser Use 0.13.3 dan OpenAI 2.16.0.

## Log 65: AgentMemory Membawa Vulnerability Transitive
* **Masalah**: `npm audit --audit-level=high` menemukan 15 vulnerability: 10 moderate, 4 high, dan 1 critical.
* **Root Cause**: `@agentmemory/agentmemory@0.9.27` membawa rantai `iii-sdk`, OpenTelemetry lama, serta `@xenova/transformers`/`onnxruntime-web` dengan `protobufjs` rentan.
* **Solusi**: Jangan start AgentMemory di PM2. Tahan service sampai versi upstream aman atau dependency override tervalidasi; backend utama tetap dapat berjalan dengan status degraded.
* **Verifikasi 2026-07-15**: 0.9.27 masih versi terbaru, `AGENTMEMORY_ENABLED` tidak disetel, dan `npm audit fix --dry-run --json` tetap menyisakan 15 vulnerability. Package AgentMemory membawa override `protobufjs`, tetapi npm hanya menerapkan `overrides` dari root project; uji root override atau versi upstream baru di environment terpisah sebelum service diaktifkan.

## Log 66: Path Healthcheck di Dokumentasi Tidak Sesuai Repo
* **Masalah**: Command `python healthcheck.py` gagal karena file tidak ada di root.
* **Root Cause**: Implementasi aktual berada di `scripts/healthcheck.py`, sedangkan dokumentasi masih menunjuk lokasi lama.
* **Solusi**: Jalankan `python scripts/healthcheck.py`; health production lulus 51 check dengan 1 warning nonfatal.

## Log 67: Operator Pipe Pencarian Health Keluar dari WSL
* **Masalah**: `rg ... | head` menjalankan `head` di PowerShell, lalu regex dengan `|` juga ditafsirkan sebagai command shell.
* **Root Cause**: Quote/operator tidak bertahan konsisten melewati PowerShell ke WSL.
* **Solusi**: Hindari pipe lintas-shell dan pakai beberapa pola `rg -e` tanpa operator alternation.

## Log 68: Parser Status Menganggap services Berbentuk List
* **Masalah**: Pembacaan snapshot berhasil mencetak `degraded`, lalu gagal saat memanggil `.get()` pada nama service.
* **Root Cause**: Field `services` adalah map `{nama: status}`, bukan list objek.
* **Solusi**: Baca map langsung. Snapshot membuktikan backend/WA/tunnel online dan AgentMemory unknown sehingga overall degraded.

## Log 69: Warning LanceDB Fork Masih Muncul Setelah Lazy Connection
* **Masalah**: Log startup production masih menampilkan warning experimental fork support dari LanceDB saat MCP subprocess dimulai.
* **Root Cause**: Re-index Arsip membuka koneksi LanceDB sebelum seluruh MCP child selesai di-fork; lazy module import saja belum cukup mengubah urutan startup.
* **Solusi**: Sistem tetap online, tetapi perbaikan lanjutan harus memindahkan re-index/warmup LanceDB setelah MCP startup atau memakai multiprocessing `spawn`/`forkserver`, lalu diverifikasi terhadap deadlock.

## Log 70: Audit Dry-run Membatalkan Output Investigasi Paralel
* **Masalah**: `npm audit fix --dry-run --json` exit 1 karena vulnerability belum terselesaikan, sehingga output query versi dan trace LanceDB dalam batch paralel tidak terkumpul.
* **Root Cause**: Orkestrasi batch menghentikan hasil agregat ketika salah satu command menghasilkan exit nonzero yang memang diharapkan dari audit.
* **Solusi**: Jalankan query versi dan trace satu per satu. Hasil resmi npm: AgentMemory 0.9.27 masih versi terbaru dan vulnerability direct tidak punya fix otomatis.

## Log 71: Ruff main.py Menemukan E402 Baseline
* **Masalah**: Ruff pada semua file tersentuh menemukan empat E402 di `main.py`.
* **Root Cause**: `uvloop.install()`, Sentry, dan konfigurasi logging sengaja dijalankan sebelum import modul aplikasi; pola ini sudah ada sebelum perbaikan LanceDB.
* **Solusi**: Jangan memindahkan urutan startup hanya untuk lint. Jalankan Ruff pada file logika yang berubah; full pytest dan startup production menjadi gate untuk `main.py`.

## Log 72: Memindahkan Thread Index Saja Belum Menghilangkan Warning LanceDB
* **Masalah**: Startup pertama setelah thread index dipindahkan masih menampilkan warning pada setiap fork MCP.
* **Root Cause**: Import top-level `lancedb` di Arsip dan Repo RAG sudah menginisialisasi runtime native sebelum koneksi/database dipakai.
* **Solusi**: Lazy-import `lancedb` di `_get_db()` dan `_connect_db()`, selain menunda thread index. Startup berikutnya bersih dan index Arsip tetap menghasilkan 897 dokumen BM25 setelah MCP siap.

## Log 73: Alert Security Repo Publik Tidak Bisa Dibaca
* **Masalah**: Audit `modiqo/waggle` mendapat HTTP 403 saat meminta Code Scanning dan Dependabot alerts.
* **Root Cause**: Endpoint alert GitHub hanya dapat dibaca dengan izin admin repository; autentikasi lokal bukan pemilik repo tersebut.
* **Solusi**: Jangan menyimpulkan repo bebas vulnerability. Nilai source, workflow, dan release publik; minta maintainer mengekspor alert atau lakukan scanner lokal pada source yang dipin bila audit lebih lanjut disetujui.

## Log 74: `jq` Tidak Tersedia di WSL
* **Masalah**: Parsing hasil benchmark Waggle gagal dengan `jq: command not found`.
* **Root Cause**: Environment WSL tidak memasang executable `jq`, meskipun `gh --jq` memiliki evaluator internal.
* **Solusi**: Gunakan `gh api ... --jq '<expression>'` langsung agar tidak membutuhkan dependency tambahan.

## Log 75: `gh` Hilang dari PATH WSL Non-login
* **Masalah**: `wsl.exe -d Ubuntu -- gh api ...` gagal dengan `gh: command not found`, padahal command yang sama tersedia melalui shell login.
* **Root Cause**: Invocation WSL non-login tidak memuat konfigurasi PATH tempat GitHub CLI terpasang.
* **Solusi**: Jalankan `gh` melalui `wsl.exe -d Ubuntu -- bash -lc "gh api ..."` pada environment ini.

## Log 76: Reader PM2 Observability Selalu Mengembalikan Kosong
* **Masalah**: `core/observability_scheduler._get_pm2_status()` mengembalikan `[]`, sehingga scheduler tidak dapat mendeteksi proses PM2 yang offline.
* **Root Cause**: `subprocess.run(["pm2", "jlist"], shell=True)` memakai list argumen bersama shell pada POSIX. `pm2` dijalankan tanpa subcommand `jlist`, output bukan JSON, lalu exception disembunyikan oleh safe-fail.
* **Solusi**: Hapus `shell=True`, pertahankan argv `['pm2', 'jlist']`, log warning saat command/JSON gagal, dan tambah regression test yang memastikan empat proses dapat diparse.
* **Verifikasi**: Reader observability menghasilkan `[]`; reader maintenance dengan command tanpa shell menghasilkan empat proses `stopped` pada PM2 yang sama.

## Log 77: Environment Python Aktif Memiliki 9 Konflik Dependency
* **Masalah**: `uv pip check --python bima_env/bin/python` menemukan 9 incompatibility pada pyarrow, protobuf, lance-namespace, rich, fsspec, aiofiles, starlette, dan pasangan torch/torchvision.
* **Root Cause**: `bima_env` memuat dependency fitur voice/browser/data yang dipasang di luar metadata `pyproject.toml`. Dibanding lock aktif, dry-run akan menghapus 163 package dan memasang 31 package.
* **Solusi**: Jangan jalankan `uv sync` langsung pada production. Inventaris dependency runtime yang benar, masukkan ke group project yang sesuai, bangun environment baru dari lock, lalu gate dengan 299 pytest serta smoke voice/browser sebelum switch.
* **Verifikasi**: `uv lock --check` lulus, tetapi `uv sync --active --frozen --dry-run` membuktikan environment aktif tidak identik dengan lock.

## Log 78: Audit Python Menemukan Tiga Package Rentan
* **Masalah**: `uv audit --frozen` menemukan 5 record advisory yang mewakili 3 package: `chromadb==1.1.1`, `diskcache==5.6.3`, dan `json-repair==0.25.2`.
* **Root Cause**: ChromaDB masuk transitif dari CrewAI dan belum punya patched release; DiskCache memakai pickle untuk cache lokal; json-repair versi lama rentan CPU DoS melalui circular schema `$ref`.
* **Solusi**: Jangan expose Chroma server dan tunggu/validasi upstream fix; batasi write access cache DiskCache serta rencanakan serializer aman; constraint json-repair ke `>=0.60.1` hanya setelah compatibility test CrewAI dan Furniture QC.
* **Verifikasi**: Dependency tree menunjukkan ChromaDB/json-repair dari `crewai==1.6.1`, sedangkan DiskCache adalah dependency langsung. Pemakaian json-repair di Furniture QC tidak memberi argumen schema, jadi jalur DoS spesifik tidak langsung terbuka di call site itu.

## Log 79: Bandit Menemukan Security Debt pada Source
* **Masalah**: Bandit memindai 20.639 baris dan melaporkan 99 low, 13 medium, serta 7 high.
* **Root Cause**: Lima high MD5 dipakai hanya untuk slug filename dan merupakan false positive kriptografi. Risiko nyata mencakup `shell=True` di observability/cloud backup, pickle load indeks BM25, dan download model Hugging Face tanpa revision pin.
* **Solusi**: Perbaiki observability sesuai Log 76; ubah helper Git backup menjadi argv tanpa shell; pin commit model melalui `TTS_HF_REVISION`; dan rebuild/validasi indeks BM25 dari corpus tepercaya sebelum load. Jangan mass-suppress dengan `# nosec`.
* **Verifikasi**: Full pytest tetap lulus 299 test dan MCP audit secure; audit ini report-only sehingga source belum diubah.

## Log 80: Git WSL Membaca 63 File Berubah karena Mismatch CRLF
* **Masalah**: `git diff --check` melalui Git WSL melaporkan trailing whitespace pada ribuan baris dan `git status` melihat 63 file berubah, sementara Git Windows hanya melihat 5 entry workspace.
* **Root Cause**: Git Windows memakai system config `core.autocrlf=true`; Git WSL tidak mempunyai nilai `core.autocrlf`. Perbedaan normalisasi line-ending membuat file CRLF lama terlihat berubah penuh dari WSL.
* **Solusi**: Jangan normalisasi massal dalam task maintenance. Gunakan Git Windows untuk gate worktree ini atau buat task terpisah untuk `.gitattributes` dan migrasi line-ending terkontrol.
* **Verifikasi**: `git diff --check -- error_solutions.md` via Git Windows bersih dan tiga dokumen audit tidak memiliki trailing spaces; mismatch global WSL tetap dilaporkan apa adanya.

## Log 82: Regex Alternation Pecah saat PowerShell Memanggil `bash -lc`
* **Masalah**: Pola `rg` berisi banyak karakter `|` berubah menjadi pipeline shell; nama pola lalu dianggap sebagai command.
* **Root Cause**: Quoting regex tidak bertahan konsisten melalui lapisan PowerShell, `wsl.exe`, dan `bash -lc`.
* **Solusi**: Jalankan `rg` langsung dari PowerShell pada workspace UNC, atau gunakan beberapa `-e` tanpa shell ganda.

## Log 83: Glob `*.md` Tidak Diterima `rg` pada Path Windows
* **Masalah**: `rg ... docs *.md` menghasilkan error nama file/path tidak valid.
* **Root Cause**: Wildcard positional `*.md` tidak diekspansi seperti di Bash pada invocation PowerShell tersebut.
* **Solusi**: Gunakan filter ripgrep `-g '*.md'` dengan root pencarian eksplisit.

## Log 84: Hasil `foreach` PowerShell Tidak Bisa Langsung Dipipe
* **Masalah**: Loop metadata GitHub diikuti `| Format-Table` menghasilkan `An empty pipe element is not allowed`.
* **Root Cause**: Statement `foreach (...) { ... }` tidak diperlakukan sebagai ekspresi pipeline pada bentuk command tersebut.
* **Solusi**: Simpan hasil loop ke variabel (`$rows = foreach (...) { ... }`), lalu pipe `$rows` ke formatter.

## Log 85: Operator Null-Coalescing Tidak Didukung PowerShell Host
* **Masalah**: Audit schema memakai operator `??` dan berhenti dengan parser error.
* **Root Cause**: PowerShell host yang menjalankan command belum mendukung operator null-coalescing tersebut.
* **Solusi**: Gunakan pemeriksaan kompatibel `$keys.ContainsKey($k)` dan percabangan eksplisit sebagai pengganti `??`.
* **Verifikasi**: Audit schema berjalan setelah operator diganti tanpa mengubah data yang diperiksa.

## Log 86: Ruff Tidak Tersedia di Virtual Environment
* **Masalah**: Test Obsidian lulus, tetapi command lanjutan `bima_env/bin/ruff` gagal dengan `No such file or directory`.
* **Root Cause**: Ruff tercantum di dependency group dev, namun executable belum terpasang di `bima_env` yang aktif.
* **Solusi**: Jalankan Ruff secara terisolasi melalui `uvx ruff` agar tidak mengubah dependency runtime.
* **Verifikasi**: Verifikasi lint akhir memakai `uvx ruff check` pada file Python yang tersentuh.

## Log 87: Filter Obsidian Base Menghasilkan Escape YAML Berlebih
* **Masalah**: Test `.base` menemukan expression folder tersimpan dengan backslash escape sehingga bentuknya tidak mengikuti format Base yang mudah dibaca.
* **Root Cause**: Expression YAML dibungkus memakai `json.dumps`, sehingga quote di dalam expression ikut di-escape.
* **Solusi**: Tulis scalar YAML dengan single quote dan escape single quote YAML secara eksplisit.
* **Verifikasi**: Lima test Obsidian lulus, termasuk view, traversal, overwrite, Canvas ID, dan edge.

## Log 88: DuckDB Grouping Tidak Mengembalikan Kolom Grup
* **Masalah**: Agregasi `sum` per kategori hanya mengembalikan kolom `value`, bukan `category` dan `value`.
* **Root Cause**: `DuckDBPyRelation.aggregate()` memakai argumen kedua hanya sebagai group expression; kolom grup tetap harus dicantumkan pada projection agregasi.
* **Solusi**: Masukkan identifier grup tervalidasi ke expression hasil sekaligus ke `group_expr`.
* **Verifikasi**: Sembilan test DuckDB lulus untuk CSV, Parquet, lima operasi allowlist, group, output CSV, path, schema, dan limit.

## Log 89: Ruff Gate Terhalang Lint Debt Lama Mekanik
* **Masalah**: Ruff pada semua file tersentuh melaporkan tujuh error.
* **Root Cause**: Enam error sudah ada pada `teams/t8_mekanik.py` di HEAD sebelum task; satu error baru adalah import `os` yang tidak terpakai di test Strix.
* **Solusi**: Hapus hanya import baru milik task dan jangan melakukan drive-by cleanup pada enam error lama.
* **Verifikasi**: Seluruh file Python baru dan file registrasi selain Mekanik lulus Ruff; scan terhadap versi HEAD Mekanik mereproduksi enam error yang sama.

## Log 90: Nested Quote PowerShell ke Bash Memutus Python `-c`
* **Masalah**: Dua smoke command berhenti dengan `unexpected EOF while looking for matching quote`.
* **Root Cause**: String Python berquote melewati JavaScript, PowerShell, `wsl.exe`, lalu `bash -lc`, sehingga delimiter berubah sebelum sampai ke Python.
* **Solusi**: Hindari shell berlapis untuk smoke test; panggil `wsl.exe ... python` langsung atau gunakan ekspresi tanpa quote bersarang.
* **Verifikasi**: Compile, import smoke, dan Strix preflight berhasil dijalankan melalui invocation langsung.

## Log 91: Docker CLI Belum Tersedia untuk Strix
* **Masalah**: Preflight Strix aktual mengembalikan `Docker CLI belum terpasang di WSL`.
* **Root Cause**: Host WSL belum mempunyai Docker CLI/daemon yang dapat dipakai Strix.
* **Solusi**: Pertahankan `STRIX_ENABLED=false`; pasang/aktifkan Docker secara terpisah sebelum scan end-to-end pertama.
* **Verifikasi**: Wrapper berhenti aman sebelum snapshot dikirim atau API dipanggil; tujuh unit test Strix tetap lulus.

## Log 92: `uv pip check` Menemukan Sembilan Konflik Environment Lama
* **Masalah**: Dependency check melaporkan konflik pyarrow, protobuf, lance-namespace, rich, fsspec, aiofiles, starlette, dan torch/torchvision.
* **Root Cause**: Paket runtime lama di `bima_env` sudah mempunyai constraint yang saling bertentangan; instalasi DuckDB tidak mengubah paket-paket tersebut.
* **Solusi**: Jangan mengubah dependency di luar scope Paket A+B. Jadwalkan audit dependency terpisah agar setiap constraint diuji terhadap fitur terkait.
* **Verifikasi**: `uv lock --check` lulus, DuckDB 1.5.4 terpasang, dan full pytest lulus 320 test sebelum koreksi healthcheck.

## Log 93: Healthcheck Salah Menandai Vault OneDrive WSL
* **Masalah**: Healthcheck menganggap setiap path `/mnt/c/` sebagai konfigurasi Windows yang salah walau vault OneDrive dapat diakses.
* **Root Cause**: `_check_vault()` memeriksa prefix mount sebelum memeriksa keberadaan path.
* **Solusi**: Nilai kesehatan vault dari akses filesystem; path mount WSL yang ada dinyatakan sehat.
* **Verifikasi**: Regression test baru lulus dan healthcheck melaporkan `Vault accessible` pada vault OneDrive aktif.

## Log 94: `uv lock` Menulis Ulang Marker CUDA yang Tidak Terkait
* **Masalah**: Penambahan DuckDB ikut mengubah marker platform optional CUDA pada package lain.
* **Root Cause**: Versi `uv` saat ini menormalisasi ulang marker lama ketika lockfile dibuat ulang.
* **Solusi**: Kembalikan marker CUDA ke isi sebelumnya dan pertahankan hanya entry DuckDB beserta referensinya.
* **Verifikasi**: Diff lockfile tidak lagi membawa perubahan marker CUDA dan `uv lock --check` tetap lulus.

## Log 95: DuckDB Melempar Exception pada Agregasi Tipe String
* **Masalah**: Operasi `sum` terhadap kolom VARCHAR melempar `BinderException` keluar dari tool dan dapat memutus eksekusi agent.
* **Root Cause**: Error DuckDB tidak termasuk dalam tuple exception yang dikonversi menjadi respons `FAILED`.
* **Solusi**: Import DuckDB sebagai dependency runtime dan tangkap `duckdb.Error` bersama error input/path.
* **Verifikasi**: Regression test kolom string gagal sebelum perbaikan lalu lulus; total test DuckDB menjadi 10.

## Log 96: PM2 Tidak Mempunyai Process `anisa-v3`
* **Masalah**: `pm2 restart anisa-v3 --update-env` gagal dengan `Process or Namespace anisa-v3 not found`.
* **Root Cause**: Daemon PM2 aktif tetapi process list kosong, sehingga tidak ada process yang dapat di-restart.
* **Solusi**: Jalankan deklarasi resmi `pm2 start ecosystem.config.js`, bukan membuat command process manual.
* **Verifikasi**: `anisa-v3`, `bima-tunnel`, `bima-whatsapp`, dan `anisa-status` online tanpa restart loop; endpoint 8000 dan 8001 merespons.

## Log 97: Variabel Bash `$port` Dihabiskan PowerShell
* **Masalah**: Loop smoke test menampilkan `PORT__NOT_READY` untuk kedua port.
* **Root Cause**: PowerShell mengembangkan `$port` sebelum string command sampai ke Bash WSL.
* **Solusi**: Hindari variabel shell berlapis dan panggil dua URL smoke test secara eksplisit.
* **Verifikasi**: `http://127.0.0.1:8001/health` mengembalikan status ok dan `/api/metrics` port 8000 mengembalikan metrics JSON.

## Log 98: Git Windows Gagal Menulis Multi-Pack-Index WSL
* **Masalah**: Setelah commit, auto geometric repack melaporkan `could not write multi-pack-index: Permission denied`.
* **Root Cause**: Commit dijalankan oleh Git Windows pada checkout UNC WSL; file pack dimiliki user Linux dan operasi maintenance lintas filesystem gagal walau penulisan commit berhasil.
* **Solusi**: Perlakukan sebagai kegagalan maintenance, bukan kegagalan commit. Jalankan maintenance repository melalui Git WSL pada task terpisah bila pack perlu dirapikan.
* **Verifikasi**: Commit tetap terbentuk dengan 24 file; ownership dan mode `.git/objects/pack` valid untuk user `bima_lucian` di WSL.

## Log 99: JSON PM2 Mengandung UTF-8 BOM
* **Masalah**: Parser Python gagal membaca output `pm2 jlist` dengan `JSONDecodeError: Unexpected UTF-8 BOM`.
* **Root Cause**: Pipeline PowerShell/WSL meneruskan BOM di awal stream JSON, sedangkan `json.load(sys.stdin)` memakai decoder UTF-8 biasa.
* **Solusi**: Untuk status singkat gunakan `pm2 status`, atau decode byte stream dengan `utf-8-sig` sebelum `json.loads`.
* **Verifikasi**: Status PM2 sebelumnya menunjukkan empat process online; smoke endpoint port 8000 dan 8001 tetap sukses pada pemeriksaan yang sama.

## Log 100: WhatsApp Bridge Mengirim `❌ Error: r` Berulang
* **Masalah**: Satu kegagalan WhatsApp Web memicu ratusan balasan `❌ Error: r` melalui event `message_create`.
* **Root Cause**: Handler memanggil `msg.getChat()` sebelum menyaring event balasan bot. Saat `getChat()` melempar `r`, blok `catch` membalas error; balasan itu memicu `message_create` baru dan mengulang siklus.
* **Solusi**: Saring prefix atau armed voice sebelum operasi async WhatsApp, pertahankan detail error hanya di log, dan kirim pesan generik ke user.
* **Verifikasi**: Unit test filter, syntax check Node, restart PM2, health endpoint, dan log startup WA tanpa kemunculan baru `❌ [WA] r`.

## Log 101: Loop Polling Health Rusak di Shell Berlapis
* **Masalah**: Polling endpoint berhenti dengan `syntax error near unexpected token '2'` sebelum sempat menjalankan `curl`.
* **Root Cause**: `$(seq ...)` dan variabel loop Bash berubah saat command melewati PowerShell, `wsl.exe`, lalu `bash -lc`.
* **Solusi**: Gunakan polling tanpa variabel lintas shell: `timeout 60 bash -c 'until curl -fsS URL; do sleep 2; done'`.
* **Verifikasi**: Polling pengganti mengembalikan `{"status":"ok","busy":false}` dari port 8001.

## Log 102: Pemeriksaan Checklist PLAN Memberi False Positive
* **Masalah**: Verifikasi akhir menganggap PLAN masih memiliki step kosong walau semua task sudah dicentang.
* **Root Cause**: Pencarian substring `- [ ]` juga cocok dengan contoh sintaks checkbox di header PLAN.
* **Solusi**: Cari hanya checkbox pada awal baris memakai regex `^- \[ \]`.
* **Verifikasi**: Pemeriksaan berbasis baris tidak menemukan task yang belum dicentang.
## Log 103: Path Dokumentasi Salah Case
* **Masalah**: Pembacaan `/home/bima_lucian/BIMA_CORE/claude.md` gagal walaupun panduan proyek tersedia.
* **Root Cause**: Filesystem Linux case-sensitive dan nama file aktual adalah `CLAUDE.md`.
* **Solusi**: Cari nama aktual dengan `rg --files -g 'CLAUDE.md' -g 'claude.md'`, lalu baca `CLAUDE.md` dengan case yang tepat.

## Log 104: Audit Threads Mengasumsikan Modul Client Terpisah
* **Masalah**: Pencarian awal menyertakan `core/threads_client.py` dan menghasilkan file-not-found.
* **Root Cause**: Implementasi Threads Graph API berada langsung di `core/threads_commands.py`; tidak ada modul `threads_client.py`.
* **Solusi**: Temukan simbol dengan `rg` sebelum menyebut path. Gunakan `publish_post_to_threads()`, `fetch_user_posts()`, dan `fetch_post_replies()` dari `core/threads_commands.py` sebagai sumber aktual.

## Log 105: Regex Alternation Verifikasi Plan Pecah di Lintas Shell
* **Masalah**: Verifikasi placeholder gagal dan Bash mencoba menjalankan kata `TODO`, `implement`, `Similar`, serta `Add` sebagai command.
* **Root Cause**: Karakter alternation `|` pada regex tidak bertahan sebagai bagian argumen saat command melewati PowerShell ke WSL Bash.
* **Solusi**: Hindari alternation pada command lintas-shell. Gunakan beberapa argumen `rg -e` atau jalankan skrip langsung dari shell WSL tanpa lapisan quoting tambahan.

## Log 106: String Tuple Checkpoint Merusak Wrapper Bash
* **Masalah**: Verifikasi kedua berhenti dengan `syntax error near unexpected token '('`.
* **Root Cause**: Kutip ganda pada string literal tuple checkpoint menutup argumen `bash -lc` lebih awal saat dilewatkan dari PowerShell.
* **Solusi**: Jangan memverifikasi literal kompleks melalui nested shell. Jalankan pemeriksaan konten dengan PowerShell native dan gunakan WSL hanya untuk command Git sederhana.

## Log 107: PDFGeneratorTool Crash pada key_values Multi-Field
* **Masalah**: Generate PDF dengan section `key_values` berisi 2+ field (kasus wajib untuk surat izin/biodata) crash dengan `FPDFException: Not enough horizontal space to render a single character`.
* **Root Cause**: Loop di `teams/t4_admin/pdf_tool.py` memanggil `cell()` lalu `multi_cell(0, ...)` tanpa reset posisi X ke margin kiri. Default fpdf2 untuk `multi_cell` adalah `new_x=RIGHT`, jadi cursor X numpuk ke kanan tiap iterasi sampai lebar tersisa jadi negatif pada field kedua/ketiga.
* **Solusi**: Tambahkan `new_x="LMARGIN", new_y="NEXT"` pada `multi_cell` di dalam loop key_values, mengikuti pola yang sudah dipakai di bagian lain file yang sama. Diverifikasi dengan generate surat izin 4 field — render sukses dan sejajar rapi.

## Log 108: TOC Level-1 Tampil Terdorong ke Tepi Kanan
* **Masalah**: Entry Daftar Isi (TOC) level 1 (indent 0) di PDF render menempel/terpotong di tepi kanan halaman alih-alih rata kiri.
* **Root Cause**: `pdf.cell(indent, 7, "")` dipakai sebagai spacer indent; saat `indent == 0` (level 1, kasus paling umum), fpdf2 menafsirkan lebar cell `0` sebagai "auto-extend ke margin kanan" (bukan cell kosong lebar nol), jadi cursor X ikut lompat ke margin kanan sebelum teks heading dirender.
* **Solusi**: Ganti spacer dengan `pdf.set_x(pdf.get_x() + indent)` yang hanya dipanggil kalau `indent > 0`, sehingga cell lebar-0 dari fpdf2 tidak pernah dipanggil untuk kasus tanpa indent. Diverifikasi: TOC 4 entry level-1 pada dokumen cover+multipage render rata kiri normal.

## Log 109: Judul Dobel di Halaman Konten Pertama PDF Saat cover=false
* **Masalah**: Untuk dokumen non-cover (surat/invoice/notulen), judul muncul dobel di halaman 1: running-header kecil di pojok kiri + judul besar di tengah, teks identik.
* **Root Cause**: `header()` di `teams/t4_admin/pdf_tool.py` hanya skip halaman 1 kalau `cover=true`. Begitu `cover=false`, running-header ikut tampil di halaman yang sudah render judul besar.
* **Solusi**: Simpan nomor halaman konten pertama di list mutable `_first_content_page` dan skip `header()` khusus di halaman itu. Diverifikasi 3 skenario (no-cover, cover+TOC, halaman isi pasca-TOC) — running-header tetap muncul di halaman lanjutan, tidak dobel di halaman judul.

## Log 110: Word key_values Kolom Nilai Melebar (Titik Dua Kejauhan)
* **Masalah**: Tabel `key_values` di Word (data diri surat izin/biodata) menampilkan jarak kosong besar antara titik dua dan nilai; kolom nilai melebar tak proporsional.
* **Root Cause**: Table default `autofit=True` bikin Word mengabaikan `cell.width`; selain itu lebar hanya di-set per-cell (`tcW`) tanpa mengubah `tblGrid`, padahal layout fixed-width Word mengacu ke `tblGrid`.
* **Solusi**: Set `kv_table.autofit = False`, lalu set lebar via `table.columns[i].width` (mengubah `tblGrid`/`gridCol`) DAN tetap set `cell.width` per baris agar `tcW` konsisten. Diverifikasi via konversi LibreOffice→PDF: titik dua rapat, nilai langsung menyusul.

## Log 111: OfficeCLI Excel — Cell Ter-offset ke Kanan (add sheet+remove & add column)
* **Masalah**: Semua penulisan cell di Excel meleset ke kanan meski OfficeCLI melaporkan sukses di alamat yang benar; sheet Ringkasan mulai kolom C, sheet data berikutnya makin geser (mulai kolom G).
* **Root Cause**: Dua pola di `teams/t4_admin/excel_tool.py` memicu insert-shift OfficeCLI: (1) `add sheet baru` lalu `remove /Sheet1`, dan yang utama (2) `add --type column --prop name=X` — schema OfficeCLI menegaskan insert kolom di slot terisi menggeser semua kolom di kanannya. Besar offset = jumlah `add column` per sheet (Ringkasan 2 kolom → offset 2; sheet data 6 kolom → offset 6).
* **Solusi**: (1) Rename Sheet1 default via `set /Sheet1 name=...` alih-alih add+remove; (2) atur lebar kolom via `set /Sheet/col[X] --prop width=...` (auto-vivify, tidak menggeser) alih-alih `add --type column`. Diverifikasi: Ringkasan A1:D6, sheet data A1:F6, formula & lebar kolom tetap benar. Catatan authoring: kalau sheet punya field `title`, header pindah ke baris 2 dan data mulai baris 3 — range formula (`=SUM(...)`) harus ikut memperhitungkan geseran ini.

## Log 112: Agen Arsip Tidak Menjamin Struktur Vault Rapi
* **Masalah**: Audit menemukan 27 catatan Auto-Save seluruhnya disimpan di folder akar, metadata sumber selalu `ANISA Auto-Save`, deduplikasi hanya membandingkan 200 karakter awal pada nama file yang sama, dan permintaan pencarian yang lewat Manager berpotensi dipaksa menjadi aksi simpan. `VaultLinkerTool` juga hanya berjalan saat diminta dan menghapus seluruh bagian setelah heading `Catatan Terkait` sebelum membangunnya ulang.
* **Root Cause**: `VaultSaveTool` tidak memiliki schema kategori/tags/sumber atau allowlist folder; keputusan judul sepenuhnya diserahkan ke LLM. `arsip_node()` menganggap setiap pesan terakhir sebagai data upstream tanpa membedakan keluaran Manager dan spesialis. Routing regex hanya menangkap frasa eksplisit tertentu. Belum ada test khusus save, organizer, linker, atau routing node Arsip.
* **Dampak**: Vault bertambah sebagai tumpukan file akar, topik yang sama dapat menghasilkan versi duplikat, provenance hilang, pencarian natural tertentu dapat salah aksi, dan konten manual di bawah `Catatan Terkait` berisiko terhapus ketika linker dijalankan.
* **Solusi / Pencegahan**: Terapkan schema simpan tervalidasi dengan kategori allowlist dan fallback `_Inbox`, YAML frontmatter, content hash/upsert, serta sumber asli. Bedakan `upstream specialist output` dari pesan Manager melalui state eksplisit. Batasi linker pada blok bertanda khusus, bukan regex sampai EOF. Tambahkan unit test sebelum perubahan dan jangan migrasikan 54 file existing tanpa backup serta persetujuan terpisah.

## Log 113: PDF Bullet List Crash (Pola multi_cell Sama seperti key_values)
* **Masalah**: Generate PDF dengan section berisi field `list` (bullet) crash `FPDFException: Not enough horizontal space` di style yang punya bullet (informal, semi_formal). Loop referensi juga salah indent URL.
* **Root Cause**: Sama seperti Log 77 — loop `list` di `teams/t4_admin/pdf_tool.py` memanggil `cell()` lalu `multi_cell(0, ...)` tanpa `new_x="LMARGIN"`, jadi cursor X numpuk ke kanan tiap item sampai lebar negatif. Loop `references` juga tidak reset X sebelum `cell()` indent URL.
* **Solusi**: Tambah `new_x="LMARGIN", new_y="NEXT"` pada `multi_cell` di loop `list` dan pada `multi_cell` teks referensi. Diverifikasi: blog informal (3 bullet) dan tutorial semi_formal render normal, URL referensi ter-indent rapi.

## Log 114: PDF Akademik — Penomoran Romawi Front Matter Tak Muncul
* **Masalah**: Halaman depan skripsi (abstrak, daftar isi) menampilkan angka Arab ("halaman 2") alih-alih Romawi ("ii"); body sudah benar Arab.
* **Root Cause**: `_body_start_page` di-set saat body mulai render, padahal footer fpdf digambar lazy saat page-break — footer front matter telanjur tergambar sebelum nilai itu ada, jatuh ke cabang Arab.
* **Solusi**: Pra-hitung `_body_start_page` sebelum cover di-add, dari kombinasi cover+abstrak+toc. Diverifikasi footer akademik PDF: `[cover kosong, ii, iii, 1, 2]`.

## Log 115: Word Akademik — Format Romawi/Arab Tertukar + Footer Front Matter Kosong
* **Masalah**: Body skripsi Word menampilkan Romawi ("halaman i"), sedangkan front matter tak bernomor sama sekali.
* **Root Cause**: (1) Di OOXML, `sectPr` yang di-embed di paragraf section-break mengatur section SEBELUMNYA (front matter), sedang `sectPr` level-body mengatur section TERAKHIR (body). Kode `word_tool.py` memasang `lowerRoman` di body-level dan `decimal` di break-para — tertukar. (2) Footer hanya diisi pada section body; section front matter footernya kosong & masih `linkedToPrevious`.
* **Solusi**: Tukar format (body=`decimal`, front matter=`lowerRoman`) dan, setelah section-break dibuat, putus link footer front matter lalu isi ulang lewat helper `_populate_footer`. Diverifikasi footer akademik Word: `[i, ii, iii, 1, 2]`.

## Log 116: Word — Chart/Gambar Ter-clip Jadi Sliver oleh Exact Line Spacing
* **Masalah**: Chart & gambar di dokumen Word muncul sebagai garis tipis (tinggi ~1 baris) alih-alih ukuran penuh, walau `<wp:extent>` di XML sudah benar (mis. 6"×3.34").
* **Root Cause**: Style `Normal` memakai `line_spacing` EKSAK dalam Pt (mis. `Pt(11.5)`). Paragraf hasil `doc.add_picture()` mewarisi style Normal, dan Word/LibreOffice meng-clip gambar inline ke tinggi baris eksak. XML gambar sendiri valid — masalahnya di line spacing paragraf induk.
* **Solusi**: Setelah tiap `doc.add_picture()` (chart maupun `image_path`), set `doc.paragraphs[-1].paragraph_format.line_spacing = 1.0`. Diverifikasi: pie chart formal Word render penuh (bbox 432×241pt), bukan sliver.

## Log 117: bima-whatsapp Crash-Loop — Puppeteer Chrome Tidak Ditemukan
* **Masalah**: pm2 `bima-whatsapp` stuck restart terus-menerus (964+ restart, status "waiting", 0b memory). `wa-error.log` menunjukkan `Error: Could not find Chrome (ver. 146.0.7680.31)` dari `whatsapp-web.js`/Puppeteer.
* **Root Cause**: Folder cache `~/.cache/puppeteer` tidak ada sama sekali di sistem — Chrome binary yang dipakai Puppeteer belum pernah/gak lagi ter-install, bukan karena env var atau config yang sengaja disable download.
* **Solusi**: Jalankan `npx puppeteer browsers install chrome` di `whatsapp/` (menambah ~371MB ke disk WSL), lalu `pm2 restart bima-whatsapp`. Diverifikasi: log menunjukkan `🔐 Auth OK` dan `🚀 Anisa WA Bridge ONLINE` setelah restart, tidak crash lagi.

## Log 118: P0 Audit — Path Escape, Thread Bocor, dan XSS Activity Log
* **Masalah**: Nama/path dari LLM dapat keluar dari root tujuan, reference image dapat dibaca lalu dikirim ke API eksternal, seluruh user WhatsApp berbagi checkpoint `anon_whatsapp`, callback Discord berbagi key per user, dan activity log merender string backend sebagai HTML.
* **Root Cause**: Join/resolve path tidak diikuti containment check; bridge WhatsApp tidak meneruskan sender ID; thread ID memakai jenis channel literal alih-alih ID percakapan nyata; `dangerouslySetInnerHTML` menerima `l.text` tanpa escape.
* **Dampak**: File arbitrary dapat dibaca/ditimpa atau tereksfiltrasi, konteks percakapan/progress dapat tertukar antar-user/channel, dan payload backend dapat menjalankan JavaScript di dashboard.
* **Solusi / Pencegahan**: Tambahkan helper path berbasis `resolve()` + containment/symlink check, sanitasi nama output, dan batasi reference image ke `outputs/`. Bentuk checkpoint/callback key dari `source_channel:user_id:conversation_id`, teruskan sender WA serta channel Discord, dan render activity log sebagai React text node. Regression P0 lulus 31 test terarah; full suite tetap hanya memiliki 6 failure Marp baseline.
* **Penyesuaian teknis**: Test RED image reference sempat memakai key palsu tanpa mock client sehingga OpenRouter menolak request 401. Test diperketat dengan mock boundary dan assertion bahwa client tidak pernah dibuat. Browser smoke menemukan simulated log dari `guild-data.jsx` masih berisi markup; template itu diubah ke plain text dan diverifikasi langsung di `/dashboard/v3/`. Command deteksi Git dengan `$()` sempat diparse PowerShell; pemeriksaan berikutnya dipecah menjadi command `wsl.exe git` tanpa nested interpolation. Runtime smoke awal juga memakai path dokumentasi stale `healthcheck.py`; path aktual adalah `scripts/healthcheck.py`.

## Log 119: Discord Mengabaikan Gambar Tanpa Caption
* **Masalah**: Gambar yang dikirim sendirian di Discord tidak mendapat respons dan tidak dianalisis oleh Vision.
* **Root Cause**: Early-return di `core/discord_bot.py` hanya mengecualikan attachment audio dari aturan pesan kosong. Attachment gambar berhenti sebelum download dan sebelum `attachment_paths` diteruskan ke LangGraph.
* **Dampak**: ImageAnalyzerTool tidak pernah dipanggil walaupun format gambar valid dan jalur Visual tersedia.
* **Solusi / Pencegahan**: Izinkan pesan kosong khusus attachment gambar yang didukung, lalu isi prompt internal `analisis gambar ini` setelah download berhasil agar intent classifier memilih tim Visual. Regression test mencakup gambar tanpa caption, file non-gambar, preservasi caption, dan hasil routing Visual.

## Log 120: Vision Discord Terdeteksi tetapi Gagal Sebelum Tool Dipanggil
* **Masalah**: Setelah gambar tanpa caption berhasil masuk tim Visual, Crew gagal sebelum `ImageAnalyzerTool` memberi hasil.
* **Root Cause**: Agent controller Visual memakai Gemini 3.5 Flash berbayar lewat OpenRouter tanpa batas output eksplisit. CrewAI mengirim `max_tokens=65536`; OpenRouter membalas HTTP 402 karena saldo saat itu hanya mengizinkan sekitar 1.867 token.
* **Dampak**: Routing dan download gambar berhasil, tetapi pengguna tetap tidak menerima analisis gambar.
* **Solusi / Pencegahan**: Untuk image-only, `visual_node` sekarang memanggil `ImageAnalyzerTool` langsung agar tidak membuat call controller Gemini kedua dan batas output tetap 1.500 token. Model/config global tidak diubah. Regression test memastikan CrewAI tidak dipanggil; smoke call pada gambar Discord tersimpan berhasil mengembalikan analisis Vision lengkap.

## Log 121: P1 Audit — Functional Safety dan Runtime Cleanup
* **Masalah**: Audit menemukan sisa path escape di tool file/gambar, sanitizer WhatsApp merusak code/URL, exception internal bocor ke chat, setup Threads dapat menulis token `None` ke `.env` relatif CWD, approval slide dapat di-bypass, Marp WSL memilih Chrome Windows, backup melakukan `git add/commit/push` unattended dari repo aktif, Browser Use meninggalkan child process saat timeout, dan Sherlock crash pada input spasi.
* **Root Cause**: Trust boundary belum memakai resolver terpusat; sanitizer berbasis regex tidak memahami state code/kurung; exception langsung diinterpolasi ke return; script setup memakai `Path('.env')`; schema publik mengekspos `bypass_preview`; pencarian browser hanya memeriksa Playwright lalu fallback ke `.exe`; backup mencampur repository development dengan destination backup; `subprocess.run(timeout=...)` hanya menghentikan worker utama; normalisasi Sherlock mengakses elemen hasil `split()` tanpa cek kosong.
* **Dampak**: File di luar `outputs/` dapat dibaca/ditulis, payload chat berubah, detail sistem terekspos, credential Threads rusak/salah lokasi, approval dapat dilewati, slide gagal di WSL, perubahan kerja dapat ter-push otomatis, proses browser yatim menghabiskan resource, dan input whitespace mematikan tool OSINT.
* **Solusi / Pencegahan**: Terapkan confinement pada seluruh boundary P1; parser WhatsApp stateful; helper error publik dengan detail hanya di log; token validation dan `ENV_PATH` absolut; pisahkan `_run` approval dari `_compile` privat serta pilih Chrome Puppeteer Linux; ganti cloud backup dengan safety stub; jalankan Browser worker sebagai process group dengan eskalasi `SIGTERM`→`SIGKILL`; normalisasi Sherlock sebelum `split()`. Targeted gate lulus 34 Python + 4 Node test, full suite lulus 344 test, healthcheck lulus 51 dengan 1 warning, endpoint WA sehat, dan kedua proses PM2 online.
* **Penyesuaian teknis**: Startup backend setelah restart membutuhkan sekitar 26 detik sehingga batch curl pertama selesai sebelum service siap; pemeriksaan ulang berhasil. Trace `KeyboardInterrupt` MCP pada log merupakan child process lama yang dihentikan saat restart; PID backend baru tetap online dan `/health` 200. Test RED slide sempat menjalankan Marp lama karena `_compile` belum ada, menghasilkan enam kegagalan browser yang memang menjadi bukti baseline sebelum refactor.

## Log 122: P2 Audit — Resource Lifetime, Race, dan False Success
* **Masalah**: Browser worker menganggap output parsial sebagai sukses dan profile marketplace dipakai paralel; footer PDF akademik salah saat abstract/TOC lebih dari satu halaman; penghapusan satu jadwal dapat terpetakan ke clear-all; organizer memindahkan file yang baru dibuat dan abort saat satu file locked; diagram bisa tertimpa dalam detik yang sama; matplotlib figure serta workbook Excel bocor pada exception. Audit Canvas WA juga belum punya regression proof.
* **Root Cause**: Worker hanya mengecek `final_result()` tanpa `is_done()`/`is_successful()` dan profile persistent tanpa file lock; footer menghitung jumlah front matter secara asumsi; ScheduleManager hanya punya `clear`; organizer tidak punya age guard/isolasi error; filename diagram hanya timestamp detik; cleanup resource hanya berada di success path. Canvas memakai nama field legacy Discord walau identity WA sudah diteruskan sejak P0.
* **Dampak**: Task browser setengah jadi dapat dilaporkan berhasil, Chromium profile race/corrupt, nomor halaman akademik salah, seluruh jadwal berisiko terhapus, file output hilang sebelum dikirim, batch organizer rapuh, artefak diagram tertimpa, serta memory/file descriptor bertambah perlahan.
* **Solusi / Pencegahan**: Wajibkan Browser history done+successful dan kunci profile marketplace memakai `fcntl.flock`; gunakan phase footer front/body aktual; tambah delete jadwal match-unik dan permission gate untuk delete/clear; tahan file organizer 5 menit serta lanjut per-file; gunakan SHA-256+nanosecond untuk diagram; tutup figure/workbook di `finally`; tambah regression route Canvas WA dan pesan channel-neutral. Targeted P2 lulus 41 test, full suite lulus 368 test dengan 2 warning dependency, compileall/diff bersih, backend restart online, dan `/health` 200.
* **Penyesuaian teknis**: Patch gabungan chart+Excel pertama gagal karena konteks docstring Excel berbeda dari plan; tidak ada hunk yang diterapkan, file dibaca ulang lalu dipatch terpisah. Trace `KeyboardInterrupt` sebelum startup baru berasal dari penghentian MCP child saat restart; PID baru mencapai Uvicorn startup complete dan MCP startup normal.

## Log 123: P3 Audit — Consistency dan Async Blocking
* **Masalah**: Prompt Manager menyebut 20 pilihan walau menu berisi 22; cache compiled graph memakai integer `id(event_loop)` yang dapat dipakai ulang; pemeriksaan/penulisan cost SQLite sinkron berjalan dari jalur async; script npm AgentMemory tidak memuat profile tools yang sama dengan PM2; script Threads pernah memakai `.env` relatif CWD.
* **Root Cause**: Teks prompt drift setelah penambahan route; cache tidak menyimpan identity object loop; callback cost memakai handler sinkron dan Discord memanggil fungsi SQLite langsung; `package.json` tertinggal dari `ecosystem.config.js`; path Threads belum di-root sebelum P1.
* **Dampak**: Instruksi routing inkonsisten, app/checkpointer loop lama berpotensi tertukar bila ID Python dipakai ulang, event loop dapat tersendat oleh file I/O SQLite, startup AgentMemory manual berbeda dari PM2, dan setup Threads berisiko menyentuh `.env` yang salah.
* **Solusi / Pencegahan**: Sinkronkan prompt ke 22; key cache memakai `WeakKeyDictionary` dengan object event loop; offload cost guard dan async callback melalui `asyncio.to_thread`; samakan npm start ke `agentmemory --tools core`; pertahankan `ENV_PATH` absolut yang sudah ditutup P1. Targeted P3+regression lulus 17 test, full suite lulus 373 test dengan 2 warning dependency, compileall/diff bersih, npm membaca script yang benar, backend restart online, dan `/health` 200.

## Log 124: Dashboard ANISA Layar Putih → Dinonaktifkan Permanen
* **Masalah**: Aplikasi desktop ANISA (`anisa-desktop.exe`, Electron) menampilkan window putih kosong saat dibuka.
* **Root Cause**: Bukan bug — dashboard (`/dashboard` dan `/dashboard/v3`, di-mount dari `core/dashboard_server.py`) tetap sehat (HTTP 200, `/api/metrics` normal). Investigasi live-request menunjukkan Electron app masih polling backend saat window putih terjadi, jadi kemungkinan besar penyebabnya di sisi render Electron (cache/GPU/proses lama), bukan backend atau kode dashboard itu sendiri. Tidak dikonfirmasi lebih lanjut karena Bima memilih mematikan dashboard, bukan memperbaikinya.
* **Dampak**: Tidak ada dampak fungsional ke bot (Discord/WhatsApp) — dashboard server berjalan independen, hanya diimpor dari `main.py` startup block dan dua test file yang mengimpor langsung.
* **Solusi / Pencegahan**: Hapus pemanggilan `start_in_background()` di `main.py` (blok try/except start dashboard) sehingga `core/dashboard_server.py` tidak pernah di-mount. Port 8000 tidak lagi listening setelah restart `anisa-v3`. Kode `dashboard_server.py` dan folder `dashboard/`, `frontend/dashboard.html` dibiarkan utuh (tidak dihapus) untuk kemungkinan diaktifkan lagi nanti.
* **Penyesuaian teknis**: `pm2 restart anisa-v3` butuh beberapa detik untuk proses lama benar-benar berhenti — log sempat menunjukkan request `/api/metrics` lanjut dan trace `KeyboardInterrupt`/`Aborted!` dari proses lama yang di-terminate, bukan error dari proses baru. Verifikasi akhir pakai `ss -tlnp` untuk memastikan port 8000 sudah tidak listening.
* **Penyesuaian teknis**: Verifikasi Node inline dua kali gagal karena nested quote PowerShell→WSL memotong ekspresi JavaScript; diganti `npm pkg get scripts.start`, yang sekaligus mem-parse `package.json` dan mengembalikan nilai yang diharapkan. Trace `KeyboardInterrupt` sebelum PID baru tetap merupakan shutdown MCP child lama; startup baru Uvicorn dan MCP bersih.
## Log 125: Format `git for-each-ref` Pecah di PowerShell ke WSL
* **Masalah**: Command audit branch memakai `--format="%(...)"` gagal dengan syntax error sebelum Git dijalankan.
* **Root Cause**: Quote dan tanda kurung pada placeholder format diparse ulang saat melewati PowerShell, `wsl.exe`, lalu `bash -lc`.
* **Solusi**: Jalankan format kompleks langsung di shell WSL atau pecah audit menjadi command Git sederhana tanpa nested format.

## Log 126: Branch Protection API Mengembalikan HTTP 404
* **Masalah**: `gh api repos/.../branches/main/protection` mengembalikan HTTP 404 saat audit setting repository.
* **Root Cause**: Branch `main` memang belum memiliki protection rule; autentikasi tetap valid.
* **Solusi**: Perlakukan 404 endpoint protection sebagai state `not protected`, bukan kegagalan autentikasi. Aktifkan protection hanya lewat perubahan settings yang disetujui.

## Log 127: `git diff --check` Membawa Whitespace dari Merge Base Lama
* **Masalah**: Verifikasi PR #8 terhadap head branch sebelum cleanup melaporkan whitespace pada dokumen yang baru masuk dari merge `main`.
* **Root Cause**: Range `origin/codex/package-a-b-integration..HEAD` ikut memeriksa seluruh commit baru dari `main`, bukan hanya diff PR terhadap base terkini.
* **Solusi**: Untuk gate perubahan PR setelah sinkronisasi, jalankan `git diff --check origin/main..HEAD`; hasilnya bersih tanpa melakukan drive-by formatting pada dokumen lama.
