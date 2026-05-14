/* GUILD APP — top-level orchestrator
   ──────────────────────────────── */

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "mode": "day",
  "spriteStyle": "chibi",
  "tilePattern": "stone",
  "hudDensity": "rich",
  "chatSide": "right",
  "weather": "clear",
  "ambientAgents": true,
  "scanlines": true
}/*EDITMODE-END*/;

function GuildApp() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [floor, setFloor] = React.useState(1);
  const [activeTab, setActiveTab] = React.useState('chat');
  const [popover, setPopover] = React.useState(null);
  const [ctxMenu, setCtxMenu] = React.useState(null);
  const [logs, setLogs] = React.useState(() => Array.from({ length: 12 }, genLog));
  const [toasts, setToasts] = React.useState([]);
  const [positions, setPositionsRaw] = React.useState(() => loadPositions());
  const [draggingFurnId, setDraggingFurnId] = React.useState(null);
  const [editFurniture, setEditFurniture] = React.useState(false);
  const setPositions = React.useCallback((updater) => {
    setPositionsRaw(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      try { saveLayoutHybrid(next); } catch(e){}
      return next;
    });
  }, []);
  const [agentPos, setAgentPos] = React.useState(() => {
    const stored = loadPositions();
    return Object.fromEntries(AGENTS.map(a => {
      const p = stored[`char-${a.id}`];
      const x = p ? pctToNum(p.left) : a.x;
      const y = p ? pctToNum(p.top)  : a.y;
      return [a.id, { x, y, floor: a.floor || 1, status: a.statusDefault, walking: false, facing: 1 }];
    }));
  });
  const [moods, setMoods] = React.useState(initMoods);
  const [quests, setQuests] = React.useState({});
  const [floatingQuotes, setFloatingQuotes] = React.useState([]);
  const [delegations, setDelegations] = React.useState([]);
  const [bursts, setBursts] = React.useState([]);
  const [bubbles, setBubbles] = React.useState({});  // {[agentId]: { text, key, expiresAt, fading }}
  const [draggingId, setDraggingId] = React.useState(null);

  // sayBubble: pop chat bubble di atas agent. Auto-fade kemudian remove.
  const bubbleTimers = React.useRef({});
  const sayBubble = React.useCallback((agentId, text, durationMs = 4500) => {
    if (!agentId || !text) return;
    const key = Math.random().toString(36).slice(2);
    setBubbles(prev => ({ ...prev, [agentId]: { text, key, fading: false } }));
    const t0 = bubbleTimers.current[agentId];
    if (t0) { clearTimeout(t0.fade); clearTimeout(t0.kill); }
    const fade = setTimeout(() => {
      setBubbles(prev => prev[agentId]?.key === key ? { ...prev, [agentId]: { ...prev[agentId], fading: true } } : prev);
    }, durationMs - 400);
    const kill = setTimeout(() => {
      setBubbles(prev => {
        if (prev[agentId]?.key !== key) return prev;
        const { [agentId]: _, ...rest } = prev;
        return rest;
      });
      delete bubbleTimers.current[agentId];
    }, durationMs);
    bubbleTimers.current[agentId] = { fade, kill };
  }, []);
  // Expose globally supaya komponen lain (ChatPanel, dll) bisa trigger.
  React.useEffect(() => { window.__sayBubble = sayBubble; }, [sayBubble]);

  const backendOnline = useBackendOnline();

  React.useEffect(() => {
    document.body.dataset.mode = tweaks.mode;
    document.body.dataset.scanlines = String(tweaks.scanlines);
    document.body.dataset.backend = backendOnline ? 'online' : 'offline';
  }, [tweaks.mode, tweaks.scanlines, backendOnline]);

  // Hydrate positions from server if backend reachable (overrides local cache).
  React.useEffect(() => {
    let dead = false;
    loadLayoutHybrid().then(merged => {
      if (dead || !merged || !Object.keys(merged).length) return;
      setPositionsRaw(merged);
      setAgentPos(prev => {
        const next = { ...prev };
        for (const a of AGENTS) {
          const p = merged[`char-${a.id}`];
          if (!p || (!p.left && !p.top)) continue;
          const x = pctToNum(p.left);
          const y = pctToNum(p.top);
          if (!next[a.id]) next[a.id] = { x, y, floor: a.floor || 1, status: a.statusDefault, walking: false, facing: 1 };
          else next[a.id] = { ...next[a.id], x, y };
        }
        return next;
      });
    }).catch(() => {});
    return () => { dead = true; };
  }, []);

  // streaming logs — simulation only when backend offline
  React.useEffect(() => {
    if (backendOnline === true) return;
    const i = setInterval(() => setLogs(l => [...l, genLog()].slice(-200)), 2200);
    return () => clearInterval(i);
  }, [backendOnline]);

  // periodic toasts — simulation only when backend offline
  React.useEffect(() => {
    if (backendOnline === true) return;
    const i = setInterval(() => {
      if (Math.random() < 0.35) {
        const a = pick(AGENTS);
        const types = [
          { type: 'loot', icon: '♦', title: 'LOOT DROP', desc: `${a.name} dapat ${pick(['Gold Token x12', 'Rune of Logic', 'Token Elixir x3'])}` },
          { type: 'loot', icon: '✓', title: 'QUEST DONE', desc: `${a.name} selesai · ${rint(20, 800)}ms` },
          { type: 'warn', icon: '!', title: 'TOKEN WARNING', desc: `Usage ${rint(60, 90)}% · monitor budget` },
          { type: 'loot', icon: '◆', title: 'LEVEL UP', desc: `${a.name} naik ke level ${rint(40, 50)}` },
        ];
        const t = pick(types);
        addToast(t.type, t.title, t.desc, t.icon);
      }
    }, 6000);
    return () => clearInterval(i);
  }, [backendOnline]);

  // ── REAL backend events: agent state / command progress / history replay ──
  useWsEvent('agent_state', React.useCallback((m) => {
    const pid = BACKEND_TO_PIXEL[m.agent] || m.agent;
    const a = AGENTS.find(x => x.id === pid);
    if (!a) return;
    const status = STATE_MAP[m.state] || m.state;
    setAgentPos(p => p[pid] ? ({ ...p, [pid]: { ...p[pid], status } }) : p);
    const lvl = m.state === 'error' ? 'ERR' : (m.state === 'talking' ? 'OK' : 'INFO');
    setLogs(prev => [...prev, {
      lvl,
      text: `<span class="agent-name">${a.name}</span> → ${m.state}`,
      time: fmtTime(),
    }].slice(-200));
    if (m.state === 'error') {
      addToast('error', 'AGENT ERROR', `${a.name} encountered an error`, '!');
      sayBubble(pid, '✕ Error...', 3500);
    } else if (m.state === 'talking') {
      const sig = AGENT_SIGNATURES[pid];
      sayBubble(pid, sig ? pick(sig.idleQuotes) : '✓ Done!', 4500);
    } else if (m.state === 'thinking') {
      sayBubble(pid, '⋯ Mikir...', 3500);
    } else if (m.state === 'working') {
      const sig = AGENT_SIGNATURES[pid];
      if (sig && Math.random() < 0.7) sayBubble(pid, pick(sig.idleQuotes), 3500);
    }
  }, [sayBubble]));

  useWsEvent('command_progress', React.useCallback((m) => {
    const text = String(m.message || '').slice(0, 100);
    if (text) sayBubble('anisa', text, 5000);
  }, [sayBubble]));

  useWsEvent('command_response', React.useCallback((m) => {
    const text = String(m.message || '').slice(0, 120);
    if (m.error) sayBubble('anisa', `⚠ ${text}`, 6000);
    else if (text) sayBubble('anisa', text, 6500);
  }, [sayBubble]));

  useWsEvent('reset', React.useCallback((m) => {
    setLogs(prev => [...prev, {
      lvl: 'INFO',
      text: `[reset] ${String(m.message || '').slice(0, 120)}`,
      time: fmtTime(),
    }].slice(-200));
  }, []));

  useWsEvent('history', React.useCallback((m) => {
    if (!Array.isArray(m.events) || !m.events.length) return;
    const rows = m.events.slice(-80).map(ev => {
      const t = (() => { try { return fmtTime(new Date(ev.ts)); } catch (e) { return fmtTime(); } })();
      if (ev.type === 'agent_state') {
        const pid = BACKEND_TO_PIXEL[ev.agent] || ev.agent;
        const a = AGENTS.find(x => x.id === pid);
        return { lvl: ev.state === 'error' ? 'ERR' : 'INFO',
          text: `<span class="agent-name">${a?.name || ev.agent}</span> → ${ev.state}`, time: t };
      }
      if (ev.type === 'command_progress')
        return { lvl: 'INFO', text: `[progress] ${String(ev.message||'').slice(0, 120)}`, time: t };
      if (ev.type === 'command_response')
        return { lvl: ev.error ? 'ERR' : 'OK',
          text: `[anisa] ${String(ev.message||'').slice(0, 120)}`, time: t };
      if (ev.type === 'reset')
        return { lvl: 'INFO', text: `[reset] ${String(ev.message||'').slice(0, 120)}`, time: t };
      return null;
    }).filter(Boolean);
    if (rows.length) setLogs(rows);
  }, []));

  // mood drift + quest progress + idle quotes
  React.useEffect(() => {
    const i = setInterval(() => {
      // mood drift
      setMoods(prev => {
        const next = { ...prev };
        for (const a of AGENTS) {
          const m = next[a.id];
          let delta = (Math.random() - 0.55) * 2;
          if (quests[a.id]) delta -= 0.6; // working drains mood
          next[a.id] = { ...m, mood: Math.max(0, Math.min(100, m.mood + delta)) };
        }
        return next;
      });

      // quest progress
      setQuests(prev => {
        const next = { ...prev };
        let toComplete = [];
        for (const id in next) {
          const q = next[id];
          if (!q) continue;
          const newProg = q.progress + 1;
          if (newProg >= q.total) { toComplete.push(id); delete next[id]; }
          else next[id] = { ...q, progress: newProg };
        }
        if (toComplete.length) {
          setTimeout(() => {
            for (const id of toComplete) {
              const a = AGENTS.find(x => x.id === id);
              const sig = AGENT_SIGNATURES[id];
              if (a) {
                addBurst(agentPos[id]?.x || a.x, agentPos[id]?.y || a.y, sig?.aura, 'crit');
                addFloating(agentPos[id]?.x || a.x, agentPos[id]?.y || a.y, '✓ DONE!', '#7fd88c');
                addToast('loot', 'QUEST COMPLETE', `${a.name} selesai quest`, '✓');
                addLog({ lvl: 'OK', text: `<span class="agent-name">${a.name}</span> completed quest · loot drop`, time: fmtTime() });
                sayBubble(id, '✓ Selesai, Lord!', 4500);
              }
            }
          }, 0);
        }
        return next;
      });

      // random idle quote — pakai SpeechBubble (typewriter chat). Skip kalau
      // agent sudah punya bubble aktif (cek via timer ref biar tdk re-render).
      if (Math.random() < 0.4) {
        const candidates = AGENTS.filter(a => !bubbleTimers.current[a.id]);
        if (candidates.length) {
          const a = pick(candidates);
          const sig = AGENT_SIGNATURES[a.id];
          if (sig) sayBubble(a.id, pick(sig.idleQuotes), 4200);
        }
      }

      // random delegation between agents (panah lewat antar mereka)
      if (Math.random() < 0.18) {
        const a1 = pick(AGENTS);
        const a2 = pick(AGENTS.filter(x => x.id !== a1.id));
        const sig = AGENT_SIGNATURES[a1.id];
        addDelegation(a1.id, a2.id, sig?.aura);
        // sender bubble
        if (Math.random() < 0.6) sayBubble(a1.id, `→ ${a2.name}`, 2800);
      }

      // random sparkle on busy agent
      if (Math.random() < 0.4) {
        const busy = AGENTS.filter(a => agentPos[a.id]?.status === 'busy' || agentPos[a.id]?.status === 'working');
        if (busy.length) {
          const a = pick(busy);
          const sig = AGENT_SIGNATURES[a.id];
          const pos = agentPos[a.id];
          addBurst(pos.x, pos.y, sig?.aura, pick(['spark','magic','spark']));
        }
      }
    }, 1000);
    return () => clearInterval(i);
  }, [quests, agentPos]);

  function addLog(l) { setLogs(prev => [...prev, l].slice(-200)); }
  function addToast(type, title, desc, icon = '★') {
    const id = Math.random().toString(36).slice(2);
    setToasts(t => [...t, { id, type, title, desc, icon }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4500);
  }
  function addFloating(x, y, text, color) {
    const id = Math.random().toString(36).slice(2);
    setFloatingQuotes(q => [...q, { id, x, y, text, color }]);
    setTimeout(() => setFloatingQuotes(q => q.filter(f => f.id !== id)), 2900);
  }
  function addDelegation(fromId, toId, color) {
    const id = Math.random().toString(36).slice(2);
    setDelegations(d => [...d, { id, fromId, toId, color }]);
    setTimeout(() => setDelegations(d => d.filter(x => x.id !== id)), 1900);
  }
  function addBurst(x, y, color, kind) {
    const id = Math.random().toString(36).slice(2);
    setBursts(b => [...b, { id, x, y, color, kind }]);
    setTimeout(() => setBursts(b => b.filter(x => x.id !== id)), 1000);
  }

  function onAgentClick(agent, e) {
    e.stopPropagation();
    if (draggingId) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setPopover({
      agent,
      x: Math.min(window.innerWidth - 340, rect.right + 8),
      y: Math.max(8, rect.top - 40),
    });
  }

  function onAgentRightClick(agent, e) {
    e.preventDefault();
    e.stopPropagation();
    setCtxMenu({
      agent,
      x: Math.min(window.innerWidth - 200, e.clientX),
      y: Math.min(window.innerHeight - 280, e.clientY),
    });
  }

  function handleAgentAction(agent, action) {
    const sig = AGENT_SIGNATURES[agent.id];
    const pos = agentPos[agent.id];
    if (action.id === 'rest') {
      setMoods(m => ({ ...m, [agent.id]: { ...m[agent.id], mood: Math.min(100, m[agent.id].mood + 30), energy: 100 } }));
      addFloating(pos.x, pos.y, '☾ Rested!', '#7fd88c');
      addBurst(pos.x, pos.y, '#7fd88c', 'heart');
      addLog({ lvl: 'OK', text: `<span class="agent-name">${agent.name}</span> rested · MP refilled`, time: fmtTime() });
      sayBubble(agent.id, '☾ Mantap, MP penuh', 3500);
      return;
    }
    if (action.id === 'potion') {
      setMoods(m => ({ ...m, [agent.id]: { ...m[agent.id], mood: Math.min(100, m[agent.id].mood + 20) } }));
      addFloating(pos.x, pos.y, '◇ +Elixir!', '#fcd34d');
      addBurst(pos.x, pos.y, '#fcd34d', 'loot');
      addLog({ lvl: 'LOOT', text: `<span class="agent-name">${agent.name}</span> received Token Elixir`, time: fmtTime() });
      sayBubble(agent.id, 'Wuih, terima kasih Lord ◇', 3500);
      return;
    }
    // assign quest
    setQuests(q => ({ ...q, [agent.id]: makeQuest(agent.id) }));
    setAgentPos(p => ({ ...p, [agent.id]: { ...p[agent.id], status: 'busy' } }));
    addFloating(pos.x, pos.y, `▸ ${action.label}`, sig?.aura);
    addBurst(pos.x, pos.y, sig?.aura, 'spark');
    addToast('loot', 'QUEST ASSIGNED', `${agent.name} · ${action.label}`, action.icon || '✦');
    addLog({ lvl: 'INFO', text: `<span class="agent-name">${agent.name}</span> menerima quest: ${action.label}`, time: fmtTime() });
    sayBubble(agent.id, `Siap! ${action.label}`, 4000);
  }

  function onFurnitureClick(id) {
    const stage = document.querySelector('.stage');
    const rect = stage?.getBoundingClientRect();
    if (!rect) return;
    const messages = {
      'anvil':       { msg: 'MEKANIK datang ke anvil!', agent: 'mekanik', x: 60, y: 50, color: '#dc2626', kind: 'spark' },
      'cauldron':    { msg: 'SENIMAN brewing magic!',   agent: 'seniman', x: 68, y: 50, color: '#f472b6', kind: 'magic' },
      'chest':       { msg: 'ARSIP buka chest!',         agent: 'arsip',   x: 38, y: 50, color: '#a3e635', kind: 'loot' },
      'door':        { msg: 'Pintu guild dibuka.',       agent: null,      x: 92, y: 18, color: '#fcd34d', kind: 'spark' },
      'bookshelf-l': { msg: 'ARSIP browsing scroll.',    agent: 'arsip',   x: 4,  y: 14, color: '#a3e635', kind: 'magic' },
      'bookshelf-r': { msg: 'VISUAL membaca tome.',      agent: 'visual',  x: 96, y: 14, color: '#f97316', kind: 'magic' },
    };
    let m;
    if (messages[id]) m = messages[id];
    else if (id.startsWith('torch-')) {
      const x = parseInt(id.split('-')[1]);
      m = { msg: 'Torch dinyalakan ulang.', agent: null, x, y: 16, color: '#ff7a2e', kind: 'spark' };
    } else if (id.startsWith('desk-')) {
      const aid = id.replace('desk-', '');
      const a = AGENTS.find(x => x.id === aid);
      const sig = AGENT_SIGNATURES[aid];
      m = { msg: `${a?.name} kembali ke meja.`, agent: aid, x: a.x, y: a.y + 8, color: sig?.aura, kind: 'spark' };
    } else if (id.startsWith('monitor-')) {
      const aid = id.replace('monitor-', '');
      const a = AGENTS.find(x => x.id === aid);
      const sig = AGENT_SIGNATURES[aid];
      m = { msg: `Monitor ${a?.name}: ${pick(sig?.idleQuotes || ['idle...'])}`, agent: aid, x: a.x, y: a.y - 4, color: sig?.aura, kind: 'magic' };
    } else {
      m = { msg: 'Hmm, tidak ada apa-apa.', agent: null, x: 50, y: 50, color: '#fcd34d', kind: 'spark' };
    }
    addFloating(m.x, m.y, m.msg, m.color);
    addBurst(m.x, m.y, m.color, m.kind);
    addLog({ lvl: 'INFO', text: m.msg, time: fmtTime() });
  }

  React.useEffect(() => {
    const h = () => { setPopover(null); setCtxMenu(null); };
    window.addEventListener('click', h);
    return () => window.removeEventListener('click', h);
  }, []);

  return (
    <div className="app" onContextMenu={(e) => { if (!e.target.closest('.agent')) e.preventDefault(); }}>
      <TopBar floor={floor} setFloor={setFloor}
        mode={tweaks.mode} setMode={(m) => setTweak('mode', m)}
        weather={tweaks.weather} setWeather={(w) => setTweak('weather', w)}
        editFurniture={editFurniture}
        toggleEditFurniture={() => setEditFurniture(v => !v)}
        resetLayout={() => {
          if (confirm('Reset all furniture & character positions to default?')) {
            setPositions({});
            try { localStorage.removeItem('anisa_positions'); } catch(e){}
            apiSaveLayout({}).catch(() => {});
            location.reload();
          }
        }} />

      <div className="main" data-chat-side={tweaks.chatSide}>
        <Stage
          floor={floor}
          mode={tweaks.mode}
          tilePattern={tweaks.tilePattern}
          spriteStyle={tweaks.spriteStyle}
          ambientAgents={tweaks.ambientAgents}
          weather={tweaks.weather}
          agentPos={agentPos}
          setAgentPos={setAgentPos}
          positions={positions}
          setPositions={setPositions}
          draggingFurnId={draggingFurnId}
          setDraggingFurnId={setDraggingFurnId}
          editFurniture={editFurniture}
          moods={moods}
          quests={quests}
          floatingQuotes={floatingQuotes}
          delegations={delegations}
          bursts={bursts}
          bubbles={bubbles}
          sayBubble={sayBubble}
          onAgentClick={onAgentClick}
          onAgentRightClick={onAgentRightClick}
          onFurnitureClick={onFurnitureClick}
          draggingId={draggingId}
          setDraggingId={setDraggingId}
        />
        <RightPanel activeTab={activeTab} setActiveTab={setActiveTab} logs={logs} addLog={addLog} addToast={addToast} />
      </div>

      <BottomHUD density={tweaks.hudDensity} floor={floor} agentPos={agentPos} />

      {popover && <AgentPopover {...popover} onClose={() => setPopover(null)} />}
      {ctxMenu && (
        <ContextMenu
          agent={ctxMenu.agent} x={ctxMenu.x} y={ctxMenu.y}
          onAction={(a) => handleAgentAction(ctxMenu.agent, a)}
          onClose={() => setCtxMenu(null)}
        />
      )}

      <div className="toast-stack">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type}`}>
            <span className="icon">{t.icon}</span>
            <div>
              <span className="title">{t.title}</span>
              <span className="desc">{t.desc}</span>
            </div>
          </div>
        ))}
      </div>

      <TweaksPanel>
        <TweakSection title="Theme">
          <TweakRadio label="Mode" value={tweaks.mode} options={[
            {value:'day',label:'DAY'},{value:'night',label:'NIGHT'},{value:'storm',label:'STORM'},{value:'neon',label:'NEON'}
          ]} onChange={v => setTweak('mode', v)} />
          <TweakToggle label="CRT scanlines" value={tweaks.scanlines} onChange={v => setTweak('scanlines', v)} />
        </TweakSection>
        <TweakSection title="Layout">
          <TweakRadio label="Chat side" value={tweaks.chatSide} options={[
            {value:'left',label:'LEFT'},{value:'right',label:'RIGHT'},{value:'bottom',label:'BOTTOM'}
          ]} onChange={v => setTweak('chatSide', v)} />
          <TweakRadio label="HUD density" value={tweaks.hudDensity} options={[
            {value:'minimal',label:'MIN'},{value:'rich',label:'RICH'}
          ]} onChange={v => setTweak('hudDensity', v)} />
        </TweakSection>
        <TweakSection title="Scene">
          <TweakRadio label="Sprite style" value={tweaks.spriteStyle} options={[
            {value:'chibi',label:'CHIBI'},{value:'tall',label:'TALL'}
          ]} onChange={v => setTweak('spriteStyle', v)} />
          <TweakSelect label="Floor pattern" value={tweaks.tilePattern} options={[
            {value:'stone',label:'Stone'},{value:'wood-plank',label:'Wood plank'},
            {value:'checker',label:'Checker'},{value:'dungeon',label:'Dungeon'}
          ]} onChange={v => setTweak('tilePattern', v)} />
        </TweakSection>
        <TweakSection title="Atmosphere">
          <TweakSelect label="Weather" value={tweaks.weather} options={[
            {value:'clear',label:'Clear'},{value:'rain',label:'Hujan'},
            {value:'storm',label:'Badai'},{value:'snow',label:'Salju'},
            {value:'comet',label:'Hujan Komet'},{value:'dust',label:'Berdebu'}
          ]} onChange={v => setTweak('weather', v)} />
          <TweakToggle label="Wandering agents" value={tweaks.ambientAgents} onChange={v => setTweak('ambientAgents', v)} />
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

function TopBar({ floor, setFloor, mode, setMode, weather, setWeather, editFurniture, toggleEditFurniture, resetLayout }) {
  const MODES = [
    { id: 'day',   label: 'DAY',   cls: 'gold',   glyph: '☀' },
    { id: 'night', label: 'NIGHT', cls: '',       glyph: '☾' },
    { id: 'storm', label: 'STORM', cls: 'danger', glyph: '⚡' },
    { id: 'neon',  label: 'NEON',  cls: 'violet', glyph: '✦' },
  ];
  const WEATHERS = [
    { id: 'clear', label: 'CLEAR', cls: 'gold',   glyph: '○' },
    { id: 'rain',  label: 'RAIN',  cls: '',       glyph: '☂' },
    { id: 'storm', label: 'STORM', cls: 'danger', glyph: '⚡' },
    { id: 'snow',  label: 'SNOW',  cls: '',       glyph: '❄' },
    { id: 'comet', label: 'COMET', cls: 'violet', glyph: '☄' },
    { id: 'dust',  label: 'DUST',  cls: '',       glyph: '◌' },
  ];
  const curMode    = MODES.find(m => m.id === mode) || MODES[0];
  const curWeather = WEATHERS.find(w => w.id === weather) || WEATHERS[0];
  const cycle = (arr, current, setter) => () => {
    const idx = arr.findIndex(x => x.id === current);
    setter(arr[(idx + 1) % arr.length].id);
  };
  return (
    <div className="topbar">
      <div className="brand">
        <span className="brand-icon"></span>
        <span>GUILD HALL ARENWOOD</span>
      </div>
      <div className="tabs">
        {FLOORS.map(f => (
          <button key={f.id} className={`tab ${floor === f.id ? 'active' : ''}`} onClick={() => setFloor(f.id)}>
            <span className="tab-glyph">{f.icon}</span>
            <span>{f.sub}</span>
          </button>
        ))}
      </div>
      <div className="spacer" />
      <div className="mode-buttons">
        <div className="mode-cluster">
          <span className="mode-label">THEME</span>
          <button className={`mode-btn ${curMode.cls} active`} onClick={cycle(MODES, mode, setMode)} title="Click to cycle theme">
            <span className="dot"></span>
            <span>{curMode.glyph} {curMode.label}</span>
            <span className="cycle-arrow">▸</span>
          </button>
        </div>
        <div className="mode-cluster">
          <span className="mode-label">WEATHER</span>
          <button className={`mode-btn ${curWeather.cls} active`} onClick={cycle(WEATHERS, weather, setWeather)} title="Click to cycle weather">
            <span className="dot"></span>
            <span>{curWeather.glyph} {curWeather.label}</span>
            <span className="cycle-arrow">▸</span>
          </button>
        </div>
        <div className="mode-cluster">
          <span className="mode-label">LAYOUT</span>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              className={`mode-btn ${editFurniture ? 'gold active' : ''}`}
              onClick={toggleEditFurniture}
              title="Toggle furniture edit mode (drag to rearrange, auto-saved)"
            >
              <span className="dot"></span>
              <span>{editFurniture ? '◉ EDITING' : '✎ EDIT'}</span>
            </button>
            {editFurniture && (
              <button className="mode-btn danger" onClick={resetLayout} title="Reset all positions to default">
                ↺ RESET
              </button>
            )}
          </div>
        </div>
        <button className="mode-btn live active">
          <span className="pulse"></span> LIVE
        </button>
      </div>
    </div>
  );
}

function fmtUptime(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function BottomHUD({ density, floor, agentPos }) {
  const online = useBackendOnline();
  const { data: live } = useApiPoll(apiMetrics, 3000, [online]);
  const [sim, setSim] = React.useState({
    active: AGENTS.length, total: AGENTS.length, events: 1283, lastEvt: '12s', uptime: '149:36', cat: 'patrolling',
    tokens: 48230, latency: 184, errors: 2.4,
  });
  React.useEffect(() => {
    if (live) return;
    const i = setInterval(() => {
      setSim(s => ({
        ...s,
        events: s.events + (Math.random() < 0.6 ? 1 : 0),
        latency: Math.max(40, Math.min(700, s.latency + rint(-15, 15))),
        tokens: Math.max(0, s.tokens + rint(-50, 200)),
        errors: Math.max(0, Math.min(8, s.errors + (Math.random() - 0.5) * 0.3)),
        cat: pick(['patrolling','meditating','crafting','scrying','smithing','dispatching','indexing','feasting']),
      }));
    }, 1800);
    return () => clearInterval(i);
  }, [live]);

  const stats = React.useMemo(() => {
    if (!live) return sim;
    const ag = live.agents || {};
    const vals = Object.values(ag);
    const events = vals.reduce((a, x) => a + (x.task_count || 0), 0);
    const errors = vals.reduce((a, x) => a + (x.error_count || 0), 0);
    const lats = vals.map(x => x.avg_ms || 0).filter(x => x > 0);
    const latency = lats.length ? Math.round(lats.reduce((a, b) => a + b, 0) / lats.length) : 0;
    const active = vals.filter(x => x.status !== 'idle' && x.status !== 'error').length || AGENTS.length;
    // pick a representative category from a busy agent name
    const busyId = Object.entries(ag).find(([, x]) => x.status === 'working' || x.status === 'busy')?.[0];
    const a = busyId ? AGENTS.find(x => x.id === busyId) : null;
    return {
      active, total: AGENTS.length,
      events, errors: errors,
      latency,
      uptime: fmtUptime(live.uptime || 0),
      lastEvt: '—',
      cat: a ? a.role.toLowerCase() : 'idle',
      tokens: 0,
    };
  }, [live, sim]);

  if (density === 'minimal') {
    return (
      <div className="hud" style={{ height: 60 }}>
        <div className="hud-block"><div className="label">ACTIVE</div><div className="val">{stats.active}/{stats.total}</div></div>
        <div className="hud-stats">
          <div className="hud-cell"><div className="label">EVENTS</div><div className="val gold">{stats.events}</div></div>
          <div className="hud-cell"><div className="label">UPTIME</div><div className="val">{stats.uptime}</div></div>
          <div className="hud-cell"><div className="label">CAT</div><div className="val">{stats.cat}</div></div>
        </div>
        <Minimap floor={floor} agentPos={agentPos} />
      </div>
    );
  }

  return (
    <div className="hud">
      <div className="hud-block">
        <div className="label">ACTIVE</div>
        <div className="val">{stats.active} <span style={{ fontSize: 14, color: 'var(--text-dim)' }}>/ {stats.total}</span></div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: stats.active === stats.total ? 'var(--emerald)' : 'var(--orange)', marginTop: 2 }}>● {stats.active === stats.total ? 'ALL ONLINE' : `${stats.total - stats.active} OFFLINE`}</div>
      </div>
      <div className="hud-stats">
        <div className="hud-cell"><div className="label">EVENTS</div><div className="val gold">{stats.events}</div><div className="sub">↑ +{stats.events - 1283} today</div></div>
        <div className="hud-cell"><div className="label">LAST EVT</div><div className="val">{stats.lastEvt}</div><div className="sub">ago</div></div>
        <div className="hud-cell"><div className="label">UPTIME</div><div className="val emerald">{stats.uptime}</div><div className="sub">hours</div></div>
        <div className="hud-cell"><div className="label">LATENCY</div><div className="val orange">{stats.latency}ms</div><div className="sub">p95</div></div>
        <div className="hud-cell"><div className="label">CATEGORY</div><div className="val" style={{ fontSize: 14 }}>{stats.cat}</div><div className="sub">current task</div></div>
      </div>
      <Minimap floor={floor} agentPos={agentPos} />
    </div>
  );
}

const STATUS_COLOR = {
  working: '#7fd88c',
  busy:    '#ff7a2e',
  idle:    '#b89760',
  error:   '#d94824',
  walking: '#fcd34d',
};

function Minimap({ floor, agentPos }) {
  return (
    <div className="minimap">
      <div className="minimap-grid">
        <div className={`mini-room ${floor === 3 ? 'active' : ''}`} style={{ top: 10, left: 10, right: 10, height: 18 }} />
        <div className={`mini-room ${floor === 2 ? 'active' : ''}`} style={{ top: 32, left: 10, right: 10, height: 18 }} />
        <div className={`mini-room ${floor === 1 ? 'active' : ''}`} style={{ top: 54, left: 10, right: 10, height: 18 }} />
        {AGENTS.map((a, i) => {
          const live = agentPos && agentPos[a.id];
          const status = live?.status || a.statusDefault || 'idle';
          const color = STATUS_COLOR[status] || a.shirt;
          return (
            <div key={a.id} className="mini-dot" title={`${a.name} · ${status}`} style={{
              background: color,
              top: 60 + (i % 2) * 4,
              left: 14 + (i % 8) * 14,
              boxShadow: status === 'error' ? '0 0 4px #d94824' : 'none',
            }} />
          );
        })}
      </div>
    </div>
  );
}

function AgentPopover({ agent, x, y, onClose }) {
  return (
    <div className="agent-popover" style={{ left: x, top: y }} onClick={e => e.stopPropagation()}>
      <div className="pop-head">
        <span>{agent.sigil} {agent.name} · {agent.role}</span>
        <span className="x" onClick={onClose}>X</span>
      </div>
      <div className="pop-body">
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 10 }}>
          <div style={{ background: 'var(--bg-deep)', padding: 6, border: '2px solid var(--border-bright)' }}>
            <AgentSprite agent={agent} scale={3} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: 'var(--pix)', fontSize: 9, color: 'var(--gold)', marginBottom: 4, letterSpacing: 1 }}>
              LV.{agent.stats.level} · {agent.class}
            </div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.4 }}>
              {agent.bio}
            </div>
          </div>
        </div>

        <div style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'var(--pix)' }}>
            <span style={{ color: 'var(--text-dim)' }}>HP</span>
            <span style={{ color: 'var(--emerald)' }}>{agent.stats.hp}/100</span>
          </div>
          <div className="bar"><div style={{ width: `${agent.stats.hp}%` }} /></div>
        </div>
        <div style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'var(--pix)' }}>
            <span style={{ color: 'var(--text-dim)' }}>MP</span>
            <span style={{ color: 'var(--sapphire)' }}>{agent.stats.mp}/100</span>
          </div>
          <div className="bar"><div style={{ width: `${agent.stats.mp}%`, background: 'linear-gradient(90deg, var(--sapphire), var(--violet))' }} /></div>
        </div>

        <div className="stat-row"><span className="stat-label">WEAPON</span><span className="stat-value">{agent.weapon}</span></div>
        <div className="stat-row"><span className="stat-label">TASKS</span><span className="stat-value">{agent.stats.tasks.toLocaleString()}</span></div>
        <div className="stat-row"><span className="stat-label">LATENCY p95</span><span className="stat-value">{agent.stats.latency}ms</span></div>
        <div className="stat-row"><span className="stat-label">ERROR RATE</span><span className="stat-value" style={{ color: agent.stats.errors > 1 ? 'var(--ember)' : 'var(--emerald)' }}>{agent.stats.errors}%</span></div>
        <div className="stat-row"><span className="stat-label">SIGIL</span><span className="stat-value">{agent.sigil}</span></div>

        <div className="quote">"{agent.quote}"</div>

        <div className="actions">
          <button>▸ FOCUS</button>
          <button>✦ SUMMON</button>
          <button onClick={onClose}>✕ CLOSE</button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { GuildApp });
