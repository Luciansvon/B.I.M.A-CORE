/* GUILD INTERACTIONS — per-agent signatures, moods, quests, menus
   ──────────────────────────────────────────────────────────────── */

// ── Per-agent signature data ───────────────────────────────
const AGENT_SIGNATURES = {
  bima: {
    aura: '#fcd34d',
    idleQuotes: ['Anisa, status tim?', 'Guild bergerak.', 'Lord Bima hadir.', '♛ Visi besar, eksekusi tegas.', 'Anisa, lapor.'],
    idleEmoji: ['♛','★','◆'],
    actions: [
      { id: 'command', label: 'Issue command', icon: '♛' },
      { id: 'rally',   label: 'Rally guild',   icon: '★' },
      { id: 'dispatch',label: 'Order Anisa',   icon: '◆' },
    ],
  },
  anisa: {
    aura: '#fcd34d',
    idleQuotes: ['Perintah Lord Bima diterima.', 'Tim sehat? ✦', 'Bima, ada perintah?', 'Koordinasi siap.', 'Quest paralel jalan.'],
    idleEmoji: ['◆','✦','★'],
    actions: [
      { id: 'dispatch', label: 'Dispatch quest', icon: '✦' },
      { id: 'standup',  label: 'Call standup',   icon: '◆' },
      { id: 'praise',   label: 'Beri pujian',    icon: '★' },
    ],
  },
  intel: {
    aura: '#22d3ee',
    idleQuotes: ['Sumber baru, 3 jejak.', 'Map area aman.', 'Ada signal kredibel.', 'OSINT loaded.'],
    idleEmoji: ['✦','◎','▸'],
    actions: [
      { id: 'scout',  label: 'Send scout',     icon: '✦' },
      { id: 'osint',  label: 'OSINT scan',     icon: '◎' },
      { id: 'silent', label: 'Mode siluman',   icon: '▸' },
    ],
  },
  visual: {
    aura: '#f97316',
    idleQuotes: ['12 halaman, 3 tabel.', 'Aku lihat polanya.', 'Artefak terbaca.', 'Visi datang...'],
    idleEmoji: ['◉','✧','◇'],
    actions: [
      { id: 'inspect', label: 'Inspect artifact', icon: '◉' },
      { id: 'ocr',     label: 'OCR document',     icon: '✎' },
      { id: 'scry',    label: 'Scry future',      icon: '✧' },
    ],
  },
  arsip: {
    aura: '#a3e635',
    idleQuotes: ['Rak 4, baris 12.', 'Hafal semua.', 'Index up to date.', 'Backup OK.'],
    idleEmoji: ['⌘','◫','⊞'],
    actions: [
      { id: 'recall', label: 'Recall memory',    icon: '⌘' },
      { id: 'backup', label: 'Backup vault',     icon: '◫' },
      { id: 'index',  label: 'Reindex archive',  icon: '⊞' },
    ],
  },
  life: {
    aura: '#fde047',
    idleQuotes: ['Resto 4.7 ★.', '♪ ♫ ♪', 'Tiket murah ada.', 'Vibes check.'],
    idleEmoji: ['♪','♫','★'],
    actions: [
      { id: 'recommend', label: 'Rekomendasi',  icon: '★' },
      { id: 'play',      label: 'Putar musik',  icon: '♪' },
      { id: 'book',      label: 'Pesan tiket',  icon: '✈' },
    ],
  },
  mekanik: {
    aura: '#dc2626',
    idleQuotes: ['Bug di line 142.', 'Patched. ✓', '3 retry, lulus.', 'Compiling...'],
    idleEmoji: ['⚙','✦','▣'],
    actions: [
      { id: 'debug',    label: 'Run debug',       icon: '⚙' },
      { id: 'refactor', label: 'Refactor code',   icon: '▣' },
      { id: 'deploy',   label: 'Deploy build',    icon: '▸' },
    ],
  },
  seniman: {
    aura: '#f472b6',
    idleQuotes: ['Sketch v3 jadi.', 'Pilih palette.', 'Brush stroke...', '✿ created.'],
    idleEmoji: ['✿','◈','✧'],
    actions: [
      { id: 'sketch',   label: 'Sketch idea',  icon: '✿' },
      { id: 'palette',  label: 'Pick palette', icon: '◈' },
      { id: 'animate',  label: 'Animate',      icon: '✧' },
    ],
  },
  admin: {
    aura: '#60a5fa',
    idleQuotes: ['Laporan 8 hal.', 'Chart auto.', 'Format Word OK.', 'PDF rendered.'],
    idleEmoji: ['✎','▤','◫'],
    actions: [
      { id: 'report', label: 'Tulis laporan', icon: '✎' },
      { id: 'export', label: 'Export PDF',    icon: '▤' },
      { id: 'chart',  label: 'Generate chart',icon: '◫' },
    ],
  },
};

