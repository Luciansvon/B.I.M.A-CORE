# CLAUDE.md

Panduan ini membantu **Claude Code** memahami lingkungan pengembangan, perintah eksekusi, serta standar penulisan kode dalam proyek **BIMA_CORE**.

## Workflow Wajib

- Gunakan alur EXPLORE → PLAN → CODE → VERIFY.
- Setiap task hanya boleh memiliki satu PLAN Markdown dan satu approval gate.
- Setelah PLAN disetujui, langsung lanjut CODE dan VERIFY tanpa membuat PLAN baru.
- Re-plan hanya jika Bima merevisi scope atau secara eksplisit meminta perubahan rencana. Pertanyaan status/detail bukan permintaan re-plan.

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
