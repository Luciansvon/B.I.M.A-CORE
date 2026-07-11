# BIMA-CORE

A LangGraph-based multi-agent orchestration engine for personal automation across Discord, WhatsApp, and Web channels.

---

## 🏗️ Architecture & Message Flow

BIMA-CORE operates as a state machine where incoming messages are analyzed, pre-routed, classified, and processed by specialized agents before returning output.

```
Incoming Message (Discord / WhatsApp / REST API)
       │
       ▼
[Pre-Route Handler] ── (Direct Commands: !play, !qc, !ocr, !status, STT transcription)
       │
       ▼
[intent_classifier.py] ── (Fast regex-based intent matching)
       │
       ▼
[manager.py] ── (LLM-based fallback routing)
       │
       ├──────────────┬──────────────┬──────────────┬──────────────┤
       ▼              ▼              ▼              ▼              ▼
[intel.py]        [arsip.py]     [mekanik.py]    [kodok.py]    [observer.py]
Web RAG, Threads   Obsidian       Code            Repo RAG      Desktop screen
Sherlock OSINT     Vault, Marp    Execution       Explain/      capture (Windows
                   Slide Gen                      Search/       bridge, `/lihat`)
                                                   Visualizer
       │              │              │              │              │
       └──────────────┴──────────────┴──────────────┴──────────────┘
                                ▼
                       [BimaState Output]
```

---

## 🛠️ Tech Stack

- **Core Engine & Orchestration**: Python 3.10+, FastAPI, Uvicorn, LangGraph, CrewAI.
- **LLM Clients**: OpenRouter (DeepSeek V4 Flash/Pro, Gemini 3.5 Flash, Claude Sonnet 5).
- **External Bridges**: `discord.py` 2.x, `whatsapp-web.js` (Node.js bridge).
- **Speech & Audio**: `faster-whisper large-v3-turbo` (STT, multilingual/Indonesian), `F5-TTS` (voice cloning via `Eempostor/F5-TTS-INDO-FINETUNE-V2` with `edge-tts` fallback), `ffmpeg`.
- **System Automation & OSINT**: `browser-use` (Playwright), `sherlock-project` (OSINT), `agent-reach` CLI, RapidAPI X scrapers.
- **Document & Media Compile**: OfficeCLI (native `.xlsx` w/ live charts), `python-docx` + `fpdf2` (Word/PDF), `@marp-team/marp-cli` (Slides), `Cytoscape.js` (Codebase network map), Jina Reader Web Fetch API.
- **Multilingual RAG**: LanceDB + `Qwen3-Embedding-0.6B` (embedding) + `bge-reranker-v2-m3` (reranking) — both multilingual, Indonesian-optimized.
- **Cache & Storage**: SQLite, DiskCache, Headroom context compressor.
- **Vision OCR**: Gemini Vision (VLM) with `easyocr` offline fallback.

---

## ⚙️ Core Modules & Capabilities

### 💬 Threads Automation & Scheduling
- **Persona Modeling**: Automated draft generation constrained to a specific Gen-Z Indonesian tone (casual chat contractions, no hyphens, strict emoji limits, under 500 characters). Drafts are scrubbed of AI self-disclaimers and competitor-tool mentions (e.g. "I can't generate images, use Midjourney/DALL-E/Canva") so the persona never breaks.
- **Scheduler**: APScheduler triggers randomized posting slots daily (morning, afternoon, evening) using local database facts (`scientific_facts.json`) or dynamic LLM ideas.
- **Topic Variety Guard**: Recently-used topics are tracked (`outputs/threads_recent_topics.json`) and fed to the idea LLM as an exclusion list, while subject-level de-duplication stops the bot from repeatedly posting the same subject (e.g. sharks).
- **Minimal-Edit Revisions**: When the owner asks for a small tweak (e.g. "swap the emoji"), only that part changes — the rest of the draft is preserved verbatim instead of being rewritten.
- **Image Generation & Tunnel-Free Hosting**: Optional AI image (OpenRouter Gemini, txt2img) is published to a public URL via a layered strategy — **Catbox.moe → Discord CDN → text-only fallback** — because the Threads API downloads media from a public URL rather than accepting byte uploads. Each URL is reachability-checked before posting, so a flaky host degrades to a text post instead of failing the whole publish.
- **Human-in-the-Loop Gate**: All posts route to the owner's Discord DM for approval. If the owner is AFK (5-minute timeout), safe topics auto-publish while sensitive topics auto-cancel.
- **Interaction Scan**: Runs every 5 minutes, filtering out toxic/spam comments (e.g. slot, promo) and auto-replying to simple greetings.

