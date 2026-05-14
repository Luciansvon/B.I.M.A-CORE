# Guild Hall Arenwood — Pixel Dashboard

Pixel-art alternate skin untuk monitoring B.I.M.A guild. Setiap agent
direpresentasikan sebagai adventurer (Ranger, Seer, Engineer, dst) yang
beraksi di guild hall medieval bertingkat tiga. Semua data hidup ditarik
dari `core/dashboard_server.py` lewat HTTP + WebSocket; kalau backend
nggak nyala, dashboard fallback ke mode simulasi yang tetap animatif.

> Standar dashboard produksi tetap `frontend/dashboard.html` (rute `/dashboard`).
> Dashboard ini dijalanin paralel di rute `/dashboard/v3`.

## Cara jalanin

### Lewat B.I.M.A core (rekomendasi — full live data)

```powershell
# di root repo
python -m core.discord_bot   # ATAU script yang manggil dashboard_server.start_in_background()
# lalu buka browser:
#   http://localhost:8000/dashboard/v3
```

Begitu connect, dashboard auto-detect backend lewat `GET /api/metrics`,
buka WebSocket `/ws`, dan mulai konsumsi event real (agent state, command
progress/response, reset). Layout furniture juga sync ke server lewat
`/api/layout`, jadi posisi sama di semua device.

### Standalone (offline preview)

```powershell
# di folder ini
python -m http.server 8080
# buka http://localhost:8080/guild.html
```

Atau buka `guild.html` langsung di browser via `file://` — Babel-standalone
tetap parse, tapi sebagian browser blok cross-file `<script src>` lewat
file://. Lebih aman pakai http server. Mode offline jalanin simulasi
event + log sendiri.

Override backend URL: `?api=http://other-host:8000`.

## Arsitektur file

| File | Tugas |
|---|---|
| `guild.html` | Entry. Load 11 file JSX via Babel-standalone, render `<GuildApp />`. |
| `tweaks-panel.jsx` | `useTweaks` hook + floating panel + form helpers (slider/radio/toggle/dst). Speak ke editor host via `postMessage`. |
| `guild-data.jsx` | Static data: `AGENTS`, `PETS`, `FLOORS`, `INVENTORY`, log templates, util `pick/rint/fmtTime/genLog`. |
| `guild-state.jsx` | LocalStorage layer: `loadAgents/saveAgents`, `loadPositions/savePositions`, seed default, daily reset, `touchAgent`, `relTime`. |
| `guild-api.jsx` | **HTTP + WebSocket bridge ke FastAPI.** `apiCommand`, `apiMetrics`, layout sync, hooks `useBackendOnline / useWsEvent / useApiPoll`. ID translation backend ↔ pixel. |
| `guild-sprites.jsx` | `PixelSprite` renderer + sprite grids agent (chibi/tall). |
| `guild-furniture.jsx` | Sprite & catalog furniture (server rack, projector, filing cabinet, dst) + `lookupFurniture(id)`. |
| `guild-pets.jsx` | Slime / Baby Dragon / Cat sprites + `usePets` wandering hook. |
| `guild-interactions.jsx` | Per-agent signature (aura, idle quotes, actions), `MoodRing`, `QuestBar`, `ContextMenu`, `ParticleBurst`, `DelegationLine`, `makeQuest`, `initMoods`. |
| `guild-scene.jsx` | `Stage` — diorama, floor patterns, ambient agents, weather particles, edit-mode drag delegation, render furniture & pets. |
| `guild-panels.jsx` | Right side: Activity log, Inventory grid, Vault stats, Chat ke Anisa. |
| `guild-app.jsx` | `GuildApp` top-level orchestrator: state, useTweaks, WS subscriptions, top bar, bottom HUD, popover, context menu, toasts. |

Semua file expose API-nya lewat `Object.assign(window, { ... })` —
nggak ada bundler, nggak ada `import`. IDE bakal kasih warning "name not
found"; ignore aja, runtime aman.

## Backend integration (guild-api.jsx)