// ── Mood meter logic ───────────────────────────────────────
function initMoods() {
  return Object.fromEntries(
    AGENTS.map(a => [a.id, {
      mood: 60 + Math.floor(Math.random() * 30),     // 0..100
      energy: 80 + Math.floor(Math.random() * 20),
      quest: null,                                    // {label, progress, total, started}
    }])
  );
}

// ── Quest generator ────────────────────────────────────────
const QUEST_TEMPLATES = {
  bima:    ['Issue command ke Anisa', 'Rally seluruh guild', 'Strategi quarterly'],
  anisa:   ['Dispatch tim ke quest baru', 'Audit beban kerja guild', 'Lapor ke Lord Bima'],
  intel:   ['Scrape 3 sumber berita', 'Map domain target', 'OSINT investigasi #' ],
  visual:  ['OCR dokumen finansial', 'Analisa chart Q4', 'Baca 12 halaman PDF'],
  arsip:   ['Index 200 entries baru', 'Backup vault encrypted', 'Recall scroll Q3'],
  life:    ['Cari resto vegan dekat', 'Booking tiket ke Bali', 'Curate playlist santai'],
  mekanik: ['Debug pipeline #' , 'Refactor module auth', 'Deploy hotfix v3.2'],
  seniman: ['Sketch hero banner', 'Render dashboard SVG', 'Animate loading state'],
  admin:   ['Tulis laporan mingguan', 'Generate chart bar', 'Format proposal PDF'],
};

function makeQuest(agentId) {
  const tpl = pick(QUEST_TEMPLATES[agentId] || ['Quest umum']);
  const label = tpl.replace('#', String(rint(100, 999)));
  return {
    label,
    progress: 0,
    total: rint(15, 40),    // ticks (1 per second)
    started: Date.now(),
  };
}

// ── Floating quote bubble (above agent) ───────────────────
function FloatingQuote({ text, x, y, color }) {
  return (
    <div className="float-quote" style={{ left: `${x}%`, top: `${y}%`, color: color || 'var(--gold)' }}>
      <span>{text}</span>
    </div>
  );
}

// ── Speech bubble dengan typewriter (anchored ke agent) ──
// Re-trigger tiap kali `text` berubah; parent harus pakai `key={bubbleId}`
// supaya remount kalau perlu.
function SpeechBubble({ text, color, fading }) {
  const [shown, setShown] = React.useState('');
  const [done, setDone] = React.useState(false);
  React.useEffect(() => {
    if (!text) { setShown(''); setDone(false); return; }
    setShown('');
    setDone(false);
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length) { clearInterval(id); setDone(true); }
    }, 26);
    return () => clearInterval(id);
  }, [text]);
  if (!text) return null;
  const tinted = !!color;
  return (
    <div
      className={`speech-bubble ${!done ? 'typing' : ''} ${fading ? 'fading' : ''} ${tinted ? 'tinted' : ''}`}
      style={tinted ? { color } : undefined}
    >
      <span style={{ color: '#1a0e08' }}>{shown}</span>
      {!done && <span className="typing-cursor" style={{ color: '#1a0e08' }}>▋</span>}
    </div>
  );
}