### 🎤 Voice Pipeline (STT + TTS)
- **Lazy Singleton STT**: `faster-whisper large-v3-turbo` (CPU int8) processes audio attachments and voice notes asynchronously — multilingual, tuned for Indonesian short utterances.
- **Isolated TTS Worker**: F5-TTS runs inside an isolated subprocess (`core/tts_worker.py`) to release VRAM on completion and prevent CUDA crashes from propagating.
- **Smart Opener Mode**:
  - Replies ≤ 80 characters are synthesized in full.
  - Replies > 80 characters trigger a short context-aware audio summary (LLM generated) while sending the full reply as text.

### 📄 Document Generator (T4 Admin)
- **Multi-format output**: Excel (`.xlsx`), Word (`.docx`), and PDF from structured JSON — reports, proposals, invoices, formal letters, meeting minutes, theses.
- **4 Indonesian writing registers** (`formal` / `semi_formal` / `informal` / `akademik`), each with its own color palette, typography, margins, and tone. Presets live in `teams/t4_admin/document_styles.json` — add or tweak a style by editing JSON, no code change or redeploy needed.
- **Native Excel via OfficeCLI**: spreadsheets are built through the [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI) binary (offline, Apache-2.0) — charts are real interactive Excel chart objects (not static images), with formulas, freeze panes, merged summary sheets, and clickable reference links.
- **Academic mode**: Times New Roman 12pt, 1.5 spacing, 4-4-3-3 cm margins, abstract + keywords page, and automatic Roman → Arabic page-number switching for front matter vs body.
- **Context-aware style detection**: the agent infers the right register from conversation history and upstream team output; keyword matching is only a fallback hint.
- Agent persona/instructions are externalized to `teams/t4_admin/prompt_templates/backstory.md` — editable without touching Python.

### 📊 Marp Slide Generator
- Compiles custom Marp Markdown + CSS into PDF, PPTX, HTML, or PNG.
- Exports slide previews to the owner via Discord DM for check/approval before compiling the final proposal document.

### 🖧 Codebase Visualizer
- Analyzes Python import dependencies in the workspace relative to `BASE_DIR` using the Abstract Syntax Tree (`ast`).
- Outputs an interactive, browser-loadable network map (`outputs/codebase_map_*.html`) powered by Cytoscape.js with directory filters and physics layout switching.

### 🐸 Kodok — Code Doctor & Repo Whisperer
- Answers questions about the BIMA_CORE codebase itself: explain a file, find a function/class, summarize a module, or check RAG index status — always grounded in the semantic + AST-chunked repo index (`tools/repo_rag_tools.py`), never from memory.
- Reachable via natural-language triggers ("jelasin file X", "cari fungsi Y", "index udah jalan?") through the fast-path regex classifier, with the LLM manager as a routing fallback (`[ROUTE: kodok]`).

### 🖥️ Observer — Desktop Screen Bridge
- On-demand screen observation via a Windows desktop bridge (`core/desktop_bridge_client.py`); describes the active app/window and what's happening, triggered by `/lihat` or phrases like "cek layar gue".
- Observation-only in the current phase — no remote action/execution is wired up (`DESKTOP_EXECUTE_ENABLED` is hardcoded `False`).

### 🛡️ MCP Security Scan (Bumblebee Audit)
- Audits `config_mcp.json` automatically on startup.
- Verifies execution command whitelists (`npx`, `uvx`, `node`, `python3`).
- Screens arguments for path traversal (`../`) and command injection keyword patterns, halting execution if critical risks are detected.

### 🧹 Anti-AI Slop (Stop-Slop) & Style Filter
- **Deslop Tool**: Automatic LLM-based draft editor that removes AI tells, filler phrases, passive voice, and local Indonesian AI clichés (e.g. "di era digital", "solusi terbaik").
- **Integration**: Active in Threads drafting/revisions, Admin Agent documents, and Manager Agent responses.

