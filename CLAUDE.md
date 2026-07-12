# CLAUDE.md

Panduan ini membantu **Claude Code** memahami lingkungan pengembangan, alur kerja wajib, serta standar penulisan kode dalam proyek **BIMA_CORE**. File ini adalah **satu-satunya sumber aturan yang otomatis dibaca Claude Code** — jangan pecah aturan baru ke file lain (`Rules for agent.md`, `.clauderules`) tanpa menautkannya ke sini, biar gak drift lagi.

Untuk konteks arsitektur/stack/repo layout lengkap (dipakai juga oleh Codex/Cursor/tool lain), lihat [AGENTS.md](AGENTS.md).

## Perintah Pengembangan (Development Commands)

Gunakan perintah-perintah berikut saat melakukan testing atau menjalankan program:

- **Aktifkan Virtual Environment**: `source bima_env/bin/activate` (WSL / Ubuntu)
- **Jalankan Aplikasi Utama (Bot & Dashboard)**: `bima_env/bin/python main.py`
- **Jalankan Semua Test**: `bima_env/bin/pytest`
- **Jalankan Test Spesifik**: `bima_env/bin/pytest tests/test_qc.py`
- **Instal Dependensi**: `bima_env/bin/pip install -r requirements.txt`

## Alur Kerja Wajib (Operating Workflow)

### 1. EXPLORE → PLAN → CODE → VERIFY

Jangan pernah skip fase. Untuk setiap task:

- **EXPLORE**: Baca file terkait dulu. Sebutkan file apa saja yang dibaca dan kenapa.
- **PLAN**: Tulis rencana kerja + task list checklist dalam format markdown. Tunggu persetujuan Bima sebelum mulai coding (Single Gate Approval). Jika ada beberapa interpretasi task, sampaikan opsinya — jangan memilih sepihak. Jika ada pendekatan lebih sederhana, sampaikan alasannya.
- **CODE**: Eksekusi satu langkah pada satu waktu. Tulis kode seminimal mungkin yang menyelesaikan masalah — tidak ada fitur di luar permintaan, tidak ada abstraksi untuk kode yang cuma dipakai sekali.
- **VERIFY**: Jalankan test/linter. Kalau gagal, berhenti dan laporkan — jangan auto-patch tanpa konfirmasi.

Setelah plan disetujui, jangan tanya izin lagi untuk langkah lanjutan yang jelas-jelas mengikuti plan (mis. pre-warm model, restart service, smoke test). Simpan pertanyaan untuk: scope berubah, dependency baru, aksi destruktif, atau logika bisnis yang ambigu.

### 2. Context Before Assumption

- Jangan pernah menebak isi file, signature fungsi, atau perilaku API — baca atau grep dulu.
- Kalau ada simbol yang gak dikenal, cari di codebase dulu sebelum asumsi itu ada.
- Kalau butuh dokumentasi eksternal, minta URL ke Bima — jangan mengarang API.
- Kalau ragu, bilang "saya gak tahu" dan tanya. Percaya diri ≠ benar.

### 3. Minimal Diff / Surgical Changes

- Ubah HANYA file yang benar-benar dibutuhkan task.
- Tidak ada "sambil beresin ini juga", tidak ada refactor di luar permintaan, tidak ada perubahan format yang gak diminta.
- Pertahankan gaya kode, penamaan, dan pola yang sudah ada — ikuti konvensi existing, meskipun ada cara lain yang menurutmu lebih baik.
- Kalau menurutmu file lain juga perlu diubah, sebutkan dan tanya dulu.

### 4. Aksi Destruktif Wajib Izin

Selalu tanya dulu sebelum:

- Menghapus file, folder, branch, atau record database
- `git push --force`, `git reset --hard`, `rm -rf`, drop table
- Install/uninstall dependency
- Mengubah file config (`.env`, settings, CI/CD)
- Menjalankan migration atau apa pun yang menyentuh layanan eksternal

### 5. Jangan Pernah Bypass Safety

- Jangan pakai `--no-verify`, `--force`, atau skip pre-commit hook untuk "menyelesaikan" kegagalan.
- Jangan hapus test yang gagal supaya CI hijau — perbaiki root cause atau laporkan.
- Jangan silence error dengan `try/except: pass` kosong.

### 6. Honest Reporting

- Kalau task baru selesai sebagian, katakan persis apa yang selesai dan yang belum.
- Kalau ada yang gak jalan, bilang — jangan klaim sukses sebelum waktunya.
- Jangan mengarang hasil test, commit message, atau isi file.
- Kalau mentok, berhenti dan laporkan — jangan coba workaround kreatif tanpa konfirmasi.

### 7. Output Discipline

- Setelah setiap task: ringkas apa yang berubah, file mana, dan kenapa — maksimal 5 baris.
- Tanpa bahasa seremonial ("", "Perfect!", "Done!"). Fakta saja.
- Kalau output panjang, tulis ke file daripada dump ke chat.
- Gunakan markdown link `[file.py:42](file.py#L42)` untuk referensi kode.

### 8. Pencatatan Error & Solusi

Setelah task selesai, kalau ada kendala/error/penyesuaian teknis yang non-trivial, catat ke `error_solutions.md` dengan format:

- Deskripsi Masalah (Root Cause)
- Dampak terhadap sistem
- Solusi / Tindakan Pencegahan

## Aturan Coding Proyek (Python Focused)

### 1. Desain & Struktur

- **Gunakan PEP 8**: Ikuti aturan PEP 8 secara ketat untuk penamaan dan format kode.
- **Type Annotations**: Semua fungsi dan method baru wajib memiliki *type annotation* untuk parameter dan return value (misal `def process_agent(name: str) -> dict:`).
- **Immutability**: Hindari mengubah data di tempat (in-place mutation). Gunakan immutable data structure seperti `NamedTuple` atau `dataclass(frozen=True)` di mana pun memungkinkan.
- **File Cohesion**: Pecah file besar (>800 baris) menjadi modul kecil yang memiliki satu tanggung jawab spesifik (Single Responsibility Principle).

### 2. Keamanan & Kredensial

- Selalu gunakan `python-dotenv` untuk memuat variabel lingkungan (.env).
- **Dilarang keras** membaca/membuka file `.env` atau kredensial lain secara langsung kecuali diinstruksikan eksplisit oleh Bima.
- **Dilarang keras** menulis hardcoded token Discord, WhatsApp, API Key OpenAI, Sentry DSN, atau kredensial sensitif lainnya — di kode, dokumentasi, `error_solutions.md`, maupun output chat. Pakai `os.getenv` + `.env.example` sebagai placeholder.
- Pastikan `.env` selalu masuk `.gitignore`.
- Bersihkan pesan error yang dikirim ke Discord/WhatsApp. Log detail error di file log lokal, jangan kirim trace internal teknis langsung ke chat.
- Jangan melakukan HTTP request ke domain di luar yang sudah dipakai proyek (mis. `openrouter.ai`, `api.telegram.org`) tanpa izin eksplisit. Kalau ragu, tanyakan.

### 3. Standar Pengujian (Testing)

- Selalu jalankan `pytest` sebelum melakukan commit.
- Jika membuat fitur baru atau memperbaiki bug, buatlah unit test padanan-nya di folder `tests/`.
