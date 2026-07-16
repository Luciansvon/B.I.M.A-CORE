/* GUILD PANELS — chat, inventory, activity log, vault
   ────────────────────────────────────────────────── */

function RightPanel({ activeTab, setActiveTab, logs, addLog, addToast }) {
  return (
    <div className="right-panel">
      <div className="panel-tabs">
        <button className={`panel-tab ${activeTab==='activity' ? 'active' : ''}`} onClick={() => setActiveTab('activity')}>
          ▸ ACTIVITY <span className="badge">{logs.length}</span>
        </button>
        <button className={`panel-tab ${activeTab==='inv' ? 'active' : ''}`} onClick={() => setActiveTab('inv')}>
          ▸ INV <span className="badge">{INVENTORY.length}</span>
        </button>
        <button className={`panel-tab ${activeTab==='vault' ? 'active' : ''}`} onClick={() => setActiveTab('vault')}>
          ▸ VAULT
        </button>
        <button className={`panel-tab ${activeTab==='chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>
          ▸ CHAT
        </button>
      </div>
      <div className="panel-content">
        {activeTab === 'chat'     && <ChatPanel addLog={addLog} addToast={addToast} />}
        {activeTab === 'inv'      && <InventoryPanel />}
        {activeTab === 'activity' && <ActivityPanel logs={logs} />}
        {activeTab === 'vault'    && <VaultPanel />}
      </div>
    </div>
  );
}

// ── CHAT ──
const LS_CHAT = 'anisa_chat_history';

function loadChatHistory() {
  try {
    const raw = localStorage.getItem(LS_CHAT);
    if (!raw) return null;
    const arr = JSON.parse(raw);
    if (Array.isArray(arr) && arr.length) return arr;
  } catch (e) {}
  return null;
}
function saveChatHistory(messages) {
  try { localStorage.setItem(LS_CHAT, JSON.stringify(messages.slice(-100))); } catch (e) {}
}

function ChatPanel({ addLog, addToast }) {
  const [messages, setMessages] = React.useState(() => loadChatHistory() || [
    { role: 'system', text: 'Connection to Guildmaster established. Awaiting orders, Lord.', time: fmtTime() },
    { role: 'anisa', text: 'Halo sayang ✦\n\nGuild siap. Tim sudah di posisi masing-masing.\n\nMau aku **delegasikan quest**, atau ada hal lain yang lagi kamu pikirin? Aku di sini siap dengerin 🌙', time: fmtTime() },
  ]);
  const [input, setInput] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [progress, setProgress] = React.useState('');
  const scrollRef = React.useRef(null);
  const online = useBackendOnline();

  React.useEffect(() => { saveChatHistory(messages); }, [messages]);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, busy, progress]);

  // Live updates from backend WS while a command runs.
  useWsEvent('command_progress', React.useCallback((m) => {
    setProgress(String(m.message || '').slice(0, 200));
  }, []));
  useWsEvent('command_response', React.useCallback((m) => {
    const text = String(m.message || '');
    const isErr = !!m.error;
    setMessages(prev => [...prev, {
      role: isErr ? 'system' : 'anisa',
      text: isErr ? `[error] ${text}` : text,
      time: fmtTime(),
    }]);
    addLog({
      lvl: isErr ? 'ERR' : 'OK',
      text: isErr
        ? `[ANISA] error: ${text.slice(0, 80)}`
        : `[ANISA] respond · quest dispatched`,
      time: fmtTime(),
    });
    if (!isErr) addToast('loot', 'QUEST DISPATCHED', 'Anisa membagi tugas ke tim');
    setProgress('');
    setBusy(false);
  }, [addLog, addToast]));

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput('');
    setMessages(m => [...m, { role: 'user', text, time: fmtTime() }]);
    setBusy(true);
    addLog({ lvl: 'INFO', text: `[LORD] kirim perintah ke [ANISA]`, time: fmtTime() });

    if (online === false) {
      // Offline-mode stub so the UI still feels alive when running standalone.
      setTimeout(() => {
        setMessages(m => [...m, {
          role: 'system',
          text: `[offline mode] Backend (${API_BASE}) tidak terhubung. Perintah tidak dikirim.\n\nUntuk konek: jalankan B.I.M.A core dan akses dashboard via http://localhost:8000/dashboard`,
          time: fmtTime(),
        }]);
        setBusy(false);
      }, 400);
      return;
    }

    try {
      await apiCommand(text);
      // Response akan datang via WS (command_response). Busy state akan dilepas di handler.
    } catch (e) {
      const msg = e?.message || String(e);
      setMessages(m => [...m, { role: 'system', text: `[connection severed] ${msg}`, time: fmtTime() }]);
      setBusy(false);
    }
  };

  return (
    <>
      <div className="chat-help">
        <kbd>Enter</kbd> kirim · <kbd>Shift</kbd>+<kbd>Enter</kbd> baris baru<br />
        <kbd>↑↓</kbd> history · <kbd>Esc</kbd> tutup modal
      </div>
      <div className="chat-messages" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className={`msg-head ${m.role === 'user' ? 'user' : ''}`}>
              <span className="role">{m.role === 'user' ? '✦ LORD' : m.role === 'anisa' ? '◆ ANISA' : '⌘ SYSTEM'}</span>
              <span className="time">{m.time}</span>
            </div>
            <div className="msg-body" dangerouslySetInnerHTML={{ __html: formatMd(m.text) }} />
          </div>
        ))}
        {busy && (
          <div className="msg">
            <div className="msg-head"><span className="role">◆ ANISA</span><span className="time">thinking...</span></div>
            <div className="msg-body" style={{ fontStyle: 'italic', color: 'var(--text-dim)' }}>
              {progress ? progress : 'Anisa mempelajari perintah'}<span className="typing"></span>
            </div>
          </div>
        )}
      </div>
      <div style={{ padding: '6px 10px', display: 'flex', gap: 4, flexWrap: 'wrap', borderTop: '1px dashed var(--border)' }}>
        {QUICK_PROMPTS.map(q => (
          <button key={q} onClick={() => setInput(q)} style={{
            fontFamily: 'var(--mono)', fontSize: 10, padding: '4px 6px',
            background: 'var(--bg-deep)', color: 'var(--text-dim)',
            border: '1px solid var(--border)', cursor: 'pointer'
          }}>{q}</button>
        ))}
      </div>
      <div className="chat-input-wrap">
        <textarea
          className="chat-input"
          placeholder="Perintah untuk Anisa & guild..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
          }}
        />
        <button className="chat-send" onClick={send} disabled={busy || !input.trim()}>KIRIM</button>
      </div>
    </>
  );
}

