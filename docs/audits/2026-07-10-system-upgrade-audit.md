# Audit Upgrade BIMA_CORE — 10 Juli 2026

## Ringkasan keputusan

Jangan upgrade semua paket dalam satu `bima_env`. Resolver membuktikan versi terbaru CrewAI, Browser Use, dan F5-TTS tidak bisa hidup bersama dalam satu environment. Prioritas pertama adalah memisahkan runtime dan mengunci versi; setelah itu baru upgrade framework.

```text
SEKARANG
anisa-v3 ── satu bima_env ── CrewAI + Browser + Voice + RAG
                              └─ dependency saling bentrok

TARGET
anisa-core-env     ── LangGraph + CrewAI + Discord/FastAPI
browser-env        ── Browser Use daemon/service
voice-env          ── F5-TTS worker
agentmemory        ── proses PM2 terpisah, versi dipin
MCP                ── versi dipin + tool allowlist
```

## Kondisi yang diverifikasi

- Git lokal sama dengan `origin/main` pada commit `17f22a9`.
- PM2: `anisa-v3`, `bima-whatsapp`, `bima-tunnel`, dan `anisa-status` online.
- Test: 207 lulus, 2 warning dependency.
- Mesin: RAM 11 GiB, GPU RTX 3050 Laptop 4 GiB. Penambahan service berat harus dibatasi.
- Semua model OpenRouter yang dikonfigurasi masih tersedia: DeepSeek V4 Flash, DeepSeek V4 Pro, dan Gemini 3.5 Flash.
- LangGraph 1.2.9, LangChain Core 1.4.9, LangChain OpenAI 1.3.4, LanceDB 0.34.0, OpenAI 2.45.0, FastAPI 0.139.0, Scrapling 0.4.10, yt-dlp 2026.7.4, dan yfinance 1.5.1 sudah versi terbaru saat audit.

## P0 — kerjakan sebelum menambah fitur

### 1. Pisahkan environment dan buat lockfile

**Masalah:** `requirements.txt` hampir seluruhnya tidak dipin. `pip check` menemukan 9 konflik versi laten. Dry-run versi terbaru juga gagal:

- CrewAI 1.15.2 meminta `openai>=2.30,<3`.
- Browser Use 0.13.3 mengunci `openai==2.16.0`.
- Browser Use meminta `rich>=14`, sementara rantai F5-TTS → `cached-path` meminta `rich<14`.
- F5-TTS dan `cached-path` juga bertabrakan pada batas versi `tqdm`.
- Runtime memasang `torch 2.13.0`, sedangkan metadata `torchvision 0.27.0` meminta `torch==2.12.0`.