### 📚 Obsidian Vault Semantic Linker
- **Vault Linker**: Automates internal wiki-linking (`[[WikiLink]]`) of related notes in the Obsidian Vault.
- **Dynamic Recommendations**: Conducts LanceDB vector similarity queries to suggest and append related notes under a "Catatan Terkait" section.

### 🌐 Smart Web Extraction & Social Intelligence
- **XReach**: Fetches recent Twitter posts via the `agent-reach` CLI with automated fallbacks to two RapidAPI X scrapers.
- **Jina Reader**: Fetches clean markdown representations of any web page to reduce token consumption and improve LLM reading comprehension.

---

## 📁 Repository Layout

```
BIMA_CORE/
├── main.py                    # App entry point (loads env, boots bridges & FastAPI)
├── config.py                  # Centralized LLM configuration
├── config_mcp.json            # Model Context Protocol server configuration
├── requirements.txt           # Python dependency manifest
├── ecosystem.config.js        # PM2 process definitions
│
├── core/                      # Core automation logic
│   ├── discord_bot.py         # Discord gateway & pre-route command parsing
│   ├── wa_server.py           # WhatsApp HTTP POST handler
│   ├── langgraph_engine.py    # LangGraph routing state machine
│   ├── permission_gate.py     # Discord DM-based approval gateway
│   ├── mcp_security.py        # Startup Bumblebee configuration scanner
│   ├── tts.py / tts_worker.py # Voice synthesis and subprocess execution
│   ├── threads_scheduler.py   # APScheduler Threads posting loop
│   ├── threads_commands.py    # Threads drafting, revision, publish & comment-reply flows
│   └── image_host.py          # Tunnel-free public image hosting (Catbox → Discord CDN)
│
├── teams/                     # CrewAI agent definitions
│   ├── t1_manager.py          # State tracking & token budget tools
│   ├── t4_admin/              # Document generator package (Excel via OfficeCLI, Word, PDF)
│   │   ├── document_styles.json       # 4 style presets (data-driven, hot-editable)
│   │   └── prompt_templates/          # Agent backstory as markdown (no-redeploy edits)
│   ├── t5_intel.py            # Web scraping, Sherlock, and browser automation agents
│   ├── t8_mekanik.py          # Code execution and file management tools
│   └── t10_kodok.py           # Code Doctor — repo explain/search/summarize agent
│
├── tools/                     # CrewAI custom tools
│   ├── slide_generator.py     # Marp compile wrapper
│   ├── code_visualizer.py     # AST dependency analysis to Cytoscape.js
│   └── repo_rag_tools.py      # Semantic + AST-chunked repo RAG tools (used by Kodok)
│
├── whatsapp/                  # Node.js WhatsApp Web API bridge
└── Bima_Vault/                # Obsidian markdown notes (RAG dataset)
```

---

## 🚀 Installation & Local Run

### Prerequisites
- Python 3.10+ & Node.js 20+
- `ffmpeg` (installed on system path)
- Chrome / Chromium browser (for Playwright/browser-use)
- OfficeCLI — required for Excel generation (T4 Admin), not a pip dependency:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh | bash
  ```

### 1. Clone & Setup Environment
```bash
git clone https://github.com/Luciansvon/B.I.M.A-CORE.git
cd B.I.M.A-CORE

# Create virtual environment
python3 -m venv bima_env
source bima_env/bin/activate  # Linux/WSL
# or: bima_env\Scripts\activate on Windows
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt

# Setup Playwright browsers
playwright install chromium
```
> *Note: First run downloads model weights — `faster-whisper large-v3-turbo` (~1.6GB), `F5-TTS` (~1.2GB), `Qwen3-Embedding-0.6B` (~1.2GB), and `bge-reranker-v2-m3` (~2.3GB). On flaky links, prefer `wget -c` / an HF token to avoid rate-limited stalls.*

### 3. Environment Variables (`.env`)
Create a `.env` file from the template:
```bash
cp .env.example .env
```
Key configuration overrides:
```env
# Credentials
OPENROUTER_API_KEY=sk-or-v1-...
DISCORD_TOKEN=your-discord-bot-token

