# Catatan Rilis BIMA CORE Mobile v1.0.1

Pembaruan **BIMA CORE Mobile v1.0.1** menambahkan menu pengaturan Kunci API langsung di dalam aplikasi HP serta penyempurnaan integrasi AI online. Pembaruan ini telah diuji secara langsung (*live test*) di emulator MuMu Player dan diverifikasi lulus 100%.

---

## 🌟 Pembaruan & Fitur Baru

### 1. Tombol & Kotak Pengaturan Kunci API
- Menambahkan menu **Kunci API** pada laci samping (*sidebar*) dengan ikon kunci emas.
- Menampilkan kotak dialog (*popup modal*) untuk memasukkan:
  - **OpenRouter API Key** (diawali `sk-or-v1-...`)
  - **Google Gemini API Key** (diawali `AIzaSy...`)
- Kunci API yang tersimpan otomatis dimuat kembali saat dialog dibuka, memudahkan pemeriksaan atau pembaruan.

### 2. Deteksi Cerdas Kunci API via Chat
- Mas Bima dapat menempelkan langsung teks kunci API ke dalam kolom obrolan chat.
- Sistem 9-Router akan otomatis mengenali kunci dan menyimpannya secara aman ke memori internal aplikasi tanpa perlu membuka menu pengaturan.

### 3. Pengujian Nyata di Emulator MuMu Player
- Terverifikasi berhasil dipasang dan dijalankan di emulator MuMu Player (Samsung Galaxy S23+ environment).
- Dialog pop-up responsif, pengisian form berhasil, dan notifikasi konfirmasi penyimpanan muncul dengan mulus.

---

## 📦 Berkas Instalasi (Assets)

- **Berkas APK**: `bima-core-mobile-v1.0.1.apk` (18.7 MB)
- **Checksum SHA-256**: `690D58BEEB266034EE23CBF19D4F8CD22F050D7E494969A2513F8D63DB9D7C10`
- **Kompatibilitas**: Android 8.0 Oreo (API 26) hingga Android 15 (API 35/36+)

---

## 🧪 Bukti Kepatuhan B.I.M.A-DEV-INFRA
- 8/8 Pengujian Unit Otomatis LULUS (100% PASS).
- Verifikasi visual dan interaksi GUI berhasil di MuMu Player.
- Hasil tervalidasi di `.artifacts/result.json`.