// ── Mini-quest progress bar above agent ───────────────────
function QuestBar({ quest, x, y, color }) {
  if (!quest) return null;
  const pct = Math.min(100, (quest.progress / quest.total) * 100);
  return (
    <div className="quest-bar" style={{ left: `${x}%`, top: `${y - 4}%` }}>
      <div className="quest-bar-label">{quest.label}</div>
      <div className="quest-bar-track">
        <div className="quest-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

// ── Mood ring on agent ────────────────────────────────────
function MoodRing({ mood }) {
  const color = mood > 75 ? 'var(--emerald)' : mood > 45 ? 'var(--gold)' : mood > 20 ? 'var(--orange)' : 'var(--ember)';
  const emoji = mood > 75 ? '♥' : mood > 45 ? '◆' : mood > 20 ? '◇' : '✕';
  return (
    <div className="mood-ring" style={{ color }} title={`Mood: ${mood}`}>
      <span>{emoji}</span>
    </div>
  );
}

// ── Right-click context menu ──────────────────────────────
function ContextMenu({ agent, x, y, onAction, onClose }) {
  const sig = AGENT_SIGNATURES[agent.id];
  if (!sig) return null;
  return (
    <div className="ctx-menu" style={{ left: x, top: y }} onClick={e => e.stopPropagation()}>
      <div className="ctx-head">
        <span>{agent.sigil}</span>
        <span>{agent.name}</span>
      </div>
      {sig.actions.map(act => (
        <button key={act.id} className="ctx-item" onClick={() => { onAction(act); onClose(); }}>
          <span className="ctx-icon">{act.icon}</span>
          <span>{act.label}</span>
        </button>
      ))}
      <div className="ctx-sep" />
      <button className="ctx-item" onClick={() => { onAction({ id: 'rest', label: 'Rest 10s' }); onClose(); }}>
        <span className="ctx-icon">☾</span>
        <span>Rest (refill MP)</span>
      </button>
      <button className="ctx-item" onClick={() => { onAction({ id: 'potion', label: 'Beri potion' }); onClose(); }}>
        <span className="ctx-icon">◇</span>
        <span>Beri Token Elixir</span>
      </button>
    </div>
  );
}

// ── Particle burst (for loot drops, level ups, crits) ────
function ParticleBurst({ x, y, color, kind }) {
  const items = React.useMemo(() => {
    const count = kind === 'crit' ? 18 : kind === 'heart' ? 5 : 12;
    return Array.from({ length: count }).map((_, i) => ({
      id: i,
      angle: (Math.PI * 2 * i) / count + Math.random() * 0.4,
      dist: 30 + Math.random() * 40,
      delay: Math.random() * 0.15,
    }));
  }, [kind]);
  return (
    <div className="particle-burst" style={{ left: `${x}%`, top: `${y}%` }}>
      {items.map(p => (
        <span key={p.id}
          className={`burst-${kind || 'spark'}`}
          style={{
            color,
            transform: `rotate(${p.angle}rad) translateX(${p.dist}px)`,
            animationDelay: `${p.delay}s`,
          }} />
      ))}
    </div>
  );
}

// ── Delegation line between two agents ───────────────────
function DelegationLine({ from, to, color }) {
  if (!from || !to) return null;
  const cx = (from.x + to.x) / 2;
  const cy = (from.y + to.y) / 2;
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.sqrt(dx * dx + dy * dy);
  const angle = Math.atan2(dy, dx) * 180 / Math.PI;
  return (
    <div className="delegation-line" style={{
      left: `${cx}%`, top: `${cy}%`,
      width: `${len}%`,
      transform: `translate(-50%, -50%) rotate(${angle}deg)`,
      background: `linear-gradient(90deg, transparent, ${color || 'var(--gold)'}, transparent)`,
    }}>
      <div className="delegation-orb" style={{ background: color || 'var(--gold)' }} />
    </div>
  );
}

Object.assign(window, {
  AGENT_SIGNATURES, initMoods, makeQuest,
  FloatingQuote, SpeechBubble, QuestBar, MoodRing, ContextMenu, ParticleBurst, DelegationLine,
});
