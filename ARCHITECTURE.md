# Arsitektur Proyek: BIMA CORE (Mobile Edition)

Dokumen ini menjelaskan arsitektur teknis aplikasi **BIMA CORE Mobile** yang dibangun mengikuti standar dan kontrak `B.I.M.A-DEV-INFRA`.

---

## 1. Identitas Proyek

- **Nama Proyek**: BIMA CORE Mobile (Anisa)
- **Repositori**: `Luciansvon/B.I.M.A-CORE`
- **Tipe Proyek**: Aplikasi Android Mandiri (Native Android APK)
- **Target Platform**: Android (API 26 hingga Android 14/15+)
- **Runtime / Toolchain Utama**:
  - Bahasa: Kotlin 2.x
  - Antarmuka: Jetpack Compose (Material 3)
  - Toolchain: Gradle 8/9, JDK 17 (Microsoft Build of OpenJDK)
  - Android SDK Platform: 36 (Build Tools 35.0.0 / 36.0.0)

---

## 2. Gambaran Aliran Sistem (System Overview)

```text
[ Mas Bima (User) ]
       |
       v (Sentuhan Layar / Chat / Perintah Suara)
+-------------------------------------------------------------+
|                     BIMA CORE MOBILE                        |
|                                                             |
|  +-------------------------------------------------------+  |
|  |       TAMPILAN UTAMA: Chat-First + Bilah Samping      |  |
|  | - Layar Chat Bersih (Percakapan dengan Anisa)         |  |
|  | - Bilah Samping: Status 9-Router, Berkas, Sync, Memo  |  |
|  +---------------------------+---------------------------+  |
|                              |                              |
|                              v                              |
|  +-------------------------------------------------------+  |
|  |           SERVER LOKAL MINI: 9-ROUTER ENGINE          |  |
|  |  (Pengatur Rute Cerdas 9 Jalur Kemampuan Agen)        |  |
|  +----+------+------+------+------+------+------+----+---+  |
|       |      |      |      |      |      |      |    |      |
|      J1     J2     J3     J4     J5     J6     J7   J8     J9   |
+-------+------+------+------+------+------+------+----+------+
        |      |      |      |      |      |      |    |      |
        v      v      v      v      v      v      v    v      v
      Anisa  Berkas  Sync   Web   Rangkum Gaya   Seni Remote Pasar
     Manager HP Safe Cloud  Intel Catatan Hidup Desain Laptop Saham
               HP   Brankas                      Bridge  JSON
```

---

## 3. Komponen Utama (9-Router Routes)

| Jalur | Komponen / Rute | Tanggung Jawab | Teknologi |
|---|---|---|---|
| **Jalur 1** | **Anisa Lead Orchestrator** | Pengatur persona, percakapan santai, pemilahan maksud perintah pengguna. | Kotlin Coroutines, LLM Client (Gemini/OpenRouter) |
| **Jalur 2** | **Storage & File Gatekeeper** | Membaca, merapikan, menyalin, memindahkan, dan menghapus berkas di HP dengan dialog konfirmasi aman. | Android Storage Access Framework & Scoped Storage |
| **Jalur 3** | **Memory Sync Engine** | Menyimpan ingatan jangka panjang (fakta, preferensi) dan menyinkronkan ke brankas cloud online agar laptop dapat membaca data yang sama. | SQLite / Room Database + HTTP Sync Adapter |
| **Jalur 4** | **Intel Web Fetcher** | Menjawab pertanyaan yang membutuhkan data internet terbaru secara hemat data. | HTTP Client Ringan (OkHttp / Ktor) |
| **Jalur 5** | **Quick Note & Summarizer** | Mengubah ide kilat menjadi rangkuman terstruktur. | Local Note Storage |
| **Jalur 6** | **Lifestyle & Routine Tracker** | Pengingat rutinitas harian dan kondisi cuaca lokal. | Android WorkManager / AlarmManager |
| **Jalur 7** | **Creative Design Assistant** | Inspirasi ide desain dan visual tanpa beban render di HP. | Text-based Prompt Engine |
| **Jalur 8** | **Laptop Remote Bridge** | Mengirim tugas komputasi berat ke laptop saat laptop menyala. | Local Network / Webhook Bridge |
| **Jalur 9** | **Market Pulse Observer** | Ringkasan berita pasar dan saham tanpa beban pustaka grafik berat. | Lightweight JSON Parser |

---

## 4. Antarmuka Build, Uji, dan Rilis

- **Perintah Build APK**: `.\gradlew.bat assembleDebug`
- **Perintah Uji Unit (Unit Test)**: `.\gradlew.bat testDebugUnitTest`
- **Hasil Berkas APK**: `app\build\outputs\apk\debug\app-debug.apk`
- **Laporan Bukti Pengujian**: `app\build\reports\tests\testDebugUnitTest\index.html`

---

## 5. Batasan dan Keamanan (Constraints)

1. **Memori & Baterai HP**: Tidak ada proses komputasi AI model raksasa lokal di HP. Beban berat didelegasikan ke cloud atau laptop.
2. **Keamanan Berkas**: Setiap aksi penghapusan berkas fisik di HP wajib melalui gerbang konfirmasi pengguna (*User Safety Gate*) untuk mencegah kehilangan data tidak sengaja.
3. **Privasi**: Kunci API dan token kredensial disimpan di penyimpanan aman lokal HP (*EncryptedSharedPreferences*), tidak disimpan terbuka di kode publik.
