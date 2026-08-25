# BIMA_CORE

BIMA_CORE adalah runtime multi-agent bernama Anisa untuk otomasi personal melalui Discord, WhatsApp, dashboard web, dan REST API. Pesan dirutekan oleh LangGraph ke agent spesialis CrewAI, lalu hasil dikembalikan sebagai teks atau artefak seperti dokumen, gambar, audio, dan laporan.

## Fitur Utama

- Discord bot dengan command, attachment, musik, STT, dan TTS opsional.
- WhatsApp bridge berbasis `whatsapp-web.js` dengan endpoint FastAPI lokal.
- Dashboard FastAPI + WebSocket untuk status, output, command, dan observasi layar.
- Agent spesialis untuk riset, arsip Obsidian, dokumen, visual, lifestyle, kode, saham, dan repo RAG.
- LangGraph checkpoint per event loop menggunakan SQLite.
- Penyimpanan semantik melalui LanceDB dan sidecar AgentMemory opsional.
- Scheduler APScheduler untuk saham, Threads, maintenance, dan observability.
- Tool dokumen Office/Word/PDF, DuckDB read-only, OCR, browser automation, dan security scan opt-in.

Detail flow dan boundary ada di [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Default Runtime

- Routing model dipusatkan di `core/model_router.py`; request harian memakai profil hemat, sedangkan visual, riset, coding berat, dan security memakai model spesialis.
- TTS nonaktif untuk pemakaian harian melalui `ENABLE_TTS=false`; konfigurasi STT tidak ikut dimatikan.
- Music Discord memakai `yt-dlp` minimum 2026.8.19 dan client YouTube Android tanpa mengambil cookie browser.
- Startup MCP berjalan non-blocking supaya kegagalan tool opsional tidak menahan Discord, WhatsApp, atau dashboard.

## Kebutuhan

- WSL Ubuntu atau Linux.
- Python `>=3.12,<3.13` sesuai `pyproject.toml` dan CI.
- Node.js + npm untuk WhatsApp bridge.
- `ffmpeg` untuk audio.
- PM2 dan `cloudflared` untuk deployment production saat dipakai.
- Docker + `uvx` hanya untuk Strix security scan opsional.

## Instalasi

```bash
git clone https://github.com/Luciansvon/B.I.M.A-CORE.git
cd B.I.M.A-CORE

python3.12 -m venv bima_env
bima_env/bin/pip install -r requirements.txt
bima_env/bin/pip install -r requirements-dev.txt
npm ci --prefix whatsapp
cp .env.example .env
```

Isi `.env` memakai credential milikmu. Jangan commit file tersebut. Daftar variable dan nilai contoh aman berada di `.env.example`.

Konfigurasi inti yang biasanya dibutuhkan:

```env
OPENROUTER_API_KEY=your_openrouter_key
DISCORD_TOKEN=your_discord_token
WA_BRIDGE_TOKEN=your_internal_bridge_token
DASHBOARD_API_TOKEN=your_dashboard_token
OBSIDIAN_PATH=/path/to/your/vault
```

## Menjalankan Lokal

```bash
source bima_env/bin/activate
bima_env/bin/python scripts/healthcheck.py
bima_env/bin/python main.py
```

`main.py` menjalankan Discord bot, WA FastAPI bridge pada port `8001`, dan dashboard FastAPI pada port `8000` secara default.

## Test dan Check

```bash
bima_env/bin/python -m pytest -q --no-header
bima_env/bin/python -m pytest tests/test_qc.py -q
node --check whatsapp/index.js
```

CI memakai Python 3.12 dan menjalankan `uv sync --locked --only-group ci`, lalu seluruh pytest suite.

## Production dengan PM2

```bash
pm2 start ecosystem.config.js
pm2 save
pm2 list
```

Service yang didefinisikan di `ecosystem.config.js`:

- `anisa-v3` — runtime Python utama.
- `bima-whatsapp` — WhatsApp Web bridge.
- `bima-tunnel` — Cloudflare Tunnel menuju dashboard lokal.
- `anisa-status` — collector status runtime.
- `agentmemory` — sidecar opsional ketika `AGENTMEMORY_ENABLED=true`.

## Struktur Repository

```text
main.py                    Entry point
core/                      Runtime dan channel handlers
core/langgraph_nodes/      Node dan state LangGraph
teams/                     CrewAI agents
tools/                     Shared tools dan plugin
tests/                     Pytest suite
whatsapp/                  Node.js bridge
dashboard/                 Dashboard frontend
services/                  Runtime sidecars
scripts/                   Healthcheck dan utility
docs/                      Dokumentasi teknis
outputs/                   Artefak hasil runtime
```

## Dokumentasi

- [Aturan coding agent](AGENTS.md)
- [Arsitektur](docs/ARCHITECTURE.md)
- [Error dan solusi](docs/ERROR_SOLUTIONS.md)
- [Status pekerjaan](docs/WORKLOG.md)
