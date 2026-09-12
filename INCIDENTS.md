# Catatan Insiden Proyek: BIMA CORE Mobile (INCIDENTS.md)

Dokumen ini mencatat masalah teknis yang ditemukan selama pengembangan dan pengujian aplikasi BIMA CORE Mobile beserta akar masalah (*root cause*) dan cara pencegahannya.

---

## Indeks Insiden

| ID Insiden | Tanggal | Status | Ringkasan Masalah | Promosi ke DEV-INFRA? |
|---|---|---|---|---|
| INC-001 | 2026-09-13 | TERSURVEY | Kebutuhan izin akses berkas penuh di Android 11+ (Scoped Storage) | Tidak (Spesifik Android) |
| INC-002 | 2026-09-13 | TERSURVEY | Background process killing oleh baterai Android saat server berjalan lama | Tidak (Spesifik Android) |

---

## Rincian Insiden

### INC-001: Izin Akses Berkas di Android Modern
- **Gejala**: Aplikasi gagal membaca/menghapus berkas di luar folder aplikasi sendiri.
- **Akar Masalah**: Kebijakan *Scoped Storage* Android membatasi akses berkas global tanpa izin `MANAGE_EXTERNAL_STORAGE`.
- **Solusi/Mitigasi**: Mendaftarkan izin kelola semua berkas di `AndroidManifest.xml` dan membuat dialog permintaan izin yang jelas kepada pengguna.

### INC-002: Penghemat Baterai Mematikan Server Mini Latar Belakang
- **Gejala**: Server lokal 9-Router mati saat layar HP mati beberapa menit.
- **Akar Masalah**: Sistem Android menghentikan proses latar belakang (*Doze Mode*) untuk menghemat baterai.
- **Solusi/Mitigasi**: Menggunakan arsitektur *on-demand invocation* di mana router dibangun sebagai engine reaktif lokal yang siap dipanggil saat aplikasi aktif atau melalui *Foreground Service* dengan notifikasi ringan jika diperlukan.
