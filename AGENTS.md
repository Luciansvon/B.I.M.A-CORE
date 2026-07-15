# AGENTS.md — BIMA_CORE Context for AI Agents

This file is the single source of truth for any AI coding agent (Claude Code, Cursor, Aider, Codex, Windsurf, Copilot, Continue, etc.) working on this repository. Read this first.

Setiap task hanya boleh memiliki satu PLAN dalam file Markdown agar bisa diaudit Bima. Setelah PLAN disetujui, langsung lanjut CODE dan VERIFY tanpa membuat PLAN atau approval gate baru. Re-plan hanya jika Bima merevisi scope atau meminta perubahan rencana.

## TL;DR

- **What**: Python multi-agent AI bot named **Anisa**. Discord + WhatsApp + REST. LangGraph state machine orchestrates 10 specialist agents.
- **Owner**: Bima — solo dev. Reply casual Bahasa Indonesia.
- **Run env**: WSL Ubuntu di Windows host. Python venv at `bima_env/`. Production via PM2.
- **Workflow**: EXPLORE → satu PLAN → CODE → VERIFY. Approval PLAN hanya sekali; re-plan hanya saat Bima merevisi scope atau memintanya. See [`CLAUDE.md`](CLAUDE.md) for the full rules — they are mandatory.

## Operating Rules

Full rules live in [`claude.md`](claude.md) (same content as `Rules for agent.md`). Memorize all 8 rules. The non-negotiable ones:

1. **Never skip phases.** Always EXPLORE first (read/grep code), then write exactly one PLAN (numbered list, wait for one approval), then continue through CODE and VERIFY without another plan gate. Re-plan only when Bima revises scope or explicitly asks.
2. **Context before assumption.** Read or grep before claiming a symbol/file/API exists. When uncertain, say "I don't know" and ask.
3. **Minimal diff.** Touch only files directly required. No drive-by cleanup, no unrequested refactors.
4. **Ask before destructive ops.** Installing/removing deps, modifying `.env`/settings/CI, `git reset --hard`, `rm -rf`, migrations — all require explicit approval.
5. **Never bypass safety.** No `--no-verify`, no `--force`, no `try/except: pass` shortcuts.
6. **Honest reporting.** If something didn't work, say so. No "" / "Perfect!" / "Done!" — just facts. 5-line summary max at task end.

## Bima's Preferences (durable)

- **Don't over-ask on trivial ops.** Once a plan is approved, stop asking permission for obvious follow-ups (pre-warming a model, restarting a service, running smoke tests). Just do them. Reserve asking for: scope change, new dependency, destructive ops, ambiguous business logic.
- **One-plan rule.** Satu task hanya satu PLAN dan satu approval gate. Pertanyaan status atau detail dari Bima bukan alasan membuat PLAN baru; revisi PLAN hanya jika Bima mengubah scope atau memintanya.
- **Bahasa Indonesia casual** for replies. Code/identifiers stay English.
- **Strict EXPLORE→PLAN→CODE→VERIFY discipline.** Bima wrote these rules himself across `claude.md` + `Rules for agent.md`.

## Stack

```
Backend         | Python 3.10+, FastAPI, Uvicorn
Orchestration   | LangGraph (state machine), LangChain
Agent framework | CrewAI
LLM provider    | OpenRouter (DeepSeek v4, Gemini 3.1 Flash, Llama 3.3)
Communication   | discord.py 2.x + davey (voice runtime), whatsapp-web.js (Node.js bridge)
Voice           | faster-whisper (STT, Indonesian) + edge-tts/F5-TTS (TTS) + ffmpeg
Music           | yt-dlp + PyNaCl
Vector store    | LanceDB + sentence-transformers
Database        | SQLite (per-agent memory)
Web automation  | browser-use, scrapling
Task scheduler  | APScheduler
Process manager | PM2 + Cloudflare Tunnel
OSINT           | sherlock-project
```

## Architecture flow