# Channels & Notifications
BOT_STATUS_CHANNEL_ID=your-channel-id
SAHAM_CHANNEL_ID=your-channel-id

# Context Compression (Headroom)
ENABLE_HEADROOM=false
HEADROOM_TARGET_RATIO=0.4

# Threads API Credentials
THREADS_APP_ID=your-app-id
THREADS_APP_SECRET=your-app-secret
THREADS_ACCESS_TOKEN=your-token
ENABLE_THREADS_AUTO=true
BIMA_DISCORD_USER_ID=your-discord-id
# Optional: Discord channel ID used to host Threads images (Discord CDN fallback).
# If unset, image hosting falls back to DMing the image to the owner.
THREADS_MEDIA_CHANNEL_ID=your-channel-id
```

### 4. Run Application
```bash
# Verify syntax & health
python scripts/healthcheck.py

# Start application locally
python main.py
```

---

## 🖥️ Production Deployment (PM2 + WSL Systemd)

For 24/7 WSL execution on a Windows host, BIMA-CORE uses a PM2 process lifecycle manager and a systemd boot hook.

### 1. PM2 Setup (WSL)
```bash
# Install PM2 globally
npm install -g pm2

# Boot services (main bot, Cloudflare tunnel, WhatsApp bridge)
pm2 start ecosystem.config.js
pm2 save
```

### 2. WSL Systemd Enable
Edit `/etc/wsl.conf` to enable boot initialization:
```ini
[boot]
systemd=true

[user]
default=bima_lucian
```
Restart WSL from a Windows host Administrator PowerShell:
```powershell
wsl --shutdown
wsl -d Ubuntu
```

### 3. Systemd PM2 Unit Registration
Run the startup script generator in WSL to ensure PM2 resurrects on boot:
```bash
sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u bima_lucian --hp /home/bima_lucian
pm2 save
```

### 4. Windows Login Trigger
Create a task in Windows Task Scheduler to wake WSL on user login:
```powershell
$action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-d Ubuntu --exec /bin/true"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "WSL-BIMA-Boot" -Action $action -Trigger $trigger -RunLevel Highest
```

---

## 🕹️ Command Reference

### Discord Command Interface

| Command | Function / Payload |
|---|---|
| `!threads [topic] [--image]` | Runs Threads drafting flow. Lists trends if no topic provided. |
| `!arsip [subcommand]` | Manage Obsidian vault notes. Subcommands: `help`, `hubungkan` (link semantik & rapikan), `index` (re-index). |
| `!qc` + PDF/PNG/JPG | Review drawing details (Gemini Flash Vision). Generates issue coordinates. Vision model, page cap, and target resolution are tunable via `QC_MODEL` / `QC_MAX_PAGES` / `QC_TARGET_WIDTH_PX` / `QC_MAX_FILE_MB` in `.env` (falls back to `config.py` defaults). |
| `!ocr` + Image | Extract text (Indonesian/English) via Gemini Vision (VLM); `easyocr` offline fallback. |
| `!status` | Inspect CPU, memory, Disk, and PM2 load using `psutil`. |
| `!play <query/URL>` | Enqueue music to current voice channel (supports playlists up to 50 tracks). |
| `!skip` / `!queue` / `!stop` | Control active music player queue. |

### WhatsApp Prefix Command Interface (`/bot ...`)

| Command | Function / Payload |
|---|---|
| `/bot <prompt>` | Submit query directly to LangGraph manager routing. |
| `/bot stt` | Arm Speech-to-Text bridge for 60 seconds (transcribes next incoming voice message). |
| `/bot ping` / `/bot status` | Health check and latency reporting. |
| `/bot login <pwd>` | Establish admin privileges on session. |

---

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -m 'feat: description'`
3. Submit a Pull Request.

> *Important: Before submitting code, read [`AGENTS.md`](AGENTS.md) to ensure compliance with our strict exploration, safety gating, and context retrieval conventions.*

---

<div align="center">
  <sub>Developed for personal automation. Built using LangGraph, CrewAI, and Python.</sub>
</div>
