# BIMA_CORE — Error & Solution Log

Dokumen ini mencatat kesalahan (error/oversight) yang ditemui selama pengembangan dan solusi perbaikannya sebagai acuan di masa mendatang.

---

## 📌 Log 1: Kegagalan Validasi Eksistensi Modul / Dependency (`browser-use`)

* **Tanggal**: 4 Juni 2026
* **Jenis**: Architectural/Oversight Error
* **Deskripsi Masalah**:
  Agen mengusulkan untuk mengintegrasikan library `browser-use` sebagai "hidden gem" baru untuk di-install ke dalam sistem, padahal library tersebut sudah tertera di [requirements.txt](file:///wsl$/Ubuntu/home/bima_lucian/BIMA_CORE/requirements.txt) (baris 25) dan sudah diintegrasikan sebagai tool utama di [tools/browser_use_tool.py](file:///wsl$/Ubuntu/home/bima_lucian/BIMA_CORE/tools/browser_use_tool.py) serta dipakai oleh `t5_intel.py`.
* **Dampak**:
  Mengusulkan pekerjaan ganda (redundant suggestion) yang menurunkan efisiensi pengembangan.
* **Solusi / Tindakan Pencegahan**:
  1. **Wajib Kroscek Lokal**: Sebelum mengusulkan integrasi tool/library baru dari GitHub trending, agen harus memeriksa `requirements.txt` dan memindai direktori `tools/` atau `core/` untuk memastikan tool serupa belum pernah diimplementasikan.
  2. **Audit Kode Mandiri**: Lakukan `grep_search` dengan nama library sebelum melakukan presentasi fitur ke pengguna.

---

## 📌 Log 2: Mismatch Bahasa Asersi Pengujian (`tests/test_mcp_security.py`)

* **Tanggal**: 4 Juni 2026
* **Jenis**: Test Code Mismatch Error
* **Deskripsi Masalah**:
  Test suite `test_mcp_security.py` gagal saat memvalidasi status `unsafe` karena mengharapkan teks asersi dalam Bahasa Inggris (`"not whitelisted"` dan `"dangerous keyword"`), sementara output logika aslinya di `core/mcp_security.py` menggunakan Bahasa Indonesia (`"tidak terdaftar di whitelist"` dan `"keyword berbahaya"`).
* **Dampak**:
  Unit test gagal (False Negative) meskipun fungsi logika intinya berjalan 100% benar.
* **Solusi / Tindakan Pencegahan**:
  Sesuaikan selalu bahasa/locale string pada asersi unit test agar sinkron dengan output teks dari modul yang diuji.

---

## 📌 Log 3: Kegagalan Launch Headless Browser Marp CLI di Lingkungan WSL

* **Tanggal**: 4 Juni 2026
* **Jenis**: Environment Execution Error
* **Deskripsi Masalah**:
  Marp CLI gagal mengekspor slide presentasi ke PDF/PPTX/PNG di WSL karena tidak menemukan Chromium lokal (`No suitable browser found`). Ketika diarahkan ke Windows Chrome Host via path `/mnt/c/Program Files/...`, Puppeteer crash (`UnhandledPromiseRejection`) akibat masalah koneksi port debugging/firewall Windows ke WSL.
* **Dampak**:
  Slide generator gagal memproses/mengompilasi presentasi dan memicu asersi gagal di test suite.
* **Solusi / Tindakan Pencegahan**:
  1. Manfaatkan cache local Chromium yang sudah diunduh oleh Playwright di WSL (`~/.cache/ms-playwright/`).
  2. Buat pencarian direktori dinamis di python `tools/slide_generator.py` untuk mendeteksi file executable `chrome` di cache tersebut dan set ke `CHROME_PATH`.
  3. Hal ini membuat Puppeteer berjalan native secara local di dalam WSL tanpa sandboxing error (`CHROME_NO_SANDBOX=1`).

---

## 📌 Log 4: Kesalahan Target Mocking (`tests/test_slide_generator.py`)

* **Tanggal**: 4 Juni 2026
* **Jenis**: Unit Test Mocking Error
* **Deskripsi Masalah**:
  Pengujian asersi gate persetujuan slide (`test_slide_generator_preview_approval`) gagal dengan `AttributeError` karena mencoba melakukan patch pada `"tools.slide_generator.check_permission_sync"`, padahal fungsi tersebut diimpor dari dalam fungsi lokal `_run` di modul tujuan (bukan level modul).
* **Dampak**:
  Unit test crash dan memicu kegagalan eksekusi test suite.
* **Solusi / Tindakan Pencegahan**:
  Arahkan target `patch` langsung ke modul asli tempat fungsi dideklarasikan (`core.permission_gate.check_permission_sync`), sehingga mock akan aktif secara global bagi pemanggilan di dalam fungsi internal mana pun.

---

## 📌 Log 5: Kegagalan Unduhan Media Threads API Akibat Routing Cloudflare Tunnel (400 Bad Request)

* **Tanggal**: 5 Juni 2026
* **Jenis**: Infrastructure / Cloudflare Tunnel Routing Error
* **Deskripsi Masalah**:
  Autoposting gambar ke Threads API gagal dengan error `400 Bad Request` (`Media download failed. Media URI does not meet requirements`). Investigasi menunjukkan bahwa Cloudflare quick tunnel (`trycloudflare.com`) secara default memuat file konfigurasi named tunnel lokal (`~/.cloudflared/config.yml`) yang memiliki aturan catch-all `404` untuk domain lain. Akibatnya, request dari Threads API ke public URL gambar diblokir dan menerima HTTP 404/400.
* **Dampak**:
  Semua postingan otomatis Threads yang menyertakan gambar gagal dipublikasikan.
* **Solusi / Tindakan Pencegahan**:
  1. **Bypass Konfigurasi Lokal**: Tambahkan argumen `--config /dev/null` pada pemanggilan `cloudflared` di [ecosystem.config.js](file:///wsl$/Ubuntu/home/bima_lucian/BIMA_CORE/ecosystem.config.js) agar berjalan sebagai quick tunnel murni tanpa memuat konfigurasi lokal.
  2. **Gunakan IPv4 Loopback**: Ubah target URL tunnel dari `http://localhost:8000` menjadi `http://127.0.0.1:8000` untuk menghindari isu resolusi DNS ke IPv6 (`::1`) di dalam lingkungan WSL.
  3. **Refresh PM2 Service**: Lakukan `pm2 delete bima-tunnel` dan `pm2 start ecosystem.config.js --only bima-tunnel` untuk menerapkan perubahan konfigurasi.

---

## 📌 Log 6: ModuleNotFoundError saat Auto-Collection Pytest di Root Directory

* **Tanggal**: 6 Juni 2026
* **Jenis**: Test Configuration / Path Resolution Error
* **Deskripsi Masalah**:
  Menjalankan perintah `pytest` secara langsung dari root directory `/home/bima_lucian/BIMA_CORE` memicu crash saat tahap collection. Pytest mendeteksi unit test di dalam nested sub-repository standalone `tools/last30days-skill/tests` dan mencoba mengimpor `tests.conftest`, yang menyebabkan `ModuleNotFoundError: No module named 'tests.conftest'`.
* **Dampak**:
  Perintah pengetesan global `pytest` crash total sebelum sempat menjalankan test case apa pun.
* **Solusi / Tindakan Pencegahan**:
  1. Buat file konfigurasi [pytest.ini](file:///Z:/home/bima_lucian/BIMA_CORE/pytest.ini) di root directory.
  2. Tambahkan aturan `norecursedirs = tools/last30days-skill bima_env .git` agar pytest melewati scanning folder virtual environment dan sub-repository standalone eksternal.

---

## 📌 Log 7: Redundant LLM API Call (Double-Processing) pada Alur Revisi Postingan Threads

* **Tanggal**: 6 Juni 2026
* **Jenis**: Logic Design / Performance Oversight
* **Deskripsi Masalah**:
  Pada alur revisi postingan Threads, teks draf yang direvisi oleh pengguna telah diproses secara cerdas menggunakan `apply_smart_revision` di modul listener Discord (`core/discord_bot.py`) sebelum disimpan ke `_revised_texts`. Namun, handler utama di `core/threads_commands.py` memproses ulang teks tersebut menggunakan `apply_smart_revision` untuk kedua kalinya saat mengambilnya dari `_revised_texts`.
* **Dampak**:
  Menyebabkan pemborosan token/biaya LLM API call (Claude 3.5 Sonnet), meningkatkan latency publikasi postingan, serta meningkatkan resiko perubahan format/halusinasi teks oleh LLM pada pemrosesan ulang yang tidak perlu.
* **Solusi / Tindakan Pencegahan**:
  1. Hapus pemanggilan `apply_smart_revision` kedua pada call-site di `core/threads_commands.py`.
  2. Gunakan penetapan nilai langsung `final_text = revised if revised else draft_text` karena teks di dalam `_revised_texts` sudah dipastikan telah melalui pemrosesan revisi yang valid.

---

## 📌 Log 8: Tiga Peningkatan Admin Tool (`teams/t4_admin.py`)

* **Tanggal**: 6 Juni 2026
* **Jenis**: Feature Enhancement / Defensive Coding
* **Deskripsi Masalah**:
  1. **Footer PDF muncul di halaman cover**: `BimaFPDF.footer()` merender nomor halaman dan author label di halaman 1 (cover page), mengotori layout cover yang seharusnya bersih.
  2. **DataAnalysisTool gagal menemukan file**: Ketika LLM agent menyebutkan path relatif yang tidak tepat (misalnya `data.csv` tanpa prefix `outputs/`), tool langsung return `FAILED` meskipun file sebenarnya ada di direktori `outputs/`.
  3. **ExcelGeneratorTool tidak mendukung chart**: Tidak ada mekanisme untuk menyisipkan grafik visual ke dalam file Excel yang dihasilkan, meskipun `WordGeneratorTool` dan `PDFGeneratorTool` sudah mendukung field `charts`.
* **Dampak**:
  1. Cover page PDF terlihat tidak profesional karena ada teks footer yang seharusnya hanya muncul di halaman isi.
  2. Analisis data gagal secara intermittent karena path resolution yang terlalu strict.
  3. Dokumen Excel yang dihasilkan kurang informatif dibandingkan output Word/PDF karena tidak ada visualisasi chart.
* **Solusi / Tindakan Pencegahan**:
  1. Tambahkan guard `if self.page_no() <= 1 and data.get("cover", True): return` di awal `BimaFPDF.footer()`.
  2. Tambahkan fallback `OUTPUT_DIR / Path(filepath).name` di `DataAnalysisTool._run()` sebelum mengembalikan error "file tidak ditemukan".
  3. Tambahkan parsing field `charts` di `ExcelGeneratorTool._run()` baik di tingkat sheet maupun tingkat dokumen, render via `_render_chart()`, dan tempel ke worksheet menggunakan `openpyxl.drawing.image.Image`.

---

## 📌 Log 9: Integrasi Sistem Anti-AI Slop (Stop-Slop) pada BIMA_CORE

* **Tanggal**: 7 Juni 2026
* **Jenis**: Text Quality / Prompt Engineering / Custom Tool
* **Deskripsi Masalah**:
  Hasil tulisan AI (baik postingan Threads, dokumen PDF/Word/Excel dari Admin Agent, maupun balasan chat dari Manager Agent) sering kali memiliki pola bahasa yang sangat terstruktur, kaku, dan dipenuhi frasa klise robotik khas AI (seperti "di era digital", "solusi terbaik", "berkomitmen untuk", atau pembuka basa-basi seperti "Tentu saja," dan "Perlu dicatat bahwa").
* **Dampak**:
  Draf postingan Threads dan dokumen keluaran terkesan kurang alami, berulang-ulang, dan kurang mencerminkan gaya penulisan kasual yang santai mirip tulisan manusia asli.
* **Solusi / Tindakan Pencegahan**:
  1. Buat custom tool baru [DeslopTool](file:///Z:/home/bima_lucian/BIMA_CORE/tools/deslop_tool.py) di `tools/deslop_tool.py` untuk membersihkan *AI tells*, *throat-clearing*, kalimat pasif, kontras biner klise, serta slop lokal Bahasa Indonesia.
  2. Integrasikan aturan anti-slop langsung di dalam `apply_smart_revision` pada [threads_commands.py](file:///Z:/home/bima_lucian/BIMA_CORE/core/threads_commands.py).
  3. Sisipkan backstory `ATURAN ANTI-SLOP (WAJIB)` pada agen admin di [t4_admin.py](file:///Z:/home/bima_lucian/BIMA_CORE/teams/t4_admin.py) dan pada `manager_node` system prompt di [manager.py](file:///Z:/home/bima_lucian/BIMA_CORE/core/langgraph_nodes/manager.py).

---

## 📌 Log 10: Kendala Eksekusi & Pengujian CLI Python di Lingkungan Windows Host vs WSL

* **Tanggal**: 8 Juni 2026
* **Jenis**: Environment & CLI execution mismatch
* **Deskripsi Masalah**:
  1. Menjalankan perintah evaluasi AST (`python3 -c "import ast; ... "`) atau `healthcheck.py` langsung pada Windows Host memicu `UnicodeDecodeError` / `UnicodeEncodeError` karena encoding default Windows Console (`cp1252`) bentrok dengan karakter UTF-8 atau box drawing unicode.
  2. Library esensial (CrewAI, LangGraph, LanceDB, dll.) tidak terdeteksi (`ModuleNotFoundError`) karena semua dependensi ter-install di virtual environment Ubuntu WSL (`bima_env/`), bukan di python sistem Windows Host.
* **Dampak**:
  Pengetesan sintaksis, testing CLI, dan verifikasi script gagal total ketika dieksekusi langsung di command line Windows Host.
* **Solusi / Tindakan Pencegahan**:
  1. Selalu gunakan opsi `encoding='utf-8'` saat membaca berkas teks menggunakan python `open()`.
  2. Set environment variable `PYTHONIOENCODING=utf-8` jika script me-render karakter khusus unicode ke stdout.
  3. Eksekusi seluruh script pengetesan dan CLI di lingkungan WSL Ubuntu dengan memicu bash interaktif via binary `wsl` serta arahkan ke absolute path WSL:
     ```bash
     wsl bash -c "cd /home/bima_lucian/BIMA_CORE && source bima_env/bin/activate && python3 test_script.py"
     ```

---

## 📌 Log 11: Build Target Conflict pada Hatchling & Loop Redundansi WSL Interop

* **Tanggal**: 8 Juni 2026
* **Jenis**: Python Packaging Conflict & Redundant Shell Invocation
* **Deskripsi Masalah**:
  1. Saat menginstalasikan package `agent-reach` via pip, proses build wheel gagal dengan error `ValueError: A second file is being added to the wheel archive at the same path: agent_reach/guides/setup-exa.md`. Ini dikarenakan section `[tool.hatch.build.targets.wheel.force-include]` di `pyproject.toml` mencoba menyertakan direktori `guides`, `skill`, dan `scripts` secara paksa, padahal target `packages = ["agent_reach"]` sudah menyertakannya secara otomatis.
  2. Saat menjalankan pengujian CLI Twitter via Python `subprocess.run()`, pemanggilan command `wsl bash -c "..."` memicu `[Errno 2] No such file or directory: 'wsl'`. Hal ini terjadi karena Python backend (atau test script) dieksekusi di dalam WSL Ubuntu, sehingga mencoba memanggil binary Windows host (`wsl`) yang redundan dan tidak ada di path Linux.
* **Dampak**:
  1. Instalasi package `agent-reach` terhenti dan gagal dipasang pada virtual environment `bima_env`.
  2. Fallback pencarian Twitter langsung terpicu karena pemanggilan CLI dianggap error akibat binary `wsl` tidak ditemukan di Linux.
* **Solusi / Tindakan Pencegahan**:
  1. **Hatch Build Fix**: Lakukan kloning repository `agent-reach`, edit `pyproject.toml` dengan menonaktifkan/mengomentari bagian `force-include` yang redundan, lalu jalankan instalasi lokal `pip install .` dari direktori kloning tersebut.
  2. **Direct CLI Call inside WSL**: Karena Python backend sudah berjalan di dalam lingkungan WSL, panggil binary CLI (`twitter`, `rdt`, dll.) secara langsung menggunakan `shutil.which()` untuk mendeteksi binary di PATH virtual environment, tanpa membungkusnya lagi dengan `wsl bash -c`.
     ```python
     twitter_bin = shutil.which("twitter") or "twitter"
     cmd = [twitter_bin, "search", query, "-n", "10", "--json"]
     ```

---

## Log 12: Bot Threads Masih Pakai Claude Sonnet 4.6

* **Tanggal**: 1 Juli 2026
* **Jenis**: Model Configuration Drift
* **Deskripsi Masalah**:
  Bot Threads masih memakai `THREADS_LLM_MODEL=anthropic/claude-sonnet-4.6` di `.env`, dan fallback di `core/threads_commands.py` serta `AI_sosmed/core/threads_commands.py` juga masih mengarah ke Sonnet 4.6. Padahal Claude Sonnet 5 sudah tersedia di OpenRouter dengan slug `anthropic/claude-sonnet-5`.
* **Dampak**:
  Draf dan revisi Threads tidak memakai model Sonnet terbaru, sehingga kualitas output dan kemampuan instruksi tertinggal dari konfigurasi yang diminta.
* **Solusi / Tindakan Pencegahan**:
  1. Ubah `.env` menjadi `THREADS_LLM_MODEL=anthropic/claude-sonnet-5`.
  2. Samakan fallback di `core/threads_commands.py` dan `AI_sosmed/core/threads_commands.py` ke `anthropic/claude-sonnet-5`.
  3. Update `AI_sosmed/.env.example` agar setup baru langsung memakai Sonnet 5.

---

## Log 13: Embedder Lokal `all-MiniLM-L6-v2` Lemah untuk Semantik Bahasa Indonesia

* **Tanggal**: 9 Juli 2026
* **Jenis**: RAG Quality / Model Selection (data-backed)
* **Deskripsi Masalah**:
  Embedder lokal default untuk domain `arsip` (vault Obsidian + calon fitur dedup konten) adalah `sentence-transformers/all-MiniLM-L6-v2` yang English-centric. Benchmark pada teks Indonesia (12 pasang parafrase gaya post Threads + 15 fakta) menunjukkan MiniLM gagal untuk dedup semantik: **recall@1 hanya 38%**, margin rata-rata **negatif (−0.031)**, dan `cos_paraphrase (0.545) < cos_cross_topic (0.575)` — artinya post topik acak dinilai lebih mirip daripada parafrase sebenarnya.
* **Dampak**:
  Vault RAG dan fitur semantik apa pun (mis. "jangan ulang post" untuk Threads-memory) tidak reliable untuk konten Indonesia. Retrieval berbasis lexical-overlap (topic→context) masih 93% karena banyak overlap kata, jadi masalah tersembunyi sampai diuji pada kasus parafrase murni.
* **Solusi / Tindakan Pencegahan**:
  1. Ganti `local_model` domain `arsip` di [core/embedder.py](file:///z:/home/bima_lucian/BIMA_CORE/core/embedder.py) ke `Qwen/Qwen3-Embedding-0.6B` (multilingual, `local_dim` 384 → 1024). Domain `code` dibiarkan (di luar scope).
  2. Benchmark pembanding: `baai/bge-m3` (via path cloud OpenRouter yang sudah ada) = dedup 100%; `Qwen3-0.6B` lokal = dedup **96%**, margin **+0.132** (terbaik), retrieval 100% — kualitas kelas bge-m3 tapi lokal + gratis.
  3. Karena `index_vault()` mengecek skema via **kolom, bukan dim**, perubahan dim TIDAK terdeteksi otomatis. Wajib `db.drop_table("vault")` manual, lalu biarkan startup thread `_index_vault_safe` rebuild (897 chunk @ 1024). Verifikasi search end-to-end sebelum restart bot.
  4. Restart `anisa-v3` agar proses live memuat Qwen3. SentenceTransformer auto-pakai GPU (`cuda:0`) — penalti CPU (2 teks/s vs 138) tidak berlaku di produksi.

---

## Log 14: Download Model HF Besar Stall di WSL (Rate-limit Anonim + CDN Flaky)

* **Tanggal**: 9 Juli 2026
* **Jenis**: Environment / Network Download Reliability
* **Deskripsi Masalah**:
  Download `Qwen/Qwen3-Embedding-0.6B` (~1.2 GB `model.safetensors`) dari HF Hub berkali-kali stall di WSL. Dua akar masalah: (a) request **anonim** kena rate-limit HF (warning "You are sending unauthenticated requests to the HF Hub"), dan (b) koneksi ke CDN LFS HF intermittent/bursty — download sebentar lalu hang mid-stream tanpa error. `HF_HUB_DOWNLOAD_TIMEOUT` tidak memicu retry karena read-stall socket tidak ter-timeout.
* **Dampak**:
  Instalasi model lokal baru mandek berjam-jam; PyPI/pip normal (2.6 MB/s) jadi mengecoh (jaringan sehat, hanya CDN model HF yang bermasalah).
* **Solusi / Tindakan Pencegahan**:
  1. **Set HF token** dulu: `huggingface-cli login` atau simpan ke cache `~/.cache/huggingface/token` (JANGAN taruh di `.env`/repo). Menghapus rate-limit anonim.
  2. **Jalankan uninterrupted, JANGAN di-kill.** `snapshot_download` TIDAK resume bersih setelah proses di-kill — partial `.incomplete` malah di-reset ke ~15 MB tiap restart. Attempt yang dibiarkan utuh justru paling jauh (0→100% bursty). Watchdog/timeout-kill = kontraproduktif.
  3. `hf_transfer` (parallel chunks) MALAH lebih buruk di koneksi flaky ini (stall dini). Pakai plain single-stream (`HF_HUB_ENABLE_HF_TRANSFER=0`, `max_workers=1`).
  4. Monitor via ukuran folder `blobs/` per menit; sabar — bursty 15→149→561→896→100% dengan hang transient di antaranya adalah normal, bukan gagal.
