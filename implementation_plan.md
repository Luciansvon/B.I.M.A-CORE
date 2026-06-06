# BIMA_CORE Upgrade Plan

Dokumen ini memetakan rencana upgrade sistem multi-agent **B.I.M.A-CORE** ke iterasi berikutnya (Wave 3/4). Rencana ini disusun untuk meningkatkan kualitas pencarian (RAG), melengkapi visualisasi Pixel Dashboard, meningkatkan user experience suara pada WhatsApp, serta menambahkan kemampuan monitoring host secara otomatis.

## User Review Required

> [!IMPORTANT]
> - **Model / Embedder Upgrade**: Jika kita mengaktifkan RAG Hybrid atau model embedding cloud (`baai/bge-m3` untuk bahasa Indonesia), database vector `vault_index/` dan `repo_index/` yang lama harus dihapus terlebih dahulu agar skema dimensi data (384 -> 1024) tidak bentrok.
> - **WhatsApp Voice Notes Autostart**: Auto-transcribe WhatsApp voice note tanpa manual trigger `/bot stt` dapat meningkatkan beban LLM/STT. Direkomendasikan untuk membatasi whitelist auto-STT hanya untuk nomor handphone Bima.

## Open Questions

> [!IMPORTANT]
> - Apakah visualisasi Floor 2 (War Room) dan Floor 3 (Tower Roost) pada dashboard pixel art ingin dirancang dinamis berdasarkan data state agen yang sedang rapat (misalnya visual dan mekanik di war room jika statusnya "working" bersama)?
> - Apakah model embedding ingin diganti ke `cloud` (`bge-m3` + `mistralai/codestral-embed`) demi akurasi pencarian bahasa Indonesia, atau tetap menggunakan `local` (`all-MiniLM-L6-v2`) untuk menghemat biaya/VRAM?

---

## Proposed Changes

Rencana upgrade dibagi menjadi 4 komponen utama:

### 1. RAG Hybrid Search Integration (BM25 + Vector)
Menggabungkan keunggulan semantic search (LanceDB vector) dan keyword search (BM25) untuk menangkap istilah teknis, nama fungsi, atau jargon spesifik.

#### [MODIFY] [t3_arsip.py](file:///wsl.localhost/Ubuntu/home/bima_lucian/BIMA_CORE/teams/t3_arsip.py)
- Integrasikan `core/bm25_index.py` untuk mengindeks dokumen vault secara paralel.
- Ubah pencarian di `search_vault` agar memanggil hasil pencarian BM25 dan Vector, lalu satukan dengan `hybrid_merge()` sebelum dikirim ke reranker.

#### [MODIFY] [repo_rag.py](file:///wsl.localhost/Ubuntu/home/bima_lucian/BIMA_CORE/tools/repo_rag.py)
- Integrasikan hybrid search agar pencarian kode sumber oleh agent **Kodok** lebih presisi saat mencari simbol atau syntax spesifik.

---

### 2. Live Pixel Dashboard V3 Wiring
Menghubungkan panel dashboard yang saat ini masih berupa data statis/placeholder ke data ril dari server.

#### [MODIFY] [dashboard_server.py](file:///wsl.localhost/Ubuntu/home/bima_lucian/BIMA_CORE/core/dashboard_server.py)
- Tambahkan endpoint `GET /api/outputs` untuk mengambil daftar berkas terbaru dari folder `outputs/` (disortir berdasarkan waktu pembuatan).
- Tambahkan endpoint `GET /api/memory` untuk mengembalikan statistik memori (jumlah fakta unik di database, total sesi, dll).

#### [MODIFY] [guild-panels.jsx](file:///wsl.localhost/Ubuntu/home/bima_lucian/BIMA_CORE/dashboard/guild-panels.jsx)
- Ubah `InventoryPanel` untuk mengambil data secara dinamis dari `/api/outputs`.
- Ubah `VaultPanel` untuk mengambil data secara dinamis dari `/api/memory`.

---

### 3. WhatsApp Intelligent Voice Automation
Membuat bot lebih responsif terhadap pesan suara tanpa perlu mengaktifkan PTT manual.

#### [MODIFY] [index.js](file:///wsl.localhost/Ubuntu/home/bima_lucian/BIMA_CORE/whatsapp/index.js)
- Tambahkan logika *Auto-Arm* khusus jika pesan suara dikirim oleh nomor pemilik bot (`WA_OWNER_NUMBER`), sehingga voice note dari Bima langsung ditranskripsi otomatis tanpa perlu mengetik `/bot stt`.

---

### 4. Observability & Automatic Alerts
Menambahkan pengawasan proaktif agar Bima tahu kondisi server/host secara *realtime* tanpa perlu mengetik `!status`.

#### [NEW] [observability_scheduler.py](file:///wsl.localhost/Ubuntu/home/bima_lucian/BIMA_CORE/core/observability_scheduler.py)
- Buat penjadwal latar belakang yang memonitor:
  - Penggunaan RAM & CPU (>90% memicu alert).
  - VRAM GPU (menggunakan nvidia-smi parser, penting karena F5-TTS boros VRAM).
  - Status proses PM2.
- Kirim pesan peringatan otomatis ke `BOT_STATUS_CHANNEL_ID` di Discord jika mendeteksi anomali.

---

## Verification Plan

### Automated Tests
1. Jalankan `pytest tests/test_qc.py` untuk memastikan fungsionalitas inti tidak rusak.
2. Buat unit test baru di `tests/test_hybrid_rag.py` untuk menguji efektivitas pencarian keyword vs semantic.

### Manual Verification
1. Jalankan `python3 healthcheck.py` untuk memastikan seluruh struktur direktori dan impor baru tetap valid.
2. Buka dashboard pixel art di `/dashboard/v3` dan pastikan data di panel *Inventory* dan *Vault* ter-render secara langsung dari endpoint FastAPI.
3. Kirim voice note langsung di WhatsApp (dari nomor owner) dan pastikan bot langsung memprosesnya.
