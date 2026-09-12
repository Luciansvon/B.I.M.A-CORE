# Catatan Perubahan (CHANGELOG.md)

Seluruh perubahan penting pada proyek **BIMA CORE** dicatat di berkas ini.

## [v1.0.2] - 2026-09-13
### Keamanan & Rilis
- Kredensial OpenRouter dan Gemini dipindahkan dari JSON plaintext ke penyimpanan terenkripsi AES-GCM berbasis Android Keystore.
- Dialog provider tidak lagi menampilkan atau memuat ulang kredensial mentah; input dimasking sebagai password.
- Memori lokal Android memakai `application.filesDir` dan backup aplikasi dinonaktifkan.
- Izin `MANAGE_EXTERNAL_STORAGE`, `READ_EXTERNAL_STORAGE`, dan `WRITE_EXTERNAL_STORAGE` dihapus; cleartext HTTP juga dinonaktifkan.
- File manager tidak lagi menimpa destination secara diam-diam saat write/copy/move.
- Build Android memakai Android 16 stable (`compileSdk/targetSdk 36`).
- Pipeline release baru hanya mempublikasikan APK release yang ditandatangani dengan keystore persisten, diverifikasi `apksigner`, dan dilengkapi SHA-256.

### Fungsional
- OpenRouter dan Gemini kini memiliki jalur request online nyata; rute web memakai web grounding/search bila provider tersedia.
- Jalur sync laptop, bridge laptop, web/cuaca/pasar offline tidak lagi mengembalikan klaim sukses palsu ketika transport/data nyata belum tersedia.
- Tombol ringkasan memori tidak lagi menyimpan prompt pembacaan sebagai memo baru.
- Status latency router tidak lagi berisi angka acak yang menyerupai pengukuran nyata.

### Verifikasi
- CI Android menjalankan unit test, lint, dan assembly pada setiap push/PR.
- Workflow release menolak publikasi jika material signing production belum dikonfigurasi.

## [v1.0.0] - 2026-09-13
### Ditambahkan
- Modul aplikasi Android mandiri (`app/`) berbasis Kotlin & Jetpack Compose Material 3.
- Server lokal mini **9-Router Engine** yang tertanam langsung di HP (9 rute agen spesialis).
- Antarmuka **Chat-First** bersih dengan bilah samping (*Sidebar Navigation Drawer*).
- Gerbang keamanan berkas (**User Safety Gate**) untuk mencegah penghapusan berkas tanpa persetujuan pengguna.
- Pengelola berkas HP (**FileManager**) untuk baca, salin, pindah, dan bersihkan berkas.
- Penyimpan memori jangka panjang (**MemoryStore**) dan adapter sinkronisasi awan (**CloudSyncAdapter**).
- Pengujian otomatis unit test dengan tingkat kelulusan 100% (8/8 lulus).
- Berkas kompilasi paket instalasi APK: `bima-core-mobile-v1.0.0.apk` (18.7 MB).
- Dokumentasi arsitektur `ARCHITECTURE.md`, catatan insiden `INCIDENTS.md`, dan laporan bukti DEV-INFRA `.artifacts/result.json`.
