# Discord + WhatsApp Simple Progress Design

**Tujuan:** Menampilkan status sederhana selama Anisa bekerja di Discord dan WhatsApp tanpa menampilkan token mentah, reasoning internal, atau tag `[ROUTE: ...]`.

## Ruang Lingkup

- Discord mempertahankan pesan tunggu yang sudah ada dan status aktual dari `notify_progress()`.
- WhatsApp menambahkan satu pesan status sementara: `⏳ Anisa lagi baca dan proses permintaan...`.
- Pesan status WhatsApp diedit menjadi jawaban pertama, status voice, atau pesan error agar chat tidak dipenuhi pesan progress.
- Dashboard, routing LangGraph, prompt, dan protokol HTTP Python–Node tidak diubah.

## Alur

### Discord

1. `core/discord_bot.py` mengirim satu pesan tunggu.
2. Callback yang sudah ada mengedit pesan itu saat Manager atau tim spesialis mengirim status.
3. Token dari `manager_node` tetap diblokir supaya tag route internal tidak bocor.
4. Jawaban final menggantikan pesan tunggu yang sama.

### WhatsApp

1. Setelah pesan lolos autentikasi, rate limit, dan validasi input, bridge mengirim satu pesan status.
2. Indikator `typing` yang sudah ada tetap aktif selama request ke backend.
3. Untuk jawaban teks, pesan status diedit menjadi chunk jawaban pertama; chunk berikutnya dikirim seperti sekarang.
4. Untuk jawaban voice-only, pesan status diedit menjadi `🎤 Balasan suara siap.` sebelum audio dikirim.
5. Jika backend tidak memberi respons atau terjadi error, pesan status diedit menjadi pesan error; fallback ke reply baru hanya jika edit gagal.

## Batasan

- WhatsApp hanya menampilkan status umum, bukan nama tim LangGraph, karena endpoint `/chat` saat ini mengembalikan satu JSON setelah proses selesai.
- Tidak menambah SSE, WebSocket, polling, dependency, atau timer status palsu.
- Tidak membuka kembali live stream Manager.

## File

- Modify: `whatsapp/index.js` — siklus hidup satu pesan progress WhatsApp.
- Modify: `error_solutions.md` — catat regresi preview dan solusi minimal.
- Discord tidak perlu perubahan produksi karena mekanisme statusnya sudah tersedia.

## Verifikasi

- Jalankan `node --check whatsapp/index.js`.
- Jalankan focused test yang melindungi filter stream Manager.
- Restart `bima-whatsapp`, lalu cek log startup tanpa error.
- Smoke manual: kirim `/bot <pesan>` dan pastikan status muncul sekali lalu berubah menjadi jawaban.
- Smoke Discord: kirim satu perintah normal dan pastikan status Manager/tim tetap terlihat tanpa `[ROUTE: ...]`.