| Backend | Frontend |
|---|---|
| `GET /api/metrics` | `useApiPoll(apiMetrics, 3000)` → driver Bottom HUD (events, latency, uptime, active count). |
| `GET /api/sprints` | (opsional, belum di-wire) |
| `GET /api/layout` | `loadLayoutHybrid()` saat mount — server menang dari cache lokal. |
| `POST /api/layout` | `saveLayoutHybrid()` debounced 600 ms tiap drag selesai. |
| `POST /api/command` | Chat panel kirim perintah ke LangGraph engine. |
| `WS /ws` event `connected` / `history` | Replay 80 event terakhir → log rows. |
| `WS /ws` event `agent_state` | Update `agentPos[pid].status` + push log row. |
| `WS /ws` event `command_progress` | Update busy indicator di chat. |
| `WS /ws` event `command_response` | Render reply Anisa di chat + close busy. |
| `WS /ws` event `reset` | Log row `[reset] ...`. |

WebSocket auto-reconnect dengan backoff 1 s → 30 s. Backend ping check
30 s saat online, 10 s saat offline.

### ID translation

Backend `langgraph_nodes/` pakai id berbeda dari pixel dashboard:

| Backend | Pixel |
|---|---|
| `manager` | `anisa` |
| `lifestyle` | `life` |
| `intel`, `visual`, `arsip`, `mekanik`, `seniman`, `admin` | (sama) |
| _(none)_ | `bima` — represent **user**, bukan agent backend |

Mapping di `BACKEND_TO_PIXEL` dan `STATE_MAP` (state `working`/`thinking`/
`talking`/`idle`/`error` → `working`/`busy`/`idle`/`idle`/`error`).

## Persistence

| Key | Lokasi | Isi |
|---|---|---|
| `anisa_positions` | localStorage | Cache offline furniture + char positions. Sinkron ke server saat online. |
| `anisa_agents_state` | localStorage | Per-agent: mood, total_tasks, tasks_today, errors_today, last_date, last_interaction. Daily auto-reset. |
| `anisa_chat_history` | localStorage | 100 pesan chat terakhir. |
| `frontend/furniture_layout.json` | server (FastAPI) | Source of truth layout, diakses lintas-device via `/api/layout`. |

Server-side selalu menang saat startup; localStorage jadi cache untuk
offline. Save call menulis ke dua-duanya.

## Tweaks (URL: tombol ✎ EDIT pojok kanan-bawah)

| Tweak | Nilai | Efek |
|---|---|---|
| `mode` | day / night / storm / neon | `body[data-mode]` cascade variabel CSS. |
| `weather` | clear / rain / storm / snow / comet / dust | Particle layer di Stage. |
| `tilePattern` | stone / wood-plank / checker / dungeon | Floor tiling. |
| `spriteStyle` | chibi / tall | Agent sprite grid. |
| `chatSide` | left / right / bottom | Posisi panel kanan. |
| `hudDensity` | minimal / rich | Jumlah cell HUD bawah. |
| `ambientAgents` | bool | Wandering agents. |
| `scanlines` | bool | CRT overlay. |

Default ada di `TWEAK_DEFAULTS` (`guild-app.jsx`) — diapit `/*EDITMODE-BEGIN*/`
& `/*EDITMODE-END*/` supaya bisa di-rewrite host editor lewat
`__edit_mode_set_keys` postMessage.

## Edit furniture

Tombol `✎ EDIT` di top bar → click & drag furniture / agent untuk pindah
posisi. Auto-save lokal + server (debounced). `↺ RESET` ngosongin
positions lalu reload.

## Limitasi

1. **Floor 2 (War Room) dan Floor 3 (Tower Roost)** belum penuh diisi — Floor 1 (Guild Hall) lengkap.
2. **Inventory dan Vault tab** masih placeholder data static (belum dikoneksikan ke `/api/memory`, `/api/outputs`).
3. **Toast simulasi** tetap jalan karena belum ada channel toast langsung dari backend.
4. **`window.parent.postMessage`** dari tweaks-panel ke host editor — kalau jalan di tab biasa, no-op (silent).

## TODO follow-up

- Wire `InventoryPanel` ke `GET /api/outputs?limit=12` (loot = file output terbaru).
- Wire `VaultPanel` ke `GET /api/memory` (facts, sessions count).
- Floor 2/3 scenes lengkap (table + map untuk War Room, fireplace + lounge untuk Tower Roost).
- Bundle prod via `bundle.py` → `guild-bundle.jsx` (single Babel parse, lebih cepat cold-load).