```
User (Discord / WhatsApp / Web)
       │
       ▼
discord_bot.py  or  wa_server.py  (HTTP /chat)
       │
       │  pre-route: !saham, !qc, !ocr, !status, !play/!skip/!queue (music), audio attachment → STT
       │
       ▼
core/langgraph_engine.py (state machine)
       │
       ▼
core/langgraph_nodes/intent_classifier.py  (fast-path regex routing)
       │
       ▼
manager (LLM) → routes to 1+ specialist nodes:
  visual, arsip, admin, intel, lifestyle, seniman, mekanik, saham, kodok, observer
       │
       ▼
core/langgraph_nodes/<team>.py → teams/t<N>_<team>.py (CrewAI agent + tools)
       │
       ▼
Output: text reply + optional file attachment (PDF/Word/Excel/HTML/image/audio)
```

State shape: see `core/langgraph_nodes/state.py` (BimaState TypedDict).

## Repository layout

```
main.py                    Entry point (loads .env, starts Discord + FastAPI dashboard + WA bridge)
config.py                  LLM model selection (admin_llm, intel_llm, etc.)
config_mcp.json            MCP server config
ecosystem.config.js        PM2 process definitions
requirements.txt           Python deps

core/                      Engine + per-channel handlers
  discord_bot.py             Discord client + pre-route commands + attachment handling
  wa_server.py               WhatsApp HTTP bridge (POST /chat)
  langgraph_engine.py        State machine orchestration
  langgraph_nodes/           One node per agent role
    state.py                   BimaState TypedDict
    manager.py                 LLM-based router (fallback when intent_classifier misses)
    intent_classifier.py       Fast-path regex routing
    seniman.py                 Image/video gen + HTML doc rendering
    canvas.py                  PDF iterative editing
    visual.py                  Image/PDF analysis
    observer.py                Desktop screen capture (Windows bridge)
    ...                        intel, arsip, admin, mekanik, saham, lifestyle, kodok
  stt.py                     faster-whisper singleton, lazy load
  tts.py                     F5-TTS (GPU primary) → edge-tts fallback → ffmpeg → OGG/Opus
  music_player.py            Per-guild Discord voice client + yt-dlp queue
  music_commands.py          !play / !skip / !queue / etc.
  api_retry.py               Centralized stamina retry wrapper for external APIs
  mcp_client_manager.py      MCP server lifecycle
  saham_*.py                 Stock data (yfinance), chart, scheduler
  ocr.py / furniture_qc.py   EasyOCR + Gemini Vision QC
  embedder.py                Hybrid local/cloud embedding
  output_prune.py            Periodic cleanup of outputs/

teams/                     CrewAI agent definitions (one per role)
  t1_manager.py              Memory + cost tracking + history tools
  t2_visual.py               Image analyzer, catalog extractor, image-to-code
  t3_arsip.py                Vault save/search/index (LanceDB)
  t4_admin.py                Word/Excel/PDF generators, data analysis, chart
  t5_intel.py                Web scraping, OSINT, browser-use, Sherlock, ImageSearch
  t6_lifestyle.py            YouTube, weather, schedule, maps
  t7_seniman.py              Dashboard/SVG/Mermaid/HTML generators
  t7_html_templates.py       HTML render templates
  t8_mekanik.py              Code executor, file saver, git automation, security scanner
  t9_saham.py                Stock tools (yfinance)

tools/                     Shared BaseTool implementations
  image_gen_tool.py          Text-to-image + image-to-image (Gemini Flash Image)
  image_search_tool.py       Wikimedia/Serper image search + download
  sherlock_tool.py           OSINT username scan
  video_gen_tool.py          OpenRouter Kling video gen
  browser_use_tool.py        Interactive browser automation
  prompt_optimizer.py        Prompt rewrite/critique
  repo_rag_tools.py          Codebase RAG (BM25 + vector)
  deslop_tool.py             Anti-AI slop prose filter (stop-slop)
  plugins/                   Hot-loadable plugins (rust_search, etc.)

whatsapp/                  Node.js WA bridge
  index.js                   whatsapp-web.js client + STT arming logic

dashboard/                 React JSX pixel-art frontend
frontend/                  Tauri 2.x desktop sidebar
Bima_Vault/                Obsidian-compatible notes (RAG corpus)
vault_index/ + search_index/  LanceDB + tantivy indices
outputs/                   Generated files (auto-pruned)
assets/                    Static assets (TTS reference audio, F5-TTS cache)
```

