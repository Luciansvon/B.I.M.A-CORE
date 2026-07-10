# Perbaikan Kebocoran Respon AI, Capping Token & Akselerasi Balasan Komentar Threads

Dokumen ini memetakan rencana untuk memperbaiki bug pada alur revisi Threads (kebocoran chat basa-basi AI), membatasi max_tokens untuk menghindari error kredit OpenRouter (402), serta meningkatkan kecepatan respons balasan komentar di Threads.

## User Review Required

> [!NOTE]
> - **Error Kredit OpenRouter (402)**: Saat memakai Claude 3.5 Sonnet, OpenRouter meminta alokasi kredit maksimal (default 65k token). Jika saldo menipis, request ditolak. Kami membatasi `max_tokens=1000` khusus untuk agen Threads karena draf postingan Threads tidak pernah melebihi 500 karakter.
> - **Interval Scan Komentar**: Saat ini, pemindaian komentar baru diatur **setiap 30 menit** di `core/threads_scheduler.py`. Kami meningkatkan kecepatannya menjadi **setiap 5 menit** agar Anisa membalas komentar jauh lebih cepat tanpa melanggar rate limit Threads API.
> - **Metode Ekstraksi Tag XML**: Kami mewajibkan LLM di `apply_smart_revision` membungkus draf final di dalam tag `<draft>...</draft>`. Kode python kemudian mengekstrak teks di dalam tag tersebut menggunakan regex. Metode ini sangat teruji untuk membuang obrolan basa-basi AI di luar draf.

## Proposed Changes

### Otomasi Threads & Konfigurasi LLM

#### [MODIFY] [llm_config.py](file:///z:/home/bima_lucian/BIMA_CORE/core/langgraph_nodes/llm_config.py)
- Modifikasi fungsi `get_langchain_llm` agar menerima parameter opsional `max_tokens: int | None = None`.
- Masukkan `max_tokens` ke dalam parameter inisialisasi `ChatOpenAI` jika ditentukan.

#### [MODIFY] [threads_commands.py](file:///z:/home/bima_lucian/BIMA_CORE/core/threads_commands.py)
- Batasi inisialisasi `threads_llm` dengan parameter `max_tokens=1000` untuk menghindari error pre-alokasi saldo kredit OpenRouter.
- Perbarui system prompt pada fungsi `apply_smart_revision` agar mewajibkan AI membungkus draf postingan final ke dalam tag `<draft>...</draft>`.
- Tambahkan logika pembersihan regex di `apply_smart_revision` untuk mengambil konten di dalam `<draft>...</draft>` jika terdeteksi, dengan fallback ke teks utuh jika tag tidak ditemukan.

#### [MODIFY] [threads_scheduler.py](file:///z:/home/bima_lucian/BIMA_CORE/core/threads_scheduler.py)
- Ubah interval pemicu `threads_comment_scan` dari `minute="*/30"` menjadi `minute="*/5"` (setiap 5 menit sekali) agar deteksi komentar lebih responsif.

---

## Verification Plan

### Automated Tests
1. Buat berkas tes unit/smoke baru di `tests/test_reviser.py` untuk menguji fungsi `apply_smart_revision` secara langsung dengan input feedback bervariasi (misal: Bima minta ganti kata, Bima langsung kirim teks final) dan verifikasi bahwa outputnya bersih tanpa basa-basi robotik, serta tidak memicu error 402.
2. Jalankan `wsl bash -c "cd /home/bima_lucian/BIMA_CORE && source bima_env/bin/activate && PYTHONPATH=. python3 tests/test_reviser.py"` di WSL.
3. Jalankan `healthcheck.py` di WSL untuk memastikan tidak ada error syntax baru.
