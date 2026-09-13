# Catatan Perubahan (CHANGELOG.md)

Seluruh perubahan penting pada proyek **BIMA CORE** dicatat di berkas ini.

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