## Common commands

```bash
# Activate venv (always do this first in WSL Ubuntu)
source bima_env/bin/activate

# PM2 process management
pm2 list                           # Status of anisa-v3, bima-whatsapp, bima-tunnel
pm2 logs anisa-v3 --lines 50       # Stream backend logs
pm2 logs anisa-v3 --nostream       # Last logs without tailing
pm2 restart anisa-v3 --update-env  # Reload Python backend with fresh .env
pm2 restart bima-whatsapp          # Reload WA bridge after editing whatsapp/index.js
pm2 save                           # Persist process list for auto-resurrect

# Restart matrix
# Edited core/, teams/, tools/, requirements.txt → pm2 restart anisa-v3
# Edited whatsapp/index.js                       → pm2 restart bima-whatsapp
# Edited both                                    → pm2 restart anisa-v3 bima-whatsapp

# Syntax / import smoke test
python3 -c "import ast; ast.parse(open('path.py').read()); print('AST OK')"
python3 -c "from module import X; print('import OK')"

# Node syntax check
node --check whatsapp/index.js

# View logs by tag
pm2 logs anisa-v3 --nostream | grep -iE 'STT|TTS|API_RETRY|CLASSIFIER|LANGGRAPH'

# Health check
python healthcheck.py
```

## Channel-specific behavior

### Discord

- Mention `@Anisa` in a channel, OR any DM, OR text command (`!play`, `!saham`, `!qc`, `!ocr`, `!status`, music commands).
- Audio attachment (`.ogg/.oga/.opus/.mp3/.m4a/.wav/.flac/.aac`) → auto-transcribed (no arming, intent implicit).
- Image attachment + prompt with "bikin gambar variasi" → image-to-image via Seniman.
- Music commands need bot voice perms: `Connect`, `Speak`, `Use Voice Activity`.

### WhatsApp (via Node bridge)

- All commands prefixed `/bot` (configurable via `WA_TRIGGER`).
- Voice notes are silent-ignored by default. Must arm first: `/bot stt` (or aliases: `tts`, `voice`, `suara`, `v`, `note`, `vn`). TTL 60s, auto-disarm after 1 voice used.
- Audio file attachments via paperclip (with `/bot` caption) → auto-transcribed without arming.

## Voice pipeline

### STT (input → text)

- Engine: `faster-whisper small` (multilingual, Indonesian primary).
- First call downloads model (~390MB) to `~/.cache/huggingface`.
- Tuned with `vad_filter=True`, `beam_size=8`, Indonesian `initial_prompt` for short-utterance accuracy.
- Wrapper: `core/stt.py` — lazy singleton, returns empty string on failure.

### TTS (text → audio)

- **Primary**: F5-TTS Indo V2 (`Eempostor/F5-TTS-INDO-FINETUNE-V2` on HuggingFace). Checkpoint cached in `assets/f5_tts_cache/` (~1.2GB).
- **Fallback**: edge-tts `id-ID-GadisNeural` if F5-TTS unavailable/fails.
- Output: OGG/Opus via ffmpeg (Discord & WA voice note compatible).
- Reference audio: `assets/tts_ref.wav` (placeholder seed for voice cloning).
- Env: `TTS_DEVICE=cuda|cpu`, `TTS_VOICE`, `TTS_HF_REPO`, `TTS_REF_AUDIO`, `TTS_REF_TEXT`, `TTS_BASE_MODEL`.
- Smart filter: reply ≤ 300 chars → voice only; > 300 chars → text + 1-line voice summary.

### Auto-mirror

Voice in → voice out, text in → text out. No user toggle.

## Gotchas / Hard-learned lessons

### CUDA / GPU diagnosis discipline

The PyTorch warning `CUDA initialization: The NVIDIA driver on your system is too old` is **misleading**. Before suggesting a driver update:

1. Run `nvidia-smi` — get Driver Version and CUDA Version supported.
2. Run `python -c "import torch; print(torch.version.cuda)"` — get the CUDA torch was compiled against.
3. Compare: `torch.version.cuda` must be ≤ `nvidia-smi CUDA Version`. If torch is newer than driver, the fix is to reinstall torch with a matching wheel (`pip install torch --index-url https://download.pytorch.org/whl/cu128`), NOT update the driver.

