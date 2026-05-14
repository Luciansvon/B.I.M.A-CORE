/* GUILD API — FastAPI + WebSocket bridge to BIMA_CORE dashboard_server.py
   ─────────────────────────────────────────────────────────────────────
   Auto-detects backend at window.location.origin. If unreachable (e.g. opened
   via file://), falls back to simulation mode — every helper resolves to
   a stub so the UI keeps animating.

   Endpoints used:
     GET  /api/metrics           — uptime + per-agent counters
     GET  /api/sprints           — non-idle agents
     GET  /api/layout            — furniture layout (server-side, shared)
     POST /api/layout            — save layout
     POST /api/command           — kirim perintah ke LangGraph
     GET  /api/command/status    — running flag
     WS   /ws                    — live events: agent_state, command_*, reset

   Backend agent ids differ from pixel ones — translated via BACKEND_TO_PIXEL.
*/

const API_BASE = (() => {
  if (typeof window === 'undefined') return '';
  // Same origin (FastAPI serves /dashboard) OR explicit override via ?api=
  const params = new URLSearchParams(window.location.search);
  const override = params.get('api');
  if (override) return override.replace(/\/$/, '');
  if (window.location.protocol === 'file:') return 'http://localhost:8000';
  return window.location.origin;
})();

const WS_URL = API_BASE.replace(/^http/, 'ws') + '/ws';

// Backend ↔ pixel id translation (langgraph_nodes/ vs guild-data.jsx).
const BACKEND_TO_PIXEL = {
  manager:   'anisa',
  lifestyle: 'life',
  intel:     'intel',
  visual:    'visual',
  arsip:     'arsip',
  mekanik:   'mekanik',
  seniman:   'seniman',
  admin:     'admin',
};
const PIXEL_TO_BACKEND = Object.fromEntries(
  Object.entries(BACKEND_TO_PIXEL).map(([b, p]) => [p, b])
);

// Backend state → pixel agentPos.status.
const STATE_MAP = {
  idle:     'idle',
  working:  'working',
  thinking: 'busy',
  talking:  'idle',
  error:    'error',
};

function pixelizeMetrics(snapshot) {
  if (!snapshot || !snapshot.agents) return { uptime: 0, agents: {} };
  const out = {};
  for (const [bid, info] of Object.entries(snapshot.agents)) {
    const pid = BACKEND_TO_PIXEL[bid] || bid;
    out[pid] = {
      task_count: info.task_count || 0,
      error_count: info.error_count || 0,
      avg_ms: info.avg_duration_ms || 0,
      last_active: info.last_active,
      status: STATE_MAP[info.current_state] || 'idle',
    };
  }
  return {
    uptime: snapshot.uptime_seconds || 0,
    active_subscribers: snapshot.active_subscribers || 0,
    agents: out,
  };
}

