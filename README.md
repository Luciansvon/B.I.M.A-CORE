<div align="center">

# ⚔️ B.I.M.A-CORE

### *Built Intelligence for Multi-Agent Automation*

**ANISA** — Artificial Neural Intelligence System Assistant

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-FF6B35?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![Discord](https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-Dashboard-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PM2](https://img.shields.io/badge/PM2-Production-2B037A?style=for-the-badge&logo=pm2&logoColor=white)](https://pm2.keymetrics.io)

*Sistem multi-agent AI berbasis LangGraph yang mengorkestrasi 10 agen spesialis untuk menjadi asisten pribadi cerdas di Discord, WhatsApp, dan Web.*

</div>

---

## 📖 Tentang Proyek

**B.I.M.A-CORE** adalah inti dari sistem AI asisten bernama **ANISA**. Menggunakan **LangGraph state machine**, setiap pesan pengguna dianalisis oleh intent classifier, lalu diteruskan ke agen spesialis yang paling tepat — mulai dari riset web, analisis saham, debugging kode, hingga pembuatan konten kreatif.

```
Pengguna → Discord / WhatsApp / Web
                ↓
        Intent Classifier
                ↓
    ┌───────────┴───────────┐
    │   LangGraph Engine    │
    │  (State Machine)      │
    └───────────┬───────────┘
                ↓
   ┌────────────────────────┐
   │  10 Specialized Agents │
   │  + MCP Tool Registry   │
   └────────────────────────┘
                ↓
       Memory + Response
```

---

## ✨ Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| 🧠 **Multi-Agent Orchestration** | LangGraph routing otomatis ke agen yang paling relevan |
| 🔌 **MCP Integration** | Fetch, Markitdown, Time, DuckDuckGo, Playwright, Git, SQLite, Filesystem — tools eksternal yang pluggable |
| 💾 **Memori Jangka Panjang** | Vector store (LanceDB) + SQLite untuk konteks percakapan persisten |
| 📊 **Real-Time Dashboard** | Guild hall pixel art (React + WebSocket) untuk visualisasi aktivitas |
| 📄 **Document Processing** | PDF, Word, Excel, PowerPoint — baca, analisis, dan generate |
| 🌐 **Web Intelligence** | Scraping marketplace, riset web, browser automation interaktif |
| 📈 **Stock Market** | Data saham real-time, portfolio tracking, chart otomatis |
| 📱 **Multi-Channel** | Discord, WhatsApp, REST API — semua dalam satu sistem |
| 💰 **Cost-Optimized** | Dynamic model selection (DeepSeek, Gemini, Llama) via OpenRouter |
| 🗂️ **Obsidian Vault** | Integrasi knowledge management dan pengarsipan dokumen |

---

## 🧑‍🤝‍🧑 Roster Agen

> Setiap agen memiliki kepribadian, tools, dan model LLM yang berbeda-beda.

| Agen | Peran | Keahlian Utama |
|------|-------|----------------|
| 🎯 **Manager** | Koordinator & Router | Memahami konteks, mendistribusikan tugas, merangkum hasil |
| 👁️ **Visual** | Analis Visual | Analisis gambar, OCR, membaca PDF visual (Gemini Vision) |
| 🗂️ **Arsip** | Pustakawan Digital | Pengarsipan dokumen, knowledge vault, Obsidian integration |
| ⚙️ **Admin** | Administrator Sistem | Manajemen file, task system, delegasi internal |
| 🔍 **Intel** | Agen Intelijen | Riset web, scraping marketplace, browser automation |
| 🌿 **Lifestyle** | Konsultan Gaya Hidup | Rekomendasi, saran hidup, pertanyaan sehari-hari |
| 🎨 **Seniman** | Kreator Konten | Penulisan kreatif, desain konsep, konten visual |
| 🔧 **Mekanik** | Engineer & Debugger | Coding, debugging, review kode, problem teknikal |
| 📈 **Saham** | Analis Pasar | Analisis saham, portofolio, jadwal update otomatis |
| 🐸 **Kodok** | Hiburan & Sosial | Humor, percakapan santai, meme |

---

## 🛠️ Tech Stack

```
Backend          │ Python 3.10+, FastAPI, Uvicorn
Orchestration    │ LangGraph, LangChain
Agent Framework  │ CrewAI
LLM Provider     │ OpenRouter (DeepSeek v4, Gemini 2.0, Llama 3.3)
Communication    │ Discord.py, WhatsApp-web.js (Node.js bridge)
Dashboard        │ React JSX (pixel art), WebSocket
Desktop App      │ Tauri 2.x (sidebar ANISA)
Vector Store     │ LanceDB + sentence-transformers
Database         │ SQLite (memori agen)
Browser Auto     │ browser-use >= 0.1.40
Task Scheduler   │ APScheduler
Process Manager  │ PM2 + Cloudflare Tunnel
Deployment       │ WSL Ubuntu 22.04+ (local PC) atau VPS Linux
```

---

## 🚀 Instalasi

### Prasyarat

- Python 3.10+
- Node.js 20+
- Chromium (untuk browser automation)
- PM2 (untuk production)

### 1. Clone & Setup Environment

```bash
git clone https://github.com/Luciansvon/B.I.M.A-CORE.git
cd B.I.M.A-CORE

# Buat virtual environment
python3 -m venv bima_env
source bima_env/bin/activate        # Linux/Mac
# atau: bima_env\Scripts\activate   # Windows
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Konfigurasi Environment

```bash
cp .env.example .env
```

Edit `.env` dengan API key kamu:

```env
# ─── WAJIB ───────────────────────────────────────
OPENROUTER_API_KEY=sk-or-v1-...
DISCORD_TOKEN=your-discord-bot-token

# ─── OPSIONAL ────────────────────────────────────
GEMINI_API_KEY=...
SERPER_API_KEY=...
TAVILY_API_KEY=...
RAPIDAPI_KEY=...

# ─── KONFIGURASI BOT ─────────────────────────────
LLM_PROVIDER=openrouter
EMBEDDING_PROVIDER=huggingface
OBSIDIAN_PATH=./Bima_Vault
DASHBOARD_PORT=8000
DASHBOARD_API_TOKEN=your-secret-token

# ─── CHANNEL DISCORD ─────────────────────────────
BOT_STATUS_CHANNEL_ID=...
SAHAM_CHANNEL_ID=...

# ─── WHATSAPP (OPSIONAL) ─────────────────────────
WA_OWNER_NUMBER=628xxxxxxxxxx
WA_BRIDGE_URL=http://127.0.0.1:8001
```

### 4. Jalankan

```bash
# Development (lokal)
python main.py

# Health check
python healthcheck.py
```

---

## 🖥️ Production Deployment (PM2)

```bash
# Install PM2 & Node.js
npm install -g pm2

# Start semua service
pm2 start ecosystem.config.js

# Simpan config & enable autostart
pm2 save
pm2 startup

# Monitor
pm2 logs anisa-v3
pm2 status
```

PM2 akan menjalankan 3 proses sekaligus:

| Proses | Deskripsi |
|--------|-----------|
| `anisa-v3` | Main bot (Python) |
| `bima-tunnel` | Cloudflare Tunnel |
| `bima-whatsapp` | WhatsApp bridge (Node.js) |

### Auto-start saat Windows login (WSL setup)

Kalau lo run BIMA_CORE di WSL Ubuntu (bukan VPS Linux native), butuh 2 layer biar bot otomatis nyala saat Windows login:

**Layer 1 — Pastikan systemd aktif di WSL** (`/etc/wsl.conf`):

```ini
[boot]
systemd=true

[user]
default=bima_lucian
```

Restart WSL setelah edit: `wsl --shutdown` (dari PowerShell Windows) → wait → `wsl -d Ubuntu`.

**Layer 2 — PM2 systemd unit (jalanin di WSL Ubuntu):**

```bash
# Generate + install systemd service (sekali aja)
sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u bima_lucian --hp /home/bima_lucian

# Save current process list ke dump file
pm2 save

# Verify
systemctl status pm2-bima_lucian
```

**Layer 3 — Trigger WSL boot saat Windows login** (lewat Windows Task Scheduler):

```powershell
# Buat task — jalan saat user login
$action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-d Ubuntu --exec /bin/true"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "WSL-BIMA-Boot" -Action $action -Trigger $trigger -RunLevel Highest
```

Task ini cuma "membangunkan" WSL — begitu WSL hidup, systemd auto-start PM2, PM2 auto-resurrect proses dari dump file. Bot online tanpa manual launch.

---

## 🌐 PC/WSL vs VPS — kapan migrate?

Saat ini lo run di **WSL Ubuntu di PC** lo. Cukup buat development + casual use, tapi ada batasan:

| Aspek | WSL di PC (sekarang) | VPS Linux native |
|---|---|---|
| Uptime | Cuma saat PC nyala | 24/7 (~99.9% SLA) |
| Cost | $0 | $5-10/bulan (mis. Hetzner CX11, DigitalOcean droplet) |
| RAM | Share dgn Windows/game | Dedicated 2-8GB |
| Latency Discord | Tergantung internet rumah | Stable datacenter |
| Maintenance | Lo restart sendiri | Auto-update OS, snapshot, dll |
| Setup | Udah jalan | Migrate semua (10-30 menit pakai script `deploy_vps.sh`) |

**Indikator lo udah perlu migrate ke VPS:**
- Sering bot mati karena PC dimatikan / restart Windows
- Saham scheduler miss event krusial saat lo lagi tidur / kerja
- Bima yg join Discord 24/7 (community bot)

**Indikator masih cukup di PC:**
- Cuma lo + 1-2 user yg pake
- Use case furniture QC + casual chat
- Belum ada commitment 24/7 / SLA

Path migrasi: `deploy_vps.sh` udah ada di repo — jalanin di VPS Ubuntu kosong, otomatis clone repo + install deps + setup PM2 + cloudflare tunnel. Migrate ~30 menit.

---

## 📊 Dashboard

Akses dashboard real-time setelah bot berjalan:

| URL | Deskripsi |
|-----|-----------|
| `http://localhost:8000/dashboard` | Dashboard utama |
| `http://localhost:8000/dashboard/v3` | Pixel art guild hall |
| `http://localhost:8000/metrics` | Metrics API (JSON) |

Dashboard menampilkan aktivitas agen secara real-time menggunakan WebSocket — kamu bisa melihat agen mana yang sedang aktif, riwayat percakapan, dan status sistem.

---

## 📁 Struktur Proyek

```
B.I.M.A-CORE/
├── main.py                    # Entry point
├── config.py                  # LLM & model config
├── config_mcp.json            # MCP server config
├── requirements.txt
├── ecosystem.config.js        # PM2 config
│
├── core/                      # Engine utama
│   ├── discord_bot.py         # Discord bot
│   ├── langgraph_engine.py    # State machine orchestration
│   ├── langgraph_nodes/       # Node per agen
│   │   ├── state.py           # BimaState definition
│   │   ├── manager.py
│   │   ├── intel.py
│   │   ├── visual.py
│   │   ├── mekanik.py
│   │   └── ...
│   ├── dashboard_server.py    # FastAPI + WebSocket
│   ├── mcp_client_manager.py  # MCP integration
│   └── saham_*.py             # Modul saham
│
├── teams/                     # CrewAI agent definitions
├── tools/                     # Shared tools & plugins
│   ├── browser_use_tool.py    # Browser automation
│   ├── repo_rag.py            # Repository RAG
│   └── plugins/               # Plugin dinamis
│
├── dashboard/                 # Frontend pixel art (React JSX)
│   ├── guild.html
│   └── guild-*.jsx
│
└── frontend/                  # Desktop sidebar (Tauri)
```

---

## 🔌 MCP Tools

B.I.M.A mendukung **Model Context Protocol (MCP)** untuk integrasi tools eksternal yang pluggable. Tiap MCP di-attach ke agent tertentu via `attach_to` di `config_mcp.json`.

**Enabled by default:**

| MCP | Fungsi | Attached agent |
|-----|--------|----------------|
| `fetch` | Ambil konten web jadi text/markdown | intel |
| `markitdown` | Konversi PDF/DOCX/PPTX/XLSX ke Markdown | arsip, visual |
| `sequential_thinking` | Reasoning chain terstruktur | manager (Anisa) |
| `memory_anthropic` | Persistent KV memory cross-session | arsip, manager |
| `time` | Current time + timezone conversion | manager, saham, lifestyle |
| `duckduckgo` | Web search gratis tanpa API key | intel, kodok |
| `playwright` | Browser automation + screenshot | visual, intel, seniman |
| `git` | Log/blame/diff repo BIMA_CORE | mekanik, kodok |
| `sqlite` | Structured store untuk log Discord + jurnal saham | arsip, saham |
| `filesystem` | Read/write file di scope `outputs/` saja | intel, mekanik, visual, seniman |

**Disabled (config-only, butuh setup tambahan):**

- `github` — butuh `GITHUB_PERSONAL_ACCESS_TOKEN` di `.env`
- `searxng` — butuh `SEARXNG_URL` (instance public atau self-host) di `.env`

Tambah/edit tool di `config_mcp.json`. Restart bot supaya `MCPClientManager` reload config.

---

## 🛡️ Reliability & Observability

| Stack | Tujuan | Setup |
|---|---|---|
| `uvloop` | Drop-in asyncio 2-4× speedup | Aktif otomatis di [main.py](main.py) |
| `loguru` | Color/structured logging, replace stdlib | Aktif otomatis dgn stdlib intercept |
| `memray` | Memory profiler (manual run) | `memray run --live bima_env/bin/python main.py` |
| `pyinstrument` | CPU flamegraph profiler (manual run) | `pyinstrument bima_env/bin/python main.py` |
| `sentry-sdk` | Auto-capture crash + stack trace + breadcrumb | Set `SENTRY_DSN` di `.env` (free tier 5k events/bulan) |
| `apprise` | Multi-channel notify fallback (Telegram/ntfy/email/dll) | Set `APPRISE_URLS` di `.env` comma-separated |
| `psutil` | System metrics (CPU/RAM/disk) | Auto via `!status` Discord command |
| `stamina` | Retry decorator (jitter + exp backoff) | Wired di [core/embedder.py](core/embedder.py) + [core/furniture_qc.py](core/furniture_qc.py) hot path |
| `diskcache` | Persistent disk cache (TTL built-in) | Auto-pakai buat cloud embedding cache di [core/embedder.py](core/embedder.py) |

Tanpa setup `.env`, `sentry-sdk` + `apprise` jadi no-op (aman, ga error). Begitu `.env` di-isi, langsung aktif.

---

## 🧠 RAG Quality (Wave 3)

Embedding backend switchable lokal/cloud via env `EMBEDDING_BACKEND`:

| Backend | Model arsip | Model code (repo_rag) | Dim | RAM | Biaya |
|---|---|---|---|---|---|
| `local` (default) | `all-MiniLM-L6-v2` | `all-MiniLM-L6-v2` | 384 | ~2GB | $0 |
| `cloud` | `baai/bge-m3` | `mistralai/codestral-embed-2505` | 1024 | ~0 | ~$0.03/bulan |

**Switch ke cloud (untuk RAG Bahasa Indonesia lebih akurat):**

```bash
# 1. Set di .env
EMBEDDING_BACKEND=cloud
EMBED_CACHE_TTL_DAYS=30

# 2. Drop existing index (dim berubah 384→1024)
rm -rf vault_index/ repo_index/

# 3. Restart bot — index auto-rebuild pakai model baru
pm2 restart anisa-v3
```

**Hybrid search (BM25 + vector):** helper di [core/bm25_index.py](core/bm25_index.py) — `build_from_corpus()` + `BM25Index.search()` + `hybrid_merge()`. Belum di-wire ke arsip/repo_rag flow (opt-in pakai langsung kalau lo mau).

---

## 🛠️ Discord Commands

| Command | Fungsi |
|---|---|
| `!saham help` | List subcommand saham (digest, watchlist, ticker, chart, portfolio, override) |
| `!qc` + attachment PDF/PNG/JPG | **Furniture drawing QC** — review gambar kerja: dimensi, detail sambungan, view, BOM. Output: text report + markup PNG (overlay box berwarna di lokasi issue). Pakai Gemini Flash vision via OpenRouter. ⚠️ Test pakai project pribadi aja, JANGAN drawing client/perusahaan (data lewat cloud third-party). |
| `!ocr` + image attachment | OCR EasyOCR — extract text dari image (PNG/JPG/WEBP). Support Bahasa Indonesia + English. Lazy-load model ~80MB (first call lambat, selanjutnya cepet). |
| `!status` | Health snapshot host (PC/WSL atau VPS) — CPU/RAM/disk/load average/process count. Pakai psutil. |
| mention `@Anisa <pesan>` | General chat → LangGraph router otomatis ke agent yg paling relevan |

---

## 🤝 Cara Berkontribusi

1. Fork repo ini
2. Buat branch fitur: `git checkout -b fitur/nama-fitur`
3. Commit perubahanmu: `git commit -m 'feat: tambah fitur X'`
4. Push ke branch: `git push origin fitur/nama-fitur`
5. Buka Pull Request

---

## 📋 Lisensi

Proyek ini dikembangkan untuk penggunaan pribadi dan edukasi.

---

<div align="center">

*Dibangun dengan ❤️ menggunakan LangGraph, CrewAI, dan Python*

**ANISA** — *Your Intelligent Guild Commander*

</div>
