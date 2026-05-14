/* GUILD STATE — persistent agent state + position storage
   matches Anisa's real schema:
   - per-agent: { mood, total_tasks, tasks_today, errors_today, last_date, last_interaction }
   - positions: { id: { left, top } }    (id = "char-<agent>" or "furn-<type>-<n>" or "window")
   ──────────────────────────────────────────────────────────────────── */

const LS_AGENTS = 'anisa_agents_state';
const LS_POSITIONS = 'anisa_positions';

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function nowSec() { return Date.now() / 1000; }

function defaultAgentState() {
  return {
    mood: 100,
    total_tasks: 0,
    tasks_today: 0,
    errors_today: 0,
    last_date: todayStr(),
    last_interaction: nowSec(),
  };
}

// initial position seeds (used if localStorage is empty for that id).
// Matches the data the user provided, plus reasonable defaults for the rest.
const SEED_POSITIONS = {
  // furniture (positions in % within stage)
  'furn-obj-24':              { left: '11.4073%', top: '-9.96273%' },
  'furn-projector-screen-25': { left: '41.1541%', top: '-0.0076867%' },
  'window':                   { left: '70%',      top: '4%' },
  'furn-obj-35':              { left: '-5.7699%', top: '-2.70393%' },
  'furn-bin-50':              { left: '93.0898%', top: '13.1714%' },
  'furn-server-rack-37':      { left: '24.6372%', top: '19.3692%' },
  'furn-filing-cabinet-40':   { left: '44.0329%', top: '32.0258%' },
  'furn-elevator-door-fl-8':  { left: '88%',      top: '50%' },
  // character starting positions (will fall back to AGENTS.x/y if not set)
  'char-anisa':   { left: '18%', top: '38%' },
  'char-intel':   { left: '22%', top: '70%' },
  'char-visual':  { left: '32%', top: '70%' },
  'char-arsip':   { left: '42%', top: '70%' },
  'char-life':    { left: '52%', top: '70%' },
  'char-mekanik': { left: '41.4761%', top: '53.3883%' },
  'char-seniman': { left: '86.2321%', top: '89.7324%' },
  'char-admin':   { left: '82%', top: '70%' },
};

function loadAgents() {
  try {
    const raw = localStorage.getItem(LS_AGENTS);
    const stored = raw ? JSON.parse(raw) : {};
    const today = todayStr();
    const out = {};
    for (const a of AGENTS) {
      const s = { ...defaultAgentState(), ...(stored[a.id] || {}) };
      // daily reset
      if (s.last_date !== today) {
        s.tasks_today = 0;
        s.errors_today = 0;
        s.last_date = today;
      }
      out[a.id] = s;
    }
    return out;
  } catch (e) {
    return Object.fromEntries(AGENTS.map(a => [a.id, defaultAgentState()]));
  }
}

function saveAgents(state) {
  try { localStorage.setItem(LS_AGENTS, JSON.stringify(state)); } catch (e) {}
}

function loadPositions() {
  try {
    const raw = localStorage.getItem(LS_POSITIONS);
    const stored = raw ? JSON.parse(raw) : {};
    return { ...SEED_POSITIONS, ...stored };
  } catch (e) {
    return { ...SEED_POSITIONS };
  }
}

function savePositions(positions) {
  try { localStorage.setItem(LS_POSITIONS, JSON.stringify(positions)); } catch (e) {}
}

// helpers to convert percent strings to numbers and back
function pctToNum(s) {
  if (typeof s === 'number') return s;
  if (!s) return 0;
  return parseFloat(String(s).replace('%',''));
}
function numToPct(n) { return `${n}%`; }

// touch agent (record an interaction)
function touchAgent(state, agentId, { mood_delta = 0, task = false, error = false } = {}) {
  const today = todayStr();
  const a = state[agentId] || defaultAgentState();
  const next = {
    ...a,
    mood: Math.max(0, Math.min(100, a.mood + mood_delta)),
    last_interaction: nowSec(),
    last_date: today,
  };
  if (a.last_date !== today) {
    next.tasks_today = 0;
    next.errors_today = 0;
  }
  if (task)  { next.total_tasks = (a.total_tasks || 0) + 1; next.tasks_today = (next.tasks_today || 0) + 1; }
  if (error) { next.errors_today = (next.errors_today || 0) + 1; }
  return { ...state, [agentId]: next };
}

// format "last_interaction" as relative time
function relTime(ts) {
  if (!ts) return '—';
  const diff = nowSec() - ts;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

Object.assign(window, {
  LS_AGENTS, LS_POSITIONS, SEED_POSITIONS,
  defaultAgentState, loadAgents, saveAgents, loadPositions, savePositions,
  pctToNum, numToPct, touchAgent, relTime, todayStr, nowSec,
});