// ── Plain HTTP helpers ──────────────────────────────────────────
async function _fetch(path, opts = {}) {
  const r = await fetch(API_BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function apiPing() {
  try {
    await _fetch('/api/metrics');
    return true;
  } catch (e) {
    return false;
  }
}

async function apiMetrics()  { return pixelizeMetrics(await _fetch('/api/metrics')); }
async function apiSprints()  { return _fetch('/api/sprints'); }
async function apiCommand(command) {
  return _fetch('/api/command', { method: 'POST', body: JSON.stringify({ command }) });
}
async function apiCommandStatus() { return _fetch('/api/command/status'); }
async function apiGetLayout() {
  const r = await _fetch('/api/layout');
  return r.layout || {};
}
async function apiSaveLayout(layout) {
  return _fetch('/api/layout', { method: 'POST', body: JSON.stringify({ layout }) });
}

// ── WebSocket manager (singleton, auto-reconnect) ───────────────
const _wsListeners = new Set();
let _ws = null;
let _wsState = 'idle';   // idle | connecting | open | closed
let _wsReconnectTimer = null;
let _wsBackoff = 1000;

function _wsBroadcast(msg) {
  for (const fn of _wsListeners) {
    try { fn(msg); } catch (e) { /* swallow */ }
  }
}

function wsConnect() {
  if (_wsState === 'connecting' || _wsState === 'open') return;
  _wsState = 'connecting';
  try {
    _ws = new WebSocket(WS_URL);
  } catch (e) {
    _wsState = 'closed';
    _scheduleReconnect();
    return;
  }
  _ws.addEventListener('open', () => {
    _wsState = 'open';
    _wsBackoff = 1000;
    _wsBroadcast({ type: '__ws_open' });
  });
  _ws.addEventListener('message', (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    _wsBroadcast(msg);
  });
  _ws.addEventListener('close', () => {
    _wsState = 'closed';
    _wsBroadcast({ type: '__ws_close' });
    _scheduleReconnect();
  });
  _ws.addEventListener('error', () => {
    try { _ws.close(); } catch (e) {}
  });
}

function _scheduleReconnect() {
  if (_wsReconnectTimer) return;
  const delay = Math.min(_wsBackoff, 30000);
  _wsReconnectTimer = setTimeout(() => {
    _wsReconnectTimer = null;
    _wsBackoff = Math.min(_wsBackoff * 2, 30000);
    wsConnect();
  }, delay);
}

function wsSubscribe(handler) {
  _wsListeners.add(handler);
  return () => _wsListeners.delete(handler);
}

function wsState() { return _wsState; }

// ── React hooks ────────────────────────────────────────────────
// Single shared "is backend alive" flag. Re-checks every 30s while alive,
// every 10s while dead so reconnect feels snappy.
function useBackendOnline() {
  const [online, setOnline] = React.useState(null); // null = unknown
  React.useEffect(() => {
    let dead = false;
    let timer;
    const check = async () => {
      const ok = await apiPing();
      if (dead) return;
      setOnline(ok);
      timer = setTimeout(check, ok ? 30000 : 10000);
    };
    check();
    return () => { dead = true; if (timer) clearTimeout(timer); };
  }, []);
  return online;
}

// Subscribe to a single WS event type. Re-subscribes if handler ref changes.
function useWsEvent(type, handler) {
  React.useEffect(() => {
    if (_wsState === 'idle' || _wsState === 'closed') wsConnect();
    const off = wsSubscribe((msg) => {
      if (!type || type === '*' || msg.type === type) handler(msg);
    });
    return off;
  }, [type, handler]);
}

// Periodic poll. Bypassed when backend is offline.
function useApiPoll(fn, intervalMs, deps = []) {
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState(null);
  React.useEffect(() => {
    let dead = false;
    let timer;
    const tick = async () => {
      try {
        const v = await fn();
        if (dead) return;
        setData(v);
        setError(null);
      } catch (e) {
        if (!dead) setError(e);
      } finally {
        if (!dead) timer = setTimeout(tick, intervalMs);
      }
    };
    tick();
    return () => { dead = true; if (timer) clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error };
}

// ── Layout: hybrid (server source of truth, localStorage offline cache) ──
const LS_LAYOUT_CACHE = 'anisa_positions';

async function loadLayoutHybrid() {
  // Try server first; fall back to cache; merge SEED_POSITIONS at the bottom.
  let server = null;
  try { server = await apiGetLayout(); } catch (e) { /* offline */ }
  let cached = {};
  try {
    const raw = localStorage.getItem(LS_LAYOUT_CACHE);
    if (raw) cached = JSON.parse(raw);
  } catch (e) {}
  const seed = (typeof SEED_POSITIONS !== 'undefined') ? SEED_POSITIONS : {};
  const merged = { ...seed, ...cached, ...(server || {}) };
  // Refresh local cache from server snapshot if we got one.
  if (server) {
    try { localStorage.setItem(LS_LAYOUT_CACHE, JSON.stringify(server)); } catch (e) {}
  }
  return merged;
}

let _layoutSaveTimer = null;
function saveLayoutHybrid(layout) {
  // Always cache locally (synchronous, instant).
  try { localStorage.setItem(LS_LAYOUT_CACHE, JSON.stringify(layout)); } catch (e) {}
  // Debounce server write (drag emits many updates per second).
  if (_layoutSaveTimer) clearTimeout(_layoutSaveTimer);
  _layoutSaveTimer = setTimeout(() => {
    apiSaveLayout(layout).catch(() => { /* offline, cache survives */ });
  }, 600);
}

Object.assign(window, {
  API_BASE, WS_URL, BACKEND_TO_PIXEL, PIXEL_TO_BACKEND, STATE_MAP,
  pixelizeMetrics,
  apiPing, apiMetrics, apiSprints, apiCommand, apiCommandStatus,
  apiGetLayout, apiSaveLayout,
  wsConnect, wsSubscribe, wsState,
  useBackendOnline, useWsEvent, useApiPoll,
  loadLayoutHybrid, saveLayoutHybrid,
});
