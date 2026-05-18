<div align="center">

# ⚔️ B.I.M.A-CORE

### *Built Intelligence for Multi-Agent Automation*

**ANISA** — Artificial Neural Intelligence System Assistant

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-FF6B35?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![Discord](https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-Dashboard-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PM2](https://img.shields.io/badge/PM2-Production-2B037A?style=for-the-badge&logo=pm2&logoColor=white)](https://pm2.keymetrics.io)

*A LangGraph-based multi-agent AI system orchestrating 10 specialized agents to be a smart personal assistant on Discord, WhatsApp, and Web.*

</div>

---

## 📖 About the Project

**B.I.M.A-CORE** is the core of an AI assistant called **ANISA**. Using a **LangGraph state machine**, every user message is analyzed by an intent classifier, then routed to the most appropriate specialist agent — from web research, stock analysis, code debugging, to creative content generation.

```
User → Discord / WhatsApp / Web
            ↓
    Intent Classifier
            ↓
┌───────────┴───────────┐
│   LangGraph Engine    │
│    (State Machine)    │
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

## ✨ Core Features

| Feature | Description |
|-------|-----------|
| 🧠 **Multi-Agent Orchestration** | LangGraph auto-routes to the most relevant agent |
| 🔌 **MCP Integration** | Fetch, Markitdown, Time, Git, SQLite, sequential_thinking, memory — pluggable external tools |
| 💾 **Long-term Memory** | Vector store (LanceDB) + SQLite for persistent conversation context |
| 📊 **Real-time Dashboard** | Pixel-art guild hall (React + WebSocket) for activity visualization |
| 📄 **Document Processing** | PDF, Word, Excel, PowerPoint — read, analyze, and generate |
| 🌐 **Web Intelligence** | Marketplace scraping, web research, interactive browser automation |
| 📈 **Stock Market** | Real-time stock data, portfolio tracking, automated charts |
| 📱 **Multi-Channel** | Discord, WhatsApp, REST API — all in one system |
| 🎤 **Voice In/Out** | STT via faster-whisper (Indonesian) + TTS via edge-tts (`id-ID-GadisNeural`). Auto-mirror: voice input → voice reply |
| 🖼️ **Image-to-Image** | Upload a reference image + prompt → variations following the reference (Gemini Flash Image multimodal) |
| 🎵 **Music Bot Discord** | Stream YouTube / SoundCloud / YT Music to Discord voice channel — single track or full playlist (max 50 tracks, auto lazy-extract per track) |
| 🕵️ **OSINT Username Scan** | Sherlock-powered username lookup across 400+ social platforms (Twitter/X, Reddit, GitHub, TikTok, Telegram, etc) |
| 🖼️ **Image Search & Download** | Find + download images from Wikimedia Commons (license-safe) → fallback Serper Images. Usable as user-facing capability ("download logo X") and as document embed |
| 💰 **Cost-Optimized** | Dynamic model selection (DeepSeek, Gemini, Llama) via OpenRouter |
| 🗂️ **Obsidian Vault** | Knowledge management & document archiving integration |

---

## 🧑‍🤝‍🧑 Agent Roster

> Each agent has a different persona, toolset, and LLM model.

| Agent | Role | Main Expertise |
|------|-------|----------------|
| 🎯 **Manager** | Coordinator & Router | Understand context, distribute tasks, summarize results |
| 👁️ **Visual** | Visual Analyst | Image analysis, OCR, visual PDF parsing (Gemini Vision) |
| 🗂️ **Arsip** | Digital Librarian | Document archiving, knowledge vault, Obsidian integration |
| ⚙️ **Admin** | System Administrator | File management, task system, document generation (Word/Excel/PDF) |
| 🔍 **Intel** | Intelligence Agent | Web research, marketplace scraping, browser automation, OSINT username scan (Sherlock), image search & download |
| 🌿 **Lifestyle** | Lifestyle Consultant | Recommendations, life advice, everyday questions |
| 🎨 **Seniman** | Content Creator | Creative writing, design concepts, HTML/SVG/Mermaid + image gen + image-to-image |
| 🔧 **Mekanik** | Engineer & Debugger | Coding, debugging, code review, technical problems |
| 📈 **Saham** | Market Analyst | Stock analysis, portfolio, automated scheduled updates |
| 🐸 **Kodok** | Code understanding | Repo RAG, function/class/symbol lookup, codebase summarization |

---

## 🛠️ Tech Stack

```
Backend          │ Python 3.10+, FastAPI, Uvicorn
Orchestration    │ LangGraph, LangChain
Agent Framework  │ CrewAI
LLM Provider     │ OpenRouter (DeepSeek v4, Gemini 3.1 Flash, Llama 3.3)
Communication    │ Discord.py, WhatsApp-web.js (Node.js bridge)
Voice            │ faster-whisper (STT, Indonesian) + edge-tts (TTS) + ffmpeg (OGG/Opus convert)
Discord Voice    │ davey (discord.py 3.x voice runtime) + PyNaCl + yt-dlp (YouTube/SoundCloud)
OSINT            │ sherlock-project (400+ social platforms username scan)
Dashboard        │ React JSX (pixel art), WebSocket
Desktop App      │ Tauri 2.x (ANISA sidebar)
Vector Store     │ LanceDB + sentence-transformers
Database         │ SQLite (agent memory)
Browser Auto     │ browser-use >= 0.1.40
Task Scheduler   │ APScheduler
Process Manager  │ PM2 + Cloudflare Tunnel
Deployment       │ WSL Ubuntu 22.04+ (local PC) or Linux VPS
```

---

## 🚀 Installation

### Prerequisites

- Python 3.10+
- Node.js 20+
- Chromium (for browser automation)
- ffmpeg (for TTS audio conversion + music streaming — `apt install ffmpeg`)
- PM2 (for production)
- (Optional) `sherlock` CLI installed automatically with `sherlock-project` pip dep

### 1. Clone & Setup Environment

```bash
git clone https://github.com/Luciansvon/B.I.M.A-CORE.git
cd B.I.M.A-CORE

# Create virtual environment
python3 -m venv bima_env
source bima_env/bin/activate        # Linux/Mac
# or: bima_env\Scripts\activate     # Windows
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> ⚠️ First STT call downloads the `faster-whisper small` model (~390MB) to `~/.cache/huggingface`. One-time cost.

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# ─── REQUIRED ───────────────────────────────────
OPENROUTER_API_KEY=sk-or-v1-...
DISCORD_TOKEN=your-discord-bot-token

# ─── OPTIONAL ───────────────────────────────────
GEMINI_API_KEY=...
SERPER_API_KEY=...
TAVILY_API_KEY=...
RAPIDAPI_KEY=...

# ─── BOT CONFIG ─────────────────────────────────
LLM_PROVIDER=openrouter
EMBEDDING_PROVIDER=huggingface
OBSIDIAN_PATH=./Bima_Vault
DASHBOARD_PORT=8000
DASHBOARD_API_TOKEN=your-secret-token

# ─── DISCORD CHANNELS ───────────────────────────
BOT_STATUS_CHANNEL_ID=...
SAHAM_CHANNEL_ID=...

# ─── WHATSAPP (OPTIONAL) ────────────────────────
WA_OWNER_NUMBER=628xxxxxxxxxx
WA_BRIDGE_URL=http://127.0.0.1:8001
WA_BRIDGE_TOKEN=your-token
WA_TRIGGER=/bot

# ─── VOICE (OPTIONAL OVERRIDES) ─────────────────
STT_MODEL_SIZE=small           # tiny|base|small|medium|large-v3
STT_COMPUTE_TYPE=int8          # int8|float16|float32
TTS_VOICE=id-ID-GadisNeural    # female Indonesian
TTS_RATE=+0%
```

### 4. Run

```bash
# Development (local)
python main.py

# Health check
python healthcheck.py
```

---

## 🖥️ Production Deployment (PM2)

```bash
# Install PM2 & Node.js
npm install -g pm2

# Start all services
pm2 start ecosystem.config.js

# Save config & enable autostart
pm2 save
pm2 startup

# Monitor
pm2 logs anisa-v3
pm2 status
```

PM2 runs 3 processes in parallel:

| Process | Description |
|--------|-----------|
| `anisa-v3` | Main bot (Python) |
| `bima-tunnel` | Cloudflare Tunnel |
| `bima-whatsapp` | WhatsApp bridge (Node.js) |

### Auto-start on Windows login (WSL setup)

If you run BIMA_CORE on WSL Ubuntu (not native Linux VPS), you need 2 layers to auto-start the bot on Windows login:

**Layer 1 — Enable systemd in WSL** (`/etc/wsl.conf`):

```ini
[boot]
systemd=true

[user]
default=bima_lucian
```

Restart WSL after editing: `wsl --shutdown` (from PowerShell) → wait → `wsl -d Ubuntu`.

**Layer 2 — PM2 systemd unit (run in WSL Ubuntu):**

```bash
# Generate + install systemd service (one-time)
sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u bima_lucian --hp /home/bima_lucian

# Save current process list to dump file
pm2 save

# Verify
systemctl status pm2-bima_lucian
```

**Layer 3 — Trigger WSL boot on Windows login** (via Windows Task Scheduler):

```powershell
# Create task — runs on user login
$action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-d Ubuntu --exec /bin/true"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "WSL-BIMA-Boot" -Action $action -Trigger $trigger -RunLevel Highest
```

This task simply "wakes" WSL — once WSL is up, systemd auto-starts PM2, PM2 auto-resurrects processes from dump file. Bot online without manual launch.

---

## 🌐 PC/WSL vs VPS — when to migrate?

Currently you run on **WSL Ubuntu on your PC**. Good enough for development + casual use, but with limitations:

| Aspect | WSL on PC (now) | Native Linux VPS |
|---|---|---|
| Uptime | Only when PC is on | 24/7 (~99.9% SLA) |
| Cost | $0 | $5-10/month (e.g. Hetzner CX11, DigitalOcean droplet) |
| RAM | Shared with Windows/games | Dedicated 2-8GB |
| Discord Latency | Depends on home internet | Stable datacenter |
| Maintenance | You restart it yourself | Auto-update OS, snapshots, etc |
| Setup | Already running | Migrate everything (10-30 min using `deploy_vps.sh`) |

**Signs you need to migrate to VPS:**
- Bot frequently dies because PC is turned off / Windows restart
- Stock scheduler misses crucial events while you sleep / work
- Bima joins Discord 24/7 (community bot)

**Signs PC is still enough:**
- Just you + 1-2 users
- Furniture QC + casual chat use case
- No 24/7 / SLA commitment yet

Migration path: `deploy_vps.sh` is already in the repo — run it on a blank Ubuntu VPS, auto-clones repo + installs deps + sets up PM2 + Cloudflare tunnel. Migration ~30 min.

---

## 📊 Dashboard

Access the real-time dashboard after the bot is running:

| URL | Description |
|-----|-----------|
| `http://localhost:8000/dashboard` | Main dashboard |
| `http://localhost:8000/dashboard/v3` | Pixel art guild hall |
| `http://localhost:8000/metrics` | Metrics API (JSON) |

The dashboard shows agent activity in real-time via WebSocket — you can see which agent is currently active, conversation history, and system status.

---

## 📁 Project Structure

```
B.I.M.A-CORE/
├── main.py                    # Entry point
├── config.py                  # LLM & model config
├── config_mcp.json            # MCP server config
├── requirements.txt
├── ecosystem.config.js        # PM2 config
│
├── core/                      # Main engine
│   ├── discord_bot.py         # Discord bot (handles attachments, audio auto-STT, music pre-route)
│   ├── wa_server.py           # WhatsApp HTTP bridge (audio auto-STT, TTS reply)
│   ├── stt.py                 # faster-whisper wrapper (lazy singleton)
│   ├── tts.py                 # edge-tts + ffmpeg → OGG/Opus
│   ├── music_player.py        # Per-guild voice client + queue + yt-dlp extract
│   ├── music_commands.py      # !play / !skip / !queue / ... handler
│   ├── api_retry.py           # Centralized stamina retry for external APIs
│   ├── langgraph_engine.py    # State machine orchestration
│   ├── langgraph_nodes/       # Node per agent
│   │   ├── state.py           # BimaState definition
│   │   ├── manager.py
│   │   ├── intel.py
│   │   ├── visual.py
│   │   ├── seniman.py         # Image gen + img2img branch
│   │   └── ...
│   ├── dashboard_server.py    # FastAPI + WebSocket
│   ├── mcp_client_manager.py  # MCP integration
│   └── saham_*.py             # Stock modules
│
├── teams/                     # CrewAI agent definitions
├── tools/                     # Shared tools & plugins
│   ├── image_gen_tool.py      # Text-to-image + image-to-image (Gemini Flash Image)
│   ├── image_search_tool.py   # Wikimedia/Serper image lookup + download
│   ├── sherlock_tool.py       # OSINT username scan (Sherlock CLI wrapper)
│   ├── browser_use_tool.py    # Browser automation
│   ├── repo_rag.py            # Repository RAG
│   └── plugins/               # Dynamic plugins
│
├── whatsapp/                  # WhatsApp bridge (Node.js)
│   └── index.js               # whatsapp-web.js client, STT arming logic
│
├── dashboard/                 # Frontend pixel art (React JSX)
│   ├── guild.html
│   └── guild-*.jsx
│
└── frontend/                  # Desktop sidebar (Tauri)
```

---

## 🔌 MCP Tools

B.I.M.A supports **Model Context Protocol (MCP)** for pluggable external tool integration. Each MCP is attached to a specific agent via `attach_to` in `config_mcp.json`.

**Enabled by default:**

| MCP | Function | Attached agent |
|-----|--------|----------------|
| `fetch` | Fetch web content as text/markdown | intel |
| `markitdown` | Convert PDF/DOCX/PPTX/XLSX to Markdown | arsip, visual |
| `sequential_thinking` | Structured reasoning chain | manager (Anisa) |
| `memory_anthropic` | Persistent KV memory cross-session | arsip, manager |
| `time` | Current time + timezone conversion | manager, saham, lifestyle |
| `sqlite` | Structured store for Discord log + stock journal | arsip, saham |
| `git` | Log/blame/diff BIMA_CORE repo | mekanik, kodok |

**Disabled (config-only, requires extra setup):**

- `github` — needs `GITHUB_PERSONAL_ACCESS_TOKEN` in `.env`
- `searxng` — needs `SEARXNG_URL` (public instance or self-host) in `.env`
- `duckduckgo` — kept config-only (redundant with `SerperDevTool` already wired in agents)
- `playwright` — kept config-only (redundant with `BrowserUseTool` already wired in agents)
- `filesystem` — kept config-only (internal `FileSaverTool` covers `outputs/` scope)

Add/edit tools in `config_mcp.json`. Restart the bot so `MCPClientManager` reloads the config.

---

## 🛡️ Reliability & Observability

| Stack | Purpose | Setup |
|---|---|---|
| `uvloop` | Drop-in asyncio 2-4× speedup | Auto-active in [main.py](main.py) |
| `loguru` | Color/structured logging, replaces stdlib | Auto-active with stdlib intercept |
| `memray` | Memory profiler (manual run) | `memray run --live bima_env/bin/python main.py` |
| `pyinstrument` | CPU flamegraph profiler (manual run) | `pyinstrument bima_env/bin/python main.py` |
| `sentry-sdk` | Auto-capture crashes + stack trace + breadcrumb | Set `SENTRY_DSN` in `.env` (free tier 5k events/month) |
| `apprise` | Multi-channel notify fallback (Telegram/ntfy/email/etc) | Set `APPRISE_URLS` in `.env` comma-separated |
| `psutil` | System metrics (CPU/RAM/disk) | Auto via `!status` Discord command |
| `stamina` | Retry decorator (jitter + exp backoff) | Centralized in [core/api_retry.py](core/api_retry.py) — wraps yfinance + embedder + furniture_qc |
| `diskcache` | Persistent disk cache (TTL built-in) | Auto-used for cloud embedding cache in [core/embedder.py](core/embedder.py) |

Without `.env` setup, `sentry-sdk` + `apprise` become no-ops (safe, no error). Once `.env` is filled, they activate.

---

## 🧠 RAG Quality (Wave 3)

Embedding backend switchable local/cloud via env `EMBEDDING_BACKEND`:

| Backend | Arsip model | Code model (repo_rag) | Dim | RAM | Cost |
|---|---|---|---|---|---|
| `local` (default) | `all-MiniLM-L6-v2` | `all-MiniLM-L6-v2` | 384 | ~2GB | $0 |
| `cloud` | `baai/bge-m3` | `mistralai/codestral-embed-2505` | 1024 | ~0 | ~$0.03/month |

**Switch to cloud (for more accurate Indonesian RAG):**

```bash
# 1. Set in .env
EMBEDDING_BACKEND=cloud
EMBED_CACHE_TTL_DAYS=30

# 2. Drop existing index (dim changes 384→1024)
rm -rf vault_index/ repo_index/

# 3. Restart bot — index auto-rebuilds with new model
pm2 restart anisa-v3
```

**Hybrid search (BM25 + vector):** helper at [core/bm25_index.py](core/bm25_index.py) — `build_from_corpus()` + `BM25Index.search()` + `hybrid_merge()`. Not yet wired into arsip/repo_rag flow (opt-in if you want to use it).

---

## 🎤 Voice Pipeline (STT + TTS)

### Speech-to-Text (input)

- **Engine**: `faster-whisper small` (multilingual, Indonesian primary). Auto-downloaded on first call (~390MB to `~/.cache/huggingface`).
- **Decode**: Opus/OGG voice notes via ffmpeg (no manual conversion).
- **Tuning**: `vad_filter=True`, `beam_size=8`, plus Indonesian context `initial_prompt` to bias short-utterance recognition.
- **Async-safe**: STT runs on a thread to avoid blocking the FastAPI / discord.py event loop.

### Text-to-Speech (output)

- **Engine**: `edge-tts` → Microsoft Neural Voice `id-ID-GadisNeural` (female Indonesian, free, no API key).
- **Pipeline**: edge-tts emits MP3 → ffmpeg converts to OGG/Opus (24 kHz mono, VoIP profile) → WhatsApp accepts as native voice note (`sendAudioAsVoice: true`).
- **Smart filter**:
  - Reply ≤ 300 chars → full reply spoken as voice, text suppressed
  - Reply > 300 chars → text reply + 1-line voice summary ("Anisa kirim jawaban lengkap di chat, baca dari teks ya.")

### Auto-mirror

- Voice in → voice out, text in → text out. No explicit user toggle needed.

---

## 🎵 Music Bot (Discord)

Stream audio from YouTube / SoundCloud / YT Music to Discord voice channels. Per-guild player + queue, auto-disconnect after 5 minutes idle, FFmpeg reconnect on network blip, forced 48 kHz stereo PCM output (so playback speed is consistent — no 1.08× drift from sample-rate mismatch).

| Command | Function |
|---|---|
| `!play <judul/URL>` | Search YouTube top-1 or direct URL. Auto-joins your current voice channel. Accepts single track OR full playlist URL (max 50 tracks, lazy-extracted per-track at play time). |
| `!skip` | Skip current track |
| `!queue` / `!q` | Show queue (up to 10 shown + total count) |
| `!pause` / `!resume` | Pause / resume playback |
| `!stop` | Clear queue + stop playback |
| `!np` | Now playing |
| `!leave` | Disconnect from voice channel |
| `!loop [off\|track\|queue]` | Loop mode |
| `!music` / `!musik` | Help |

**Requirements**: bot role needs `Connect` + `Speak` voice permissions, plus channel-level access to the voice channel you're in.

**Playlist behavior**: paste a YouTube playlist URL (`?list=...`) — all tracks (capped at 50) get enqueued instantly via flat metadata extraction. Each track is fresh-extracted only when it's about to play, which sidesteps URL expiration and keeps enqueue fast.

---

## 📱 WhatsApp Commands

The WA bridge requires the prefix configured in `WA_TRIGGER` (default `/bot`). Voice notes are silent-ignored by default — they must be armed first to avoid spamming the LangGraph engine with random voice notes from other chats.

| Command | Function |
|---|---|
| `/bot <message>` | General chat — routed via LangGraph |
| `/bot help` | Show help |
| `/bot ping` / `/bot status` | Backend health check |
| `/bot stt` (alias: `tts`, `voice`, `suara`, `v`, `note`, `vn`) | Arm STT for 60 seconds — the next voice note (PTT) will be transcribed |
| `/bot login <password>` | Login (if `WA_BOT_PASSWORD` is set) |
| `/bot logout` | Logout |
| `/bot wl …` / `/bot password …` / `/bot session …` | Admin commands (whitelist, password rotation, session kick) |

**Voice flow example:**

```
You  → /bot stt
Bot  → 🎤 Voice mode aktif 60 detik. Kirim voice note — Anisa bales pakai voice juga.
You  → [voice note: "halo Anisa lagi ngapain?"]
Bot  → [voice note from Anisa, ≤ 300 chars reply]
```

Audio file attachments (e.g. `.mp3`, `.m4a` uploaded via the paperclip with `/bot` caption) are auto-transcribed without arming.

---

## 🛠️ Discord Commands

| Command | Function |
|---|---|
| `!saham help` | List stock subcommands (digest, watchlist, ticker, chart, portfolio, override) |
| `!qc` + PDF/PNG/JPG attachment | **Furniture drawing QC** — review working drawings: dimensions, joint details, views, BOM. Output: text report + markup PNG (colored overlay box at issue locations). Uses Gemini Flash vision via OpenRouter. ⚠️ Test with personal projects only, NOT client/company drawings (data goes through third-party cloud). |
| `!ocr` + image attachment | OCR via EasyOCR — extract text from images (PNG/JPG/WEBP). Supports Indonesian + English. Lazy-loads model ~80MB (first call slow, subsequent fast). |
| `!status` | Host health snapshot (PC/WSL or VPS) — CPU/RAM/disk/load average/process count. Uses psutil. |
| `!play` / `!skip` / `!queue` / `!pause` / `!resume` / `!stop` / `!np` / `!leave` / `!loop` / `!music` | Music bot — see [Music Bot section](#-music-bot-discord) above |
| mention `@Anisa <message>` | General chat → LangGraph router auto-picks the most relevant agent |
| Audio attachment (`.ogg/.opus/.mp3/.m4a/.wav/.flac/.aac`) | Auto-transcribed via faster-whisper (no arming required on Discord — user intent is implicit via mention/DM). Voice reply attached if input was audio. |
| Image attachment + "bikin gambar variasi" | Image-to-image (Seniman team) — generates variations following the reference |
| `@Anisa cek username X di sosmed` | OSINT via Sherlock — routed to Intel agent, returns list of platforms where the username is registered |
| `@Anisa carikan logo / download foto X` | Image search & download via Wikimedia Commons (license-safe) → fallback Serper Images |

---

## 🤝 Contributing

1. Fork this repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'feat: add feature X'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📋 License

This project is developed for personal and educational use.

---

<div align="center">

*Built with ❤️ using LangGraph, CrewAI, and Python*

**ANISA** — *Your Intelligent Guild Commander*

</div>
