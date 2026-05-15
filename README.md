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
| 🔌 **MCP Integration** | Fetch, Markitdown, GitHub, SearXNG — tools eksternal yang pluggable |
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
Deployment       │ VPS (Ubuntu 22.04+)
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

B.I.M.A mendukung **Model Context Protocol (MCP)** untuk integrasi tools eksternal yang pluggable:

- **fetch** — Mengambil konten web
- **markitdown** — Konversi dokumen ke Markdown
- **memory** — Memori agen persisten
- **github** — Integrasi GitHub repository
- **searxng** — Search engine private

Tambah tool baru di `config_mcp.json`.

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