**Solusi:** gunakan [uv 0.11.28](https://github.com/astral-sh/uv/releases/tag/0.11.28) yang sudah ada, lalu pecah dependency menjadi `core`, `browser`, dan `voice`, masing-masing dengan lockfile. CI wajib memakai mode frozen/locked.

**Dampak:** rebuild menjadi konsisten dan upgrade satu subsistem tidak merusak subsistem lain.

### 2. Stabilkan AgentMemory

**Masalah:** port 3111 mati. Launcher menulis “spawn berhasil”, tetapi log berulang menunjukkan cache `npx` gagal rename dengan `ENOTEMPTY`. Akibatnya semantic recall diam-diam jatuh ke fallback SQLite.

**Solusi:** pasang/pin `@agentmemory/agentmemory@0.9.27` sekali, jalankan sebagai proses PM2 terpisah, tambahkan readiness gate `/agentmemory/health`, dan hentikan penggunaan `npx -y` saat setiap boot. Rilis [AgentMemory v0.9.27](https://github.com/rohitg00/agentmemory/releases/tag/v0.9.27) juga memperbaiki kebocoran isolasi antar-agent dan kehilangan data saat stop/restart.

**Catatan:** upstream masih meminta iii-engine 0.11.2; jangan naik ke iii 0.11.6 sebelum AgentMemory menyelesaikan migrasi sandbox.

### 3. Amankan dan pin MCP

**Masalah:** semua server `npx`/`uvx` mengambil versi tanpa pin. Upstream menjelaskan server referensi MCP bukan solusi production-ready. `mcp-server-sqlite` yang aktif sudah diarsipkan dan tidak mendapat security update. Server itu memberi tool tulis database ke agen.

**Solusi:**

1. Pin setiap MCP ke versi yang diaudit.
2. Nonaktifkan `mcp-server-sqlite`; ganti dengan fungsi SQLite internal yang query-nya dibatasi.
3. Gunakan allowlist tool per agen; jangan injeksikan seluruh tool write/delete.
4. Tambahkan `kodok` ke registry agen karena Git MCP saat ini gagal diinjeksi.
5. Pertimbangkan pilot [ToolHive v0.34.0](https://github.com/stacklok/toolhive/releases/tag/v0.34.0) hanya untuk MCP berisiko tinggi. ToolHive memberi isolasi container, policy, audit log, dan penyaringan tool, tetapi menambah Docker/overhead.

Sumber: [MCP reference servers](https://github.com/modelcontextprotocol/servers), [MCP archived servers](https://github.com/modelcontextprotocol/servers-archived).

### 4. Perbaiki warning runtime yang sudah aktif

- `kodok` tidak ada di `_AGENT_REGISTRY`, sehingga 12 Git MCP tools dibuang saat startup.
- LanceDB dibuka pada import sebelum subprocess MCP dibuat; log memperingatkan kemungkinan deadlock setelah fork. Ubah koneksi menjadi lazy setelah proses utama siap.
- APScheduler berulang kali terlambat 23–77 detik. Profil event-loop/GIL dengan `pyinstrument` yang sudah terpasang; jangan menambah profiler baru dulu.
- Dashboard menulis 8 karakter awal API token ke log. Log cukup menyatakan token tersedia tanpa menampilkan bagian token.
- `audioop` akan hilang di Python 3.13. Tetap di Python 3.12 sampai jalur Discord voice diverifikasi dengan pengganti yang didukung.

### 5. Pulihkan gate CI/security

**Masalah:** `requirements-dev.txt` mendeklarasikan Ruff dan pip-audit, tetapi keduanya tidak terpasang di `bima_env`. `uv audit` juga tidak bisa berjalan karena repo belum punya `pyproject.toml`. CI menginstal dependency tanpa lockfile sehingga hasil build bisa berubah setiap hari.

**Solusi:** tambahkan project metadata + lockfile, jalankan `uv sync --frozen`, `ruff`, test, `uv audit`/`pip-audit`, dan `uv pip check` di CI.

## P1 — upgrade setelah P0 selesai

| Sistem | Sekarang | Terbaru | Keputusan |
|---|---:|---:|---|
| CrewAI | 1.6.1 | [1.15.2](https://github.com/crewAIInc/crewAI/releases/tag/1.15.2) | Upgrade di `core-env`; lakukan bertahap karena sembilan minor release dan AgentExecutor baru menjadi default. API `MCPServerAdapter` yang dipakai BIMA masih tersedia. |
| CrewAI Tools | 1.6.1 | 1.15.2 | Ikuti versi CrewAI yang sama. Jangan upgrade terpisah. |
| Browser Use | 0.11.13 | [0.13.3](https://github.com/browser-use/browser-use/releases/tag/0.13.3) | Upgrade hanya di `browser-env`. Versi 0.12.7 membawa hardening token, redaction, path containment, dan timeout action; 0.13.3 membawa CLI 3.0/Browser Harness. Wrapper lokal perlu compatibility test. |
| F5-TTS | 1.1.20 | 1.1.21 | Upgrade rendah risiko setelah `voice-env` terpisah. |
| AgentMemory | proses gagal | [0.9.27](https://github.com/rohitg00/agentmemory/releases/tag/v0.9.27) | Pin dan jadikan proses PM2 terpisah. |

## P2 — repo baru yang layak diuji

### Docling MCP

[Docling 2.111.0](https://github.com/docling-project/docling/releases/tag/v2.111.0) memahami layout PDF, tabel, reading order, formula, chart, OCR, email, dan format dokumen lain. [Docling MCP 2.0.1](https://github.com/docling-project/docling-mcp) punya mode remote ringan sekitar 50 MB dan mode lokal penuh.

**Cocok untuk:** katalog furnitur, gambar kerja PDF, tabel spesifikasi, dan dokumen scan yang gagal dipertahankan strukturnya oleh MarkItDown.

**Cara pakai:** jadikan fallback/replacement untuk dokumen kompleks, bukan menambah tool generik ke semua agen. Jalankan POC 20 dokumen dan bandingkan akurasi tabel, waktu, RAM, dan ukuran output.

### ToolHive

[ToolHive](https://github.com/stacklok/toolhive) cocok jika Bima ingin mempertahankan banyak MCP. Nilai utamanya adalah isolasi, policy, secrets, audit, dan pengurangan tool context. Karena sistem hanya 11 GiB RAM, mulai dari satu MCP berisiko; jangan migrasikan tujuh server sekaligus.

## P3 — pantau, jangan pasang sekarang

| Repo | Alasan ditunda |
|---|---|
| [Langfuse v3.212.0](https://github.com/langfuse/langfuse/releases/tag/v3.212.0) | Tracing/eval LLM berguna, tetapi self-host stack menambah service dan RAM. Optimalkan observability internal/Sentry dulu; gunakan cloud/OTel bila nanti butuh trace per-agent. |
| [Graphiti v0.29.2](https://github.com/getzep/graphiti/releases/tag/v0.29.2) | Temporal knowledge graph bagus, tetapi BIMA sudah punya AgentMemory graph + MCP Memory + LanceDB. Menambah Graphiti sekarang membuat memori keempat dan memperbesar sinkronisasi data. |
| Vector database/RAG baru | LanceDB, Qwen embedding, BM25, dan BGE reranker sudah aktif dan versinya baru. Perbaiki warning fork dan ukur retrieval sebelum mengganti database. |
| LangGraph baru | BIMA sudah memakai versi terbaru 1.2.9. Tidak ada upgrade yang diperlukan. |

## Urutan implementasi yang disarankan

1. **Branch A — dependency foundation:** `pyproject.toml`, tiga environment, lockfile, CI frozen.
2. **Branch B — runtime repair:** AgentMemory PM2, health alert, registry `kodok`, lazy LanceDB, sanitasi log.
3. **Branch C — framework:** CrewAI 1.15.2 pada core; Browser Use 0.13.3 pada service terpisah; F5-TTS 1.1.21 pada voice worker.
4. **Branch D — document POC:** Docling MCP versus MarkItDown pada dataset furnitur.
5. **Opsional:** ToolHive untuk satu MCP write-capable setelah benchmark RAM dan latency.

## Gate verifikasi tiap branch

- Resolver dan lockfile tidak berubah pada `uv sync --frozen`.
- `uv pip check` menghasilkan nol konflik.
- Full test minimal tetap 207 lulus.
- Import smoke untuk CrewAI, Browser Use, F5-TTS, Torch/Torchvision, LanceDB, dan Google SDK.
- AgentMemory health 200 dan proses tetap hidup setelah restart PM2.
- Tidak ada `kodok tidak dikenal`, warning fork LanceDB, token prefix, atau scheduler misfire baru di log.
- Smoke test Discord, WhatsApp `/bot ping`, browser interaktif, STT→TTS, arsip recall, dan satu query saham.

## Batas audit

Audit keamanan lengkap belum bisa dijalankan karena `pip-audit` tidak terpasang dan `uv audit` membutuhkan project metadata/lockfile. Temuan security di atas berasal dari resolver lokal, log runtime, serta release/security notice upstream; bukan pengganti full CVE scan setelah lockfile dibuat.