### MCP / tool audit discipline

Before suggesting a new MCP server or CrewAI tool, **grep every existing `BaseTool` in `tools/` and `teams/*.py`** plus every `tools=[...]` list. Many capabilities already exist as custom tools — adding duplicates causes decision paralysis for the agent. `config_mcp.json` alone is not enough; many tools are inline in team definitions.

### WSL networking

- `pip install` over WSL is flaky for large CUDA wheels (SSL decryption errors). Retry with `--timeout 180 --retries 8`, or `wsl --shutdown` and try again.
- After Windows NVIDIA driver update, run `wsl --update` + `wsl --shutdown` in PowerShell to refresh WSL CUDA bridge.
- WSL `--shutdown` resets PM2 daemon — restart all processes with `pm2 start ecosystem.config.js` after.

### Output discipline (Bima preference)

- End each task with 5-line max factual summary. No "" / "Perfect!" / "Done!".
- For long output, write to a file instead of dumping in chat.
- Use markdown link `[file.py:42](file.py#L42)` syntax for code references in IDE-rendered output.

### MCP integration

- `config_mcp.json` controls MCP servers attached to specific agents.
- After editing, restart `anisa-v3` (the `MCPClientManager` reloads on startup).
- Enabled by default: `fetch`, `markitdown`, `sequential_thinking`, `memory_anthropic`, `time`, `sqlite`, `git`.
- Disabled config-only: `duckduckgo` (redundant w/ SerperDevTool), `playwright` (redundant w/ BrowserUseTool), `filesystem`, `github`, `searxng`.

### Anti-AI Slop (Stop-Slop)

Sistem anti-slop terintegrasi di 4 titik untuk memastikan output Anisa tidak terdengar robotik:

1. **`tools/deslop_tool.py`** — `DeslopTool` (CrewAI BaseTool). Agen bisa panggil tool ini untuk menyaring draf tulisan dari AI tells / slop sebelum publish.
2. **`core/threads_commands.py`** — Aturan anti-slop disisipkan di `apply_smart_revision()` system prompt, otomatis aktif saat revisi draf postingan Threads.
3. **`teams/t4_admin.py`** — Aturan anti-slop ada di backstory `admin_agent`, aktif saat generate dokumen PDF/Word/Excel.
4. **`core/langgraph_nodes/manager.py`** — Aturan anti-slop ada di system prompt `manager_node`, aktif saat Anisa menjawab chat biasa.

**Frasa terlarang (Bahasa Indonesia):** "di era digital", "solusi terbaik", "berkomitmen untuk", "tidak hanya itu", "secara keseluruhan", "menawarkan kemudahan", "Tentu saja,", "Perlu dicatat bahwa".

**Prinsip utama:** Kalimat aktif, langsung ke poin, tanpa pembuka basa-basi (*throat-clearing*), tanpa kontras biner klise ("Bukan X, melainkan Y").

Referensi asal: [hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop). Lihat juga `error_solutions.md` Log 9.

## Test commands

There's no formal pytest suite. Smoke testing pattern:

1. `python3 -c "import ast; ast.parse(open('FILE.py').read())"` — syntax check
2. `python3 -c "from MODULE import X"` — import resolution
3. End-to-end test by sending a message via Discord or WA (`/bot ping` for backend health)

For external API call sites, use `core/api_retry.py:call_with_retry()` to wrap with stamina retry instead of ad-hoc try/except.

## Quick links

- [README.md](README.md) — public-facing project overview, install, deployment
- [claude.md](claude.md) — full operating rules (mandatory)
- [Rules for agent.md](Rules%20for%20agent.md) — same rules (kept in sync)
- [config_mcp.json](config_mcp.json) — MCP server map
- [ecosystem.config.js](ecosystem.config.js) — PM2 process definitions
- [requirements.txt](requirements.txt) — Python deps

## When in doubt

Ask Bima. He wrote the rules deliberately. He'd rather you ask than guess wrong.

masukan semua kesalahan dan solusi nya ke file error_solutions.md
