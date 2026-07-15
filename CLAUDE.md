# CLAUDE.md — OPERATING RULES

## 1. EXPLORE → PLAN → CODE → VERIFY

- EXPLORE: baca file terkait sebelum membuat klaim.
- PLAN: buat tepat satu PLAN Markdown dan tunggu satu persetujuan.
- CODE: setelah PLAN disetujui, langsung kerjakan tanpa PLAN atau approval gate baru.
- VERIFY: jalankan test/linter yang relevan dan laporkan hasil sebenarnya.
- Re-plan hanya jika Bima merevisi scope atau secara eksplisit meminta perubahan rencana.

## 2. CONTEXT BEFORE ASSUMPTION

- Jangan menebak isi file, signature fungsi, atau perilaku API; baca atau cari lebih dulu.
- Cari simbol yang belum dikenal sebelum mengasumsikan keberadaannya.
- Saat tidak yakin, katakan tidak tahu dan minta konteks.
- Sebelum mengulang command yang pernah gagal, cari masalah terkait di `error_solutions.md`.

## 3. MINIMAL DIFF

- Sentuh hanya file yang langsung dibutuhkan task.
- Jangan refactor, cleanup, atau formatting di luar scope.
- Ikuti style dan pola yang sudah ada.

## 4. DESTRUCTIVE ACTIONS REQUIRE APPROVAL

Minta persetujuan sebelum menghapus file/data, memasang atau mencopot dependency,
mengubah `.env`/settings/CI, menjalankan migration, `git reset --hard`, `rm -rf`,
atau operasi destruktif lain.

## 5. NEVER BYPASS SAFETY

- Jangan gunakan `--no-verify`, `--force`, atau melewati safety check.
- Jangan hapus test yang gagal untuk membuat verifikasi hijau.
- Jangan menyembunyikan error dengan `try/except: pass`.

## 6. HONEST REPORTING

- Laporkan apa yang berhasil, gagal, atau belum selesai secara faktual.
- Jangan membuat hasil test, commit, atau isi file palsu.
- Jika terblokir, hentikan dan laporkan buktinya.

## 7. THINK IN PRESENT TENSE

Sebelum mengubah kode, pastikan masalah nyata, perubahan terkecil, risiko, dan cara
verifikasinya sudah jelas.

## 8. OUTPUT DISCIPLINE

- Ringkasan akhir maksimal 5 baris.
- Tanpa pembuka, perayaan, atau teori panjang.
- Tulis output panjang ke file.

## Perintah Pengembangan (Development Commands)

Gunakan perintah-perintah berikut saat melakukan testing atau menjalankan program:

- **Aktifkan Virtual Environment**: `source bima_env/bin/activate` (WSL / Ubuntu)
- **Jalankan Aplikasi Utama (Bot & Dashboard)**: `bima_env/bin/python main.py`
- **Jalankan Semua Test**: `bima_env/bin/pytest`
- **Jalankan Test Spesifik**: `bima_env/bin/pytest tests/test_qc.py`
- **Instal Dependensi**: `bima_env/bin/pip install -r requirements.txt`

## Aturan Coding Proyek (Python Focused)

### 1. Desain & Struktur
- **Gunakan PEP 8**: Ikuti aturan PEP 8 secara ketat untuk penamaan dan format kode.
- **Type Annotations**: Semua fungsi dan method baru wajib memiliki *type annotation* untuk parameter dan return value (misal `def process_agent(name: str) -> dict:`).
- **Immutability**: Hindari mengubah data di tempat (in-place mutation). Gunakan immutable data structure seperti `NamedTuple` atau `dataclass(frozen=True)` di mana pun memungkinkan.
- **File Cohesion**: Pecah file besar (>800 baris) menjadi modul kecil yang memiliki satu tanggung jawab spesifik (Single Responsibility Principle).

### 2. Keamanan & Kredensial
- Selalu gunakan `python-dotenv` untuk memuat variabel lingkungan (.env).
- **Dilarang keras** menulis hardcoded token Discord, WhatsApp, API Key OpenAI, Sentry DSN, atau kredensial sensitif lainnya di dalam repositori kode.
- Bersihkan pesan error yang dikirim ke Discord/WhatsApp. Log detail error di file log lokal, jangan kirim trace internal teknis langsung ke chat.

### 3. Standar Pengujian (Testing)
- Selalu jalankan `pytest` sebelum melakukan commit.
- Jika membuat fitur baru atau memperbaiki bug, buatlah unit test padanan-nya di folder `tests/`.
