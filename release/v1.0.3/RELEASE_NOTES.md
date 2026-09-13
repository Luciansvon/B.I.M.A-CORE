# BIMA CORE Mobile v1.0.3 — Catatan Rilis

## Ringkasan Perubahan
Rilis versi **v1.0.3** mengubah identitas agen menjadi **Agent Harness mandiri di Android** yang sadar penuh akan akses berkas lokal HP Bima, memperbaiki pendeteksian perintah pembersihan sampah, dan menghapus seluruh panggilan 'Mas Bima'.

### Fitur & Perbaikan Utama
1. **Identitas Agent Harness Mandiri**:
   - Agen sadar bahwa ia beroperasi langsung di dalam smartphone Android Bima sebagai Agent Harness.
   - Memiliki akses nyata ke sistem penyimpanan lokal HP dan tidak lagi menolak/mengira dirinya bot web.

2. **Pendeteksian Perintah 'Bersihin Sampah'**:
   - Kata kunci baru: ersih, ersihin, sampah, storage, penyimpanan langsung memicu rute FILE_MANAGER.
   - Menampilkan kartu aksi persetujuan sebelum menghapus/merapikan berkas di HP.

3. **Penghapusan Panggilan 'Mas Bima'**:
   - Semua sapaan dan referensi kini menggunakan nama panggilan 'Bima' dengan gaya santai dan akrab.

4. **Verifikasi Kualitas**:
   - Unit tests: 8/8 PASS.
   - Emulator MuMu: Tes pembersihan sampah & kartu aksi sukses terverifikasi.
   - Obrolan Agent Harness: Berhasil menjawab dengan identitas harness Android.

## Berkas Artefak
- **Nama APK**: bima-core-mobile-v1.0.3.apk
- **Ukuran**: 18.8 MB
- **SHA-256**: 
E11E073C5B412ACDF8F74B27F309B9E33C2B8971A97BC296BAD6E4AB6BC34BB2
