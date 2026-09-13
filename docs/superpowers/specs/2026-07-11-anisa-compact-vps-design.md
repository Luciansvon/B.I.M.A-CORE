# Anisa Compact VPS Design

**Status:** Disimpan untuk dikerjakan saat anggaran tersedia. Tidak ada implementasi pada Juli 2026.

## Tujuan

Menjalankan Anisa 24/7 pada VPS bulanan Rp100.000-Rp150.000 dengan fitur inti tetap aktif, tanpa workload suara, browser automation, atau model GPU lokal.

## Target Infrastruktur

- Kandidat utama: Biznet Gio NEO Lite MS 4.2, 2 vCPU, RAM 4 GB, SSD 60 GB, Rp139.000/bulan.
- Sistem operasi: Ubuntu LTS.
- Swap: 4 GB sebagai pengaman, bukan memori kerja utama.
- LLM, vision umum, image generation, dan video generation tetap memakai API yang sudah dikonfigurasi.

## Fitur yang Dipertahankan

- Discord, WhatsApp, REST API, dashboard, LangGraph, dan seluruh specialist agent berbasis API.
- Threads bot lengkap: pencarian tren via Serper, pembuatan draf, preview DM, reaction gate, auto-post setelah timeout jika safety check aman, scan komentar, dan auto-reply komentar aman.
- Furniture QC, dokumen Word/PDF/Excel/PPT, saham, cutlist, vault, SQLite checkpoint, image/video generation via API, dan OCR lokal.
- OCR Anisa memakai EasyOCR CPU lokal. GPT, Claude, dan DeepSeek yang dipakai langsung oleh Bima berada di luar alur Anisa.

## Fitur yang Dimatikan

- STT/Whisper.
- TTS/F5-TTS/Edge-TTS.
- Browser automation dan Observer desktop.
- Workload GPU lokal dan reranker berat yang tidak dibutuhkan untuk jalur utama.

## Alur OCR

```text
!ocr + gambar -> direct pre-route -> EasyOCR CPU -> hasil teks
                                      |
                                      +-> reader dilepas setelah idle 10 menit
```

OCR tidak melewati LangGraph, CrewAI, atau vision API. Model dimuat hanya ketika `!ocr` dipakai agar RAM idle tetap rendah.

## Alur Threads yang Dipertahankan

```text
Draf -> DM Discord -> tunggu reaction 5 menit
  |         |               |
  |         |               +-> tidak ada reaction -> safety check
  |         +-> reject -> batal                    |-> aman: auto-post
  +-> approve -> post                              +-> sensitif: batal
```

Reaction gate tidak diubah. Penambahan berikutnya hanya membaca insight posting untuk evaluasi Anisa pada checkpoint 1 jam, 24 jam, dan 7 hari.

## Batasan

- EasyOCR pertama setelah reader dilepas akan lebih lambat karena cold start.
- WhatsApp tetap membutuhkan Chromium internal dari `whatsapp-web.js`; ini bukan browser automation Anisa.
- Harga API tidak termasuk biaya VPS.
- Threads learning saat ini baru belajar dari tren dan komentar; insight views/likes/reposts/quotes belum diambil oleh kode aktual.

## Rencana Terpisah

1. `docs/superpowers/plans/2026-07-11-anisa-compact-vps.md`
2. `docs/superpowers/plans/2026-07-11-threads-learning-loop.md`

