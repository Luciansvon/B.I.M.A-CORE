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