function formatMd(text) {
  return String(text)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>');
}

// ── INVENTORY ──
// Live-fed dari /api/outputs (file di outputs/ dari hasil Anisa). Saat backend
// offline, fallback ke INVENTORY static biar tetap ada item buat dilihat.
const _OUTPUT_ICONS = {
  pdf: '†', docx: '✎', xlsx: '▤', html: '◎', img: '◇', svg: '✦',
  json: '⌘', csv: '▣', txt: '▦', code: '⚙', file: '◫',
};

function rarityFromMtime(iso) {
  if (!iso) return 'common';
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return 'common';
  const ageMs = Date.now() - ts;
  const day = 86_400_000;
  if (ageMs < day)        return 'legend';   // <24h
  if (ageMs < 7 * day)    return 'epic';     // <1 minggu
  if (ageMs < 30 * day)   return 'rare';     // <1 bulan
  return 'common';
}

function InventoryPanel() {
  const online = useBackendOnline();
  const { data: outputs } = useApiPoll(
    () => fetch(API_BASE + '/api/outputs?limit=20').then(r => r.json()),
    5000,
    [online],
  );
  const items = (online && outputs?.items) ? outputs.items.map(f => ({
    id: f.name,
    name: f.name,
    desc: `${f.size_human} · ${f.modified_human}`,
    icon: _OUTPUT_ICONS[f.icon] || '◫',
    rarity: rarityFromMtime(f.modified),
    url: f.url,
    count: 1,
  })) : INVENTORY;
  const total = (online && outputs?.total) || items.length;

  const cells = [...items, ...Array(Math.max(0, 20 - items.length)).fill(null)];
  return (
    <>
      <div style={{ padding: '8px 12px', borderBottom: '1px dashed var(--border)',
        fontFamily: 'var(--pix)', fontSize: 8, color: 'var(--gold)', letterSpacing: 1,
        display: 'flex', justifyContent: 'space-between' }}>
        <span>▣ {online ? 'ANISA OUTPUTS' : 'GUILD INVENTORY'}</span>
        <span style={{ color: 'var(--text-dim)' }}>{items.length}/{total}</span>
      </div>
      <div className="inv-grid">
        {cells.map((it, i) => (
          <div
            key={it?.id || i}
            className={`inv-cell ${it ? `inv-rarity-${it.rarity}` : 'empty'}`}
            onClick={() => { if (it?.url) window.open(API_BASE + it.url, '_blank'); }}
            style={{ cursor: it?.url ? 'pointer' : undefined }}
            title={it?.url ? 'Klik untuk buka' : undefined}
          >
            {it && (
              <>
                <span className="inv-icon">{it.icon}</span>
                {it.count > 1 && <span className="inv-count">x{it.count}</span>}
                <div className="inv-tooltip">
                  <span className="name">{it.name}</span>
                  <span className="desc">{it.desc}</span>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
      <div style={{ padding: '8px 12px', fontFamily: 'var(--mono)', fontSize: 11,
        color: 'var(--text-dim)', borderTop: '1px dashed var(--border)' }}>
        {online
          ? '▸ Klik item buat buka file. Rarity dari umur: <24h legend, <minggu epic, <bulan rare.'
          : '▸ [offline] menampilkan inventory statis. Konek backend untuk lihat output Anisa.'}
      </div>
    </>
  );
}

// ── ACTIVITY LOG ──
function ActivityPanel({ logs }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);
  return (
    <>
      <div style={{ padding: '8px 12px', borderBottom: '1px dashed var(--border)',
        fontFamily: 'var(--pix)', fontSize: 8, color: 'var(--gold)', letterSpacing: 1,
        display: 'flex', justifyContent: 'space-between' }}>
        <span>▸ EVENT STREAM</span>
        <span style={{ color: 'var(--emerald)' }}>● LIVE</span>
      </div>
      <div className="activity-log" ref={ref}>
        {logs.slice(-200).map((l, i) => (
          <div key={i} className="log-row">
            <span className="t">{l.time}</span>
            <span className={`lvl ${l.lvl}`}>{l.lvl}</span>
            <span className="msg-text">{l.text}</span>
          </div>
        ))}
      </div>
    </>
  );
}

// ── VAULT ──
function VaultPanel() {
  const [tokens, setTokens] = React.useState(48230);
  const [latency, setLatency] = React.useState(184);
  const [errs, setErrs] = React.useState(2.4);
  const [spark, setSpark] = React.useState(() => Array.from({ length: 24 }, () => rint(20, 90)));

  React.useEffect(() => {
    const i = setInterval(() => {
      setTokens(t => Math.max(0, t + rint(-200, 600)));
      setLatency(l => Math.max(20, Math.min(800, l + rint(-30, 30))));
      setErrs(e => Math.max(0, Math.min(8, e + (Math.random() - 0.5) * 0.4)));
      setSpark(s => [...s.slice(1), rint(20, 95)]);
    }, 1500);
    return () => clearInterval(i);
  }, []);

  const peakIdx = spark.indexOf(Math.max(...spark));

  return (
    <div className="vault-content">
      <div className="vault-block">
        <div className="head"><span>◈ TOKEN VAULT</span><span className="val">{tokens.toLocaleString()}</span></div>
        <div className="metric-bar"><div className="fill" style={{ width: `${Math.min(100, tokens / 800)}%` }} /><div className="label">{Math.min(100, Math.round(tokens / 800))}% USED</div></div>
        <div className="row"><span className="k">Daily limit</span><span className="v">80,000</span></div>
        <div className="row"><span className="k">Reset in</span><span className="v">04:17:23</span></div>
      </div>

      <div className="vault-block">
        <div className="head"><span>⚙ SYSTEM HEALTH</span><span className="val" style={{ color: errs > 4 ? 'var(--ember)' : 'var(--emerald)' }}>{errs > 4 ? 'WARN' : 'OK'}</span></div>
        <div className="row"><span className="k">Latency p95</span><span className="v">{latency}ms</span></div>
        <div className="metric-bar danger"><div className="fill" style={{ width: `${Math.min(100, latency / 8)}%` }} /></div>
        <div className="row"><span className="k">Error rate</span><span className="v">{errs.toFixed(2)}%</span></div>
        <div className="metric-bar danger"><div className="fill" style={{ width: `${errs * 12}%` }} /></div>
        <div className="row"><span className="k">Uptime</span><span className="v">149h 36m</span></div>
      </div>

      <div className="vault-block">
        <div className="head"><span>✦ THROUGHPUT 24h</span></div>
        <div className="spark">
          {spark.map((v, i) => (
            <div key={i} className={i === peakIdx ? 'peak' : ''} style={{ height: `${v}%` }} />
          ))}
        </div>
        <div className="row"><span className="k">Quest done</span><span className="v">1,283</span></div>
        <div className="row"><span className="k">Sessions</span><span className="v">50</span></div>
        <div className="row"><span className="k">Active agents</span><span className="v">8 / 8</span></div>
      </div>

      <div className="vault-block">
        <div className="head"><span>♦ LOOT TABLE</span></div>
        <div className="row"><span className="k">Legend drops</span><span className="v" style={{ color: 'var(--gold)' }}>2</span></div>
        <div className="row"><span className="k">Epic drops</span><span className="v" style={{ color: 'var(--violet)' }}>14</span></div>
        <div className="row"><span className="k">Rare drops</span><span className="v" style={{ color: 'var(--sapphire)' }}>67</span></div>
        <div className="row"><span className="k">Common</span><span className="v" style={{ color: 'var(--text-dim)' }}>312</span></div>
      </div>
    </div>
  );
}

Object.assign(window, { RightPanel, ChatPanel, InventoryPanel, ActivityPanel, VaultPanel });
