/* GUILD SCENE — pixel diorama with rooms, agents, ambient
   ────────────────────────────────────────────────────── */

function Stage({
  floor, mode, tilePattern, spriteStyle, ambientAgents, weather,
  agentPos, setAgentPos, positions, setPositions,
  moods, quests, floatingQuotes, delegations, bursts,
  bubbles, sayBubble,
  onAgentClick, onAgentRightClick, onFurnitureClick,
  draggingId, setDraggingId, draggingFurnId, setDraggingFurnId,
  editFurniture,
}) {
  const stageRef = React.useRef(null);
  const sceneMetaRef = React.useRef({});  // ephemeral wander state per agent (pauseUntil, speedMul, _greet pairs)
  const [time, setTime] = React.useState('21:43:07');
  const [walkTick, setWalkTick] = React.useState(0);

  React.useEffect(() => {
    const i = setInterval(() => setTime(fmtTime()), 1000);
    return () => clearInterval(i);
  }, []);

  // walk frame ticker (200ms)
  React.useEffect(() => {
    const i = setInterval(() => setWalkTick(t => t + 1), 220);
    return () => clearInterval(i);
  }, []);

  // ── ambient wander v4 — multi-floor + meeting + greet ──
  // Tiap landmark punya `floor`. Saat agent pilih landmark di floor lain,
  // dia transisi: fade-out 350ms → switch floor → teleport ke FLOOR_ENTRY[newFloor]
  // → fade-in → lanjut wander ke target. Selama transisi, agent invisible
  // di floor lama dan belum tampil di floor baru.
  React.useEffect(() => {
    if (!ambientAgents) return;

    const meta = sceneMetaRef.current;
    if (!meta._init) {
      meta._init = true;
      meta._greet = {};
      meta.meetingUntil = 0;
      meta.nextMeetingAt = Date.now() + 45000 + Math.random() * 60000;
    }
    for (const a of AGENTS) {
      if (!meta[a.id]) {
        const seed = a.id.split('').reduce((s, c) => s + c.charCodeAt(0), 0);
        meta[a.id] = {
          pauseUntil: 0,
          streak: 0,
          speedMul: 0.85 + ((seed % 40) / 100),
          lastLandmark: null,
          transitionUntil: 0,    // saat transisi antar lantai
          targetFloor: null,
        };
      }
    }

    function pickLandmark(agentId) {
      const prefs = AGENT_PREFS[agentId] || [];
      if (prefs.length && Math.random() < 0.6) {
        const name = prefs[Math.floor(Math.random() * prefs.length)];
        return LANDMARKS.find(l => l.name === name) || LANDMARKS[0];
      }
      return LANDMARKS[Math.floor(Math.random() * LANDMARKS.length)];
    }

    const i = setInterval(() => {
      const now = Date.now();

      // ── MEETING SCHEDULER (di floor 2 War Room) ──
      if (now > meta.nextMeetingAt && meta.meetingUntil < now) {
        meta.meetingUntil = now + 9000 + Math.random() * 4000;   // hold 9-13s
        meta.nextMeetingAt = meta.meetingUntil + 60000 + Math.random() * 60000;
        // semua non-quest agent diundang ke War Room (floor 2 meja meeting)
        for (const a of AGENTS) {
          if (quests && quests[a.id]) continue;
          if (draggingId === a.id) continue;
          const m = meta[a.id];
          m._meetTarget = {
            floor: 2,
            x: 50 + (Math.random() - 0.5) * 10,
            y: 50 + (Math.random() - 0.5) * 8,
          };
          m._meetGreeted = false;
        }
        if (sayBubble) sayBubble('anisa', '◆ Kumpul di War Room!', 4500);
      }

      const inMeeting = now < meta.meetingUntil;

      setAgentPos(prev => {
        const next = { ...prev };

        for (const a of AGENTS) {
          if (draggingId === a.id) continue;
          const cur = prev[a.id];
          if (!cur) continue;
          const m = meta[a.id];
          const curFloor = cur.floor || 1;

          const hasQuest = quests && quests[a.id];

          // ── 0. di tengah TRANSISI antar-lantai
          if (m.transitionUntil && now < m.transitionUntil) {
            // half-time: switch floor + teleport ke FLOOR_ENTRY
            if (m.targetFloor && m.targetFloor !== curFloor && now > m.transitionUntil - 175) {
              const entry = FLOOR_ENTRY[m.targetFloor] || { x: 90, y: 50 };
              next[a.id] = { ...cur, floor: m.targetFloor, x: entry.x, y: entry.y, walking: false, transitioning: true };
              continue;
            }
            next[a.id] = { ...cur, walking: false, transitioning: true };
            continue;
          }
          if (m.transitionUntil && now >= m.transitionUntil) {
            m.transitionUntil = 0;
            m.targetFloor = null;
            next[a.id] = { ...cur, transitioning: false };
            // lanjut tick berikutnya
            continue;
          }

          // ── 1. quest aktif → balik ke floor 1 home (workstation)
          if (hasQuest) {
            // kalau di floor lain, transisi pulang dulu
            if (curFloor !== (a.floor || 1)) {
              m.transitionUntil = now + 350;
              m.targetFloor = a.floor || 1;
              next[a.id] = { ...cur, walking: false, transitioning: true };
              continue;
            }
            const dx = (a.x - cur.x);
            const dy = (a.y - cur.y);
            const len = Math.hypot(dx, dy);
            const step = 1.4 * m.speedMul;
            const nx = len > step ? cur.x + (dx / len) * step : a.x;
            const ny = len > step ? cur.y + (dy / len) * step : a.y;
            next[a.id] = {
              ...cur,
              x: nx, y: ny,
              walking: len > 0.5,
              facing: dx < -0.1 ? -1 : (dx > 0.1 ? 1 : cur.facing),
              tx: undefined, ty: undefined,
            };
            continue;
          }

          // ── 2. MEETING mode → War Room (floor 2)
          if (inMeeting && m._meetTarget) {
            // pindah ke floor 2 dulu kalau belum
            if (curFloor !== m._meetTarget.floor) {
              m.transitionUntil = now + 350;
              m.targetFloor = m._meetTarget.floor;
              next[a.id] = { ...cur, walking: false, transitioning: true };
              continue;
            }
            const tx = m._meetTarget.x, ty = m._meetTarget.y;
            const dx = tx - cur.x;
            const dy = ty - cur.y;
            const len = Math.hypot(dx, dy);
            const step = 1.4 * m.speedMul;
            const nx = len > step ? cur.x + (dx / len) * step : tx;
            const ny = len > step ? cur.y + (dy / len) * step : ty;
            if (len < 1 && !m._meetGreeted && sayBubble && Math.random() < 0.6) {
              m._meetGreeted = true;
              sayBubble(a.id, pick(MEETING_QUOTES), 4000);
            }
            next[a.id] = {
              ...cur,
              x: nx, y: ny,
              walking: len > 0.4,
              facing: dx < -0.1 ? -1 : (dx > 0.1 ? 1 : cur.facing),
              tx, ty,
            };
            continue;
          } else if (m._meetTarget && !inMeeting) {
            m._meetTarget = null;
          }

          // ── 3. pause (idle setelah arrive)
          if (now < m.pauseUntil) {
            next[a.id] = { ...cur, walking: false };
            continue;
          }

          // ── 4. pilih landmark baru atau udah dekat
          let tx = cur.tx, ty = cur.ty;
          const distToTarget = (tx != null && ty != null) ? Math.hypot(tx - cur.x, ty - cur.y) : Infinity;

          if (tx == null || distToTarget < 1.2) {
            if (tx != null) {
              const lm = m.lastLandmark;
              const home = { x: a.x, y: a.y };
              const distFromHome = Math.hypot(cur.x - home.x, cur.y - home.y);
              if (lm && Math.random() < 0.55 && sayBubble) {
                sayBubble(a.id, pick(lm.action), 2800);
              } else if (Math.random() < 0.4 && sayBubble) {
                const topics = a.id === 'anisa' ? ANISA_TOPICS : WORK_TOPICS;
                sayBubble(a.id, pick(topics), 2800);
              }
              m.pauseUntil = now + 1800 + Math.random() * 3200;
              m.streak += 1;

              // setelah 3 wander, paksa balik ke floor 1 home
              if (m.streak >= 3 && (curFloor !== 1 || distFromHome > 5)) {
                m.streak = 0;
                m.lastLandmark = null;
                if (curFloor !== 1) {
                  m.transitionUntil = now + 350;
                  m.targetFloor = 1;
                  next[a.id] = { ...cur, walking: false, transitioning: true, tx: a.x, ty: a.y };
                  continue;
                }
                tx = a.x; ty = a.y;
                next[a.id] = { ...cur, tx, ty };
                continue;
              }
            }

            // pilih landmark berikut — bisa lintas-lantai
            const lm = pickLandmark(a.id);
            m.lastLandmark = lm;
            const jx = (Math.random() - 0.5) * 6;
            const jy = (Math.random() - 0.5) * 4;
            tx = Math.max(4, Math.min(96, lm.x + jx));
            ty = Math.max(20, Math.min(94, lm.y + jy));

            // kalau target di lantai lain → trigger transisi
            if (lm.floor !== curFloor) {
              m.transitionUntil = now + 350;
              m.targetFloor = lm.floor;
              if (sayBubble && Math.random() < 0.4) {
                const dest = lm.floor === 1 ? 'Guild Hall ⚒' : lm.floor === 2 ? 'War Room ⚔' : 'Tower Roost ☾';
                sayBubble(a.id, `→ ${dest}`, 2200);
              }
              next[a.id] = { ...cur, walking: false, transitioning: true, tx, ty };
              continue;
            }
          }

          // ── 5. step toward target + separation (cuma vs agent di floor sama)
          let dx = tx - cur.x;
          let dy = ty - cur.y;

          for (const b of AGENTS) {
            if (b.id === a.id) continue;
            const op = prev[b.id];
            if (!op || (op.floor || 1) !== curFloor) continue;
            const sx = cur.x - op.x;
            const sy = cur.y - op.y;
            const sd = Math.hypot(sx, sy);
            if (sd > 0 && sd < 3.5 && !inMeeting) {
              const push = (3.5 - sd) * 0.4;
              dx += (sx / sd) * push;
              dy += (sy / sd) * push;
            }
            if (sd > 0 && sd < 5 && sayBubble) {
              const pairKey = a.id < b.id ? `${a.id}|${b.id}` : `${b.id}|${a.id}`;
              const last = meta._greet[pairKey] || 0;
              if (now - last > 18000 && Math.random() < 0.04) {
                meta._greet[pairKey] = now;
                sayBubble(a.id, pick(GREETINGS), 2400);
                if (Math.random() < 0.6) {
                  setTimeout(() => sayBubble(b.id, pick(GREETINGS), 2200), 700);
                }
              }
            }
          }

          const len = Math.hypot(dx, dy);
          const step = 1.4 * m.speedMul * (0.9 + Math.random() * 0.2);
          const nx = len > step ? cur.x + (dx / len) * step : tx;
          const ny = len > step ? cur.y + (dy / len) * step : ty;
          next[a.id] = {
            ...cur,
            x: Math.max(2, Math.min(98, nx)),
            y: Math.max(20, Math.min(96, ny)),
            tx, ty,
            walking: len > 0.4,
            facing: dx < -0.1 ? -1 : (dx > 0.1 ? 1 : (cur.facing ?? 1)),
          };
        }
        return next;
      });
    }, 100);
    return () => clearInterval(i);
  }, [ambientAgents, draggingId, setAgentPos, quests, sayBubble]);

  // ── EDIT MODE delegation: while editFurniture is true,
  //    any mousedown on a .interactive-fx (with data-furn-id) starts a furn drag.
  React.useEffect(() => {
    if (!editFurniture) return;
    const stage = stageRef.current;
    if (!stage) return;
    const onDown = (e) => {
      if (e.button !== 0) return;
      // ignore agent / pet clicks
      if (e.target.closest('.agent') || e.target.closest('.pet-sprite')) return;
      const item = e.target.closest('.interactive-fx[data-furn-id], .draggable-furn[data-furn-id], .furn-item[data-furn-id]');
      if (!item) return;
      e.preventDefault();
      e.stopPropagation();
      const id = item.getAttribute('data-furn-id');
      setDraggingFurnId && setDraggingFurnId(id);
    };
    stage.addEventListener('mousedown', onDown, true);
    return () => stage.removeEventListener('mousedown', onDown, true);
  }, [editFurniture, setDraggingFurnId]);

  // Apply persisted position overrides to any [data-furn-id] node.
  React.useEffect(() => {
    const stage = stageRef.current;
    if (!stage || !positions) return;
    Object.entries(positions).forEach(([id, pos]) => {
      if (id.startsWith('char-')) return;
      const el = stage.querySelector(`[data-furn-id="${id}"]`);
      if (!el || !pos) return;
      if (pos.left)  el.style.left   = pos.left;
      if (pos.top)   el.style.top    = pos.top;
      if (pos.right) el.style.right  = '';
      if (pos.bottom)el.style.bottom = '';
    });
  }, [positions, floor]);

  // drag handler — agents
  React.useEffect(() => {
    if (!draggingId) return;
    const onMove = (e) => {
      const rect = stageRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      const cx = Math.max(2, Math.min(98, x));
      const cy = Math.max(20, Math.min(95, y));
      setAgentPos(prev => ({
        ...prev,
        [draggingId]: { ...prev[draggingId], x: cx, y: cy, walking: true },
      }));
      if (setPositions) setPositions(prev => ({
        ...prev,
        [`char-${draggingId}`]: { left: `${cx}%`, top: `${cy}%` },
      }));
    };
    const onUp = () => {
      setAgentPos(prev => ({ ...prev, [draggingId]: { ...prev[draggingId], walking: false } }));
      setDraggingId(null);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [draggingId, setAgentPos, setPositions, setDraggingId]);

  // drag handler — furniture (persisted via positions state)
  React.useEffect(() => {
    if (!draggingFurnId || !setPositions) return;
    const onMove = (e) => {
      const rect = stageRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      setPositions(prev => ({
        ...prev,
        [draggingFurnId]: { left: `${x}%`, top: `${y}%` },
      }));
    };
    const onUp = () => setDraggingFurnId(null);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [draggingFurnId, setPositions, setDraggingFurnId]);

  const room = ROOMS[floor];
  const showAgents = floor === 1;
  const showWar = floor === 2;
  const showRoost = floor === 3;

  return (
    <div className="stage-frame">
      <div className="stage-header">
        <div className="crumbs">
          <span style={{ color: 'var(--gold)' }}>▸</span>
          <span>{room.name}</span>
          <span className="arrow">»</span>
          <span>{room.sub}</span>
        </div>
        <div className="clock">{time}</div>
      </div>

      <div className={`stage ${editFurniture ? 'edit-furniture-mode' : ''}`} ref={stageRef}>
        <div className={`floor ${tilePattern}`}></div>

        {showAgents && (
          <GuildHallScene
            agentPos={agentPos} spriteStyle={spriteStyle} moods={moods} quests={quests}
            bubbles={bubbles}
            walkTick={walkTick}
            positions={positions} setPositions={setPositions}
            onAgentClick={onAgentClick} onAgentRightClick={onAgentRightClick}
            onFurnitureClick={onFurnitureClick}
            draggingId={draggingId} setDraggingId={setDraggingId}
            draggingFurnId={draggingFurnId} setDraggingFurnId={setDraggingFurnId}
          />
        )}
        {showWar && <WarRoomScene />}
        {showRoost && <TowerRoostScene walkTick={walkTick} />}

        {/* Agent layer di-render setelah scene, filtered by current floor.
           Agent yang lagi di lantai ini muncul; lainnya ke-hidden. */}
        <AgentLayer
          floor={floor}
          agentPos={agentPos} spriteStyle={spriteStyle}
          moods={moods} quests={quests} bubbles={bubbles}
          walkTick={walkTick}
          draggingId={draggingId} setDraggingId={setDraggingId}
          onAgentClick={onAgentClick} onAgentRightClick={onAgentRightClick}
        />

        {/* delegation lines */}
        {delegations.map(d => {
          const from = agentPos[d.fromId];
          const to = agentPos[d.toId];
          return <DelegationLine key={d.id} from={from} to={to} color={d.color} />;
        })}

        {bursts.map(b => (
          <ParticleBurst key={b.id} x={b.x} y={b.y} color={b.color} kind={b.kind} />
        ))}
        {floatingQuotes.map(q => (
          <FloatingQuote key={q.id} text={q.text} x={q.x} y={q.y} color={q.color} />
        ))}

        <Weather mode={mode} weather={weather} />
      </div>
    </div>
  );
}

// ── Draggable furniture wrapper ──
// Every interactive furniture item should be wrapped in <Furn> so its
// position can be edited (when editMode is on) and persisted in `positions`.
function Furn({ id, positions, setPositions, fallback, setDraggingFurnId, editMode, children, onClick, zIndex = 3, extraStyle }) {
  const pos = (positions && positions[id]) || fallback;
  const onMouseDown = (e) => {
    if (!editMode) return;
    if (e.button !== 0) return;
    e.stopPropagation();
    setDraggingFurnId && setDraggingFurnId(id);
  };
  const baseStyle = {
    position: 'absolute',
    left: pos.left, top: pos.top, right: pos.right, bottom: pos.bottom,
    zIndex,
    cursor: editMode ? 'grab' : 'pointer',
    ...extraStyle,
  };
  return (
    <div
      className={`furn-item ${editMode ? 'edit-mode' : 'interactive-fx'}`}
      data-furn-id={id}
      style={baseStyle}
      onClick={(e) => {
        e.stopPropagation();
        if (editMode) return;
        onClick && onClick();
      }}
      onMouseDown={onMouseDown}
    >
      {children}
      {editMode && <span className="furn-edit-handle">✥</span>}
    </div>
  );
}

// ── L1: Guild Hall ──
function GuildHallScene({ agentPos, spriteStyle, moods, quests, bubbles, walkTick, positions, setPositions, onAgentClick, onAgentRightClick, onFurnitureClick, draggingId, setDraggingId, draggingFurnId, setDraggingFurnId, editMode }) {
  const pets = usePets(PETS);

  return (
    <>
      {/* Wall */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '14%',
        background: 'linear-gradient(180deg, var(--wood-dark) 0%, var(--wood-mid) 70%, var(--wood-dark) 100%)',
        borderBottom: '3px solid var(--ink)', zIndex: 1 }}>
        <div style={{ position: 'absolute', inset: 0,
          backgroundImage: `repeating-linear-gradient(90deg, rgba(0,0,0,0.3) 0 2px, transparent 2px 48px)` }} />
      </div>

      {/* Tower-style parapet at the sky/floor border */}
      <div className="tower-railing" style={{ top: '14%' }}>
        <div className="tower-pillar" style={{ left: 0 }}></div>
        <div className="tower-pillar" style={{ right: 0 }}></div>
      </div>

      {/* Medieval window (no glass) — on the wall (above battlements) */}
      <div className="med-window" style={{ top: '2%', left: '50%', transform: 'translateX(-50%)', width: '90px', height: '60px' }}></div>

      <div style={{ position: 'absolute', top: '4%', left: '20%', zIndex: 2 }}>
        <BannerSprite scale={3} color="#dc2626" />
      </div>
      <div style={{ position: 'absolute', top: '4%', left: '78%', zIndex: 2 }}>
        <BannerSprite scale={3} color="#22c55e" />
      </div>

      {/* interactive bookshelves */}
      <div className="interactive-fx" data-furn-id="bookshelf-l" style={{ position: 'absolute', top: '18%', left: '4%' }} onClick={() => onFurnitureClick('bookshelf-l')}>
        <BookshelfSprite scale={2} />
      </div>
      <div className="interactive-fx" data-furn-id="bookshelf-r" style={{ position: 'absolute', top: '18%', right: '4%' }} onClick={() => onFurnitureClick('bookshelf-r')}>
        <BookshelfSprite scale={2} />
      </div>

      {/* anvil / cauldron / chest */}
      <div className="interactive-fx" data-furn-id="anvil" style={{ position: 'absolute', top: '52%', left: '60%' }} onClick={() => onFurnitureClick('anvil')}>
        <AnvilSprite scale={2} />
      </div>
      <div className="interactive-fx" data-furn-id="cauldron" style={{ position: 'absolute', top: '52%', left: '68%' }} onClick={() => onFurnitureClick('cauldron')}>
        <CauldronSprite scale={2} />
      </div>
      <div className="interactive-fx" data-furn-id="chest" style={{ position: 'absolute', top: '52%', left: '38%' }} onClick={() => onFurnitureClick('chest')}>
        <ChestSprite scale={2} />
      </div>

      {/* torches */}
      {[15, 35, 55, 75, 92].map(x => (
        <React.Fragment key={x}>
          <div className="torch" style={{ left: `${x}%`, top: '20%', cursor: 'pointer' }}
            onClick={() => onFurnitureClick('torch-' + x)}>
            <div className="flame"></div>
            <div className="stick"></div>
          </div>
          <div className="torch-glow" style={{ left: `${x}%`, top: '24%' }}></div>
        </React.Fragment>
      ))}

      {/* ANISA EXCLUSIVE OFFICE — bigger, decorated, "tangan kanan Bima" */}
      <div className="anisa-office" style={{ position: 'absolute', top: '22%', left: '4%', width: '24%', height: '32%', zIndex: 2 }}>
        <div className="room-label" style={{ top: '-12px', left: '8px' }}>OFFICE: ANISA · LIEUTENANT</div>
        {/* desk + chair inside */}
        <div style={{ position: 'absolute', bottom: '18%', left: '50%', transform: 'translateX(-50%)' }}>
          <BigDeskSprite scale={2.2} />
        </div>
        {/* trophy / banner */}
        <div style={{ position: 'absolute', top: '14%', left: '10%' }}>
          <BannerSprite scale={2} color="#fcd34d" />
        </div>
        {/* potted plant */}
        <div style={{ position: 'absolute', bottom: '6%', right: '6%' }}>
          <PlantSprite scale={2} />
        </div>
        {/* portrait of Bima on the wall */}
        <div style={{ position: 'absolute', top: '14%', right: '10%', width: 36, height: 44,
          background: 'var(--ink)', border: '3px solid var(--gold)', padding: 3 }}>
          <div style={{ width: '100%', height: '70%', background: 'var(--crimson)' }}></div>
          <div style={{ position: 'absolute', bottom: 2, left: 4, right: 4, height: 8,
            background: 'var(--gold)', fontFamily: 'var(--pix)', fontSize: 5, color: 'var(--ink)',
            textAlign: 'center', lineHeight: '8px' }}>♛BIMA</div>
        </div>
      </div>

      {/* BIGGER desks for each agent (except anisa who has her own office, and bima who roams) */}
      {AGENTS.filter(a => a.id !== 'anisa' && a.id !== 'bima').map((a) => (
        <React.Fragment key={a.id + '-station'}>
          <div className="interactive-fx" data-furn-id={'desk-' + a.id} style={{ position: 'absolute', left: `${a.x - 5}%`, top: `${a.y + 8}%`, zIndex: 4 }}
            onClick={() => onFurnitureClick('desk-' + a.id)}>
            <BigDeskSprite scale={2} />
            <div className="station-label" style={{ left: '50%', bottom: '-14px' }}>{a.name}</div>
          </div>
          <div className="interactive-fx" data-furn-id={'monitor-' + a.id} style={{ position: 'absolute', left: `${a.x - 4}%`, top: `${a.y - 6}%`, zIndex: 4 }}
            onClick={() => onFurnitureClick('monitor-' + a.id)}>
            <MonitorSprite scale={2} glow={a.shirt} />
          </div>
        </React.Fragment>
      ))}

      {/* SOFA + FIREPLACE */}
      <div className="interactive-fx" data-furn-id="sofa-l1" style={{ position: 'absolute', top: '46%', right: '24%', zIndex: 3 }} onClick={() => onFurnitureClick('sofa-l1')}>
        <SofaSprite scale={2.2} />
      </div>
      <div className="interactive-fx" data-furn-id="sofa-fire-l1" style={{ position: 'absolute', top: '40%', right: '28%' }} onClick={() => onFurnitureClick('sofa-fire-l1')}>
        <div className="sofa-fire" style={{ position: 'relative', top: 0, right: 0 }}></div>
      </div>

      {/* Plants */}
      <div className="interactive-fx" data-furn-id="plant-l1-1" style={{ position: 'absolute', top: '50%', left: '2%', zIndex: 3 }} onClick={() => onFurnitureClick('plant-l1-1')}><PlantSprite scale={2} /></div>
      <div className="interactive-fx" data-furn-id="plant-l1-2" style={{ position: 'absolute', top: '88%', right: '2%', zIndex: 3 }} onClick={() => onFurnitureClick('plant-l1-2')}><PlantSprite scale={2} /></div>

      {/* Door */}
      <div className="interactive-fx" data-furn-id="door-l1" style={{ position: 'absolute', top: '22%', right: '4%', zIndex: 3, cursor: 'pointer' }}
        onClick={() => onFurnitureClick('door-l1')}>
        <DoorSprite scale={2} />
      </div>

      {/* PETS */}
      {pets.map(p => (
        <div key={p.id} className="pet-sprite" style={{ left: `${p.x}%`, top: `${p.y}%` }}
          onClick={(e) => { e.stopPropagation(); onFurnitureClick && onFurnitureClick('pet-' + p.id); }}>
          <PetSprite pet={p} frame={p.frame} scale={2} />
          <span className="pet-tag">{p.name} · {p.species}</span>
        </div>
      ))}

      {/* AGENTS di-render terpisah lewat <AgentLayer> di Stage, supaya bisa
         filter per floor dan ikut tampil juga di War Room / Tower Roost. */}
    </>
  );
}

// ── AgentLayer: render semua agent yg di-floor saat ini ──
function AgentLayer({ floor, agentPos, spriteStyle, moods, quests, bubbles, walkTick, draggingId, setDraggingId, onAgentClick, onAgentRightClick }) {
  return (
    <>
      {AGENTS.map(a => {
        const pos = agentPos[a.id];
        if (!pos) return null;
        const agentFloor = pos.floor || 1;
        if (agentFloor !== floor) return null;
        const m = moods[a.id];
        const q = quests[a.id];
        const sig = AGENT_SIGNATURES[a.id];
        return (
          <React.Fragment key={a.id}>
            {q && <QuestBar quest={q} x={pos?.x || a.x} y={pos?.y || a.y} color={sig?.aura} />}
            <Agent
              agent={a} pos={pos} style={spriteStyle}
              mood={m?.mood ?? 60}
              bubble={bubbles?.[a.id]}
              walkTick={walkTick}
              dragging={draggingId === a.id}
              onClick={(e) => onAgentClick(a, e)}
              onContextMenu={(e) => onAgentRightClick(a, e)}
              onMouseDown={(e) => {
                if (e.button === 0) {
                  const startX = e.clientX, startY = e.clientY;
                  const move = (ev) => {
                    if (Math.hypot(ev.clientX - startX, ev.clientY - startY) > 6) {
                      setDraggingId(a.id);
                      window.removeEventListener('mousemove', move);
                    }
                  };
                  window.addEventListener('mousemove', move);
                  window.addEventListener('mouseup', () => window.removeEventListener('mousemove', move), { once: true });
                }
              }}
            />
          </React.Fragment>
        );
      })}
    </>
  );
}

// ── L2: War Room ──
function WarRoomScene() {
  return (
    <>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '14%',
        background: 'linear-gradient(180deg, var(--stone-dark), var(--stone-mid))',
        borderBottom: '3px solid var(--ink)', zIndex: 1 }} />
      <div className="tower-railing" style={{ top: '14%' }}>
        <div className="tower-pillar" style={{ left: 0 }}></div>
        <div className="tower-pillar" style={{ right: 0 }}></div>
      </div>
      <div className="med-window" style={{ top: '2%', left: '20%', width: 60, height: 50 }}></div>
      <div className="med-window" style={{ top: '2%', right: '20%', width: 60, height: 50 }}></div>
      <div className="room-label" style={{ top: '18%', left: '4%' }}>WAR COUNCIL CHAMBER</div>
      <div style={{ position: 'absolute', top: '40%', left: '50%', transform: 'translate(-50%,-50%)', zIndex: 4 }}>
        <RoundTableSprite scale={6} />
      </div>
      {[
        { l: '36%', t: '32%' }, { l: '50%', t: '24%' }, { l: '64%', t: '32%' },
        { l: '36%', t: '52%' }, { l: '50%', t: '60%' }, { l: '64%', t: '52%' },
      ].map((c, i) => (
        <div key={i} style={{ position: 'absolute', left: c.l, top: c.t, transform: 'translate(-50%,-50%)',
          width: '16px', height: '16px', background: 'var(--wood-mid)', border: '2px solid var(--ink)', zIndex: 3 }} />
      ))}
      <div style={{ position: 'absolute', top: '24%', left: '8%', width: '120px', height: '80px',
        background: 'var(--parchment)', border: '3px solid var(--ink)', zIndex: 3,
        backgroundImage: `radial-gradient(circle at 30% 40%, var(--wood-dark) 2px, transparent 3px),
                         radial-gradient(circle at 70% 60%, var(--wood-dark) 2px, transparent 3px),
                         radial-gradient(circle at 50% 80%, var(--ember) 2px, transparent 3px)` }}>
        <div style={{ position: 'absolute', bottom: 2, right: 2, fontFamily: 'var(--pix)', fontSize: 5, color: 'var(--ink)' }}>WORLD MAP</div>
      </div>
      {[20, 80].map(x => (
        <React.Fragment key={x}>
          <div className="torch" style={{ left: `${x}%`, top: '20%' }}><div className="flame"></div><div className="stick"></div></div>
          <div className="torch-glow" style={{ left: `${x}%`, top: '24%' }}></div>
        </React.Fragment>
      ))}
      <div style={{ position: 'absolute', bottom: '8%', left: '50%', transform: 'translateX(-50%)',
        fontFamily: 'var(--term)', fontSize: 18, color: 'var(--gold)', textShadow: '2px 2px 0 var(--ink)' }}>
        ⚔ Strategic planning in session ⚔
      </div>
    </>
  );
}

// ── L3: Tower Roost ──
function TowerRoostScene({ walkTick }) {
  return (
    <>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '46%',
        background: 'linear-gradient(180deg, #1a0e08 0%, #2a1810 60%, var(--wood-dark) 100%)', zIndex: 1 }} />
      {Array.from({ length: 40 }).map((_, i) => (
        <div key={i} style={{ position: 'absolute',
          top: `${Math.random() * 35}%`, left: `${Math.random() * 100}%`,
          width: '2px', height: '2px', background: '#fff',
          animation: `pulse ${1 + Math.random() * 2}s steps(2, end) infinite`, zIndex: 2 }} />
      ))}

      {/* MOON with glow */}
      <div className="moon-glow" style={{ top: '4%', right: '8%', width: 90, height: 90 }}></div>
      <div style={{ position: 'absolute', top: '8%', right: '12%', width: '40px', height: '40px',
        borderRadius: '50%', background: 'var(--parchment)',
        boxShadow: '0 0 24px rgba(244,196,138,0.7), inset -8px -2px 0 rgba(0,0,0,0.2)', zIndex: 3 }} />

      {/* battlements at the parapet edge */}
      <div className="tower-railing" style={{ top: '40%' }}>
        <div className="tower-pillar" style={{ left: 0 }}></div>
        <div className="tower-pillar" style={{ right: 0 }}></div>
      </div>

      <div className="room-label" style={{ top: '50%', left: '4%' }}>TOWER ROOST · QUIET ZONE</div>

      {/* sofa */}
      <div style={{ position: 'absolute', bottom: '24%', left: '20%', zIndex: 4 }}>
        <SofaSprite scale={2.2} />
      </div>
      {/* fireplace in front of sofa */}
      <div className="sofa-fire" style={{ bottom: '20%', left: '28%' }}></div>

      {/* Big fireplace in corner */}
      <div style={{ position: 'absolute', bottom: '20%', right: '20%', width: '80px', height: '80px',
        background: 'var(--stone-dark)', border: '3px solid var(--ink)', zIndex: 4 }}>
        <div style={{ position: 'absolute', inset: 8, background: '#000', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', bottom: 0, left: '20%', right: '20%', height: '70%',
            background: 'radial-gradient(ellipse at center bottom, var(--gold), var(--orange) 40%, var(--ember) 70%, transparent 90%)',
            animation: 'flicker 0.4s infinite alternate' }} />
        </div>
      </div>

      {/* tea cup */}
      <div style={{ position: 'absolute', bottom: '36%', left: '46%',
        width: '24px', height: '16px', background: 'var(--parchment)', border: '2px solid var(--ink)', zIndex: 4 }}>
        <div style={{ position: 'absolute', top: -4, left: 4, right: 4, height: 4,
          background: 'rgba(244,196,138,0.5)', filter: 'blur(2px)', animation: 'rise 2s ease-out infinite' }} />
      </div>

      {/* sleeping cat on the sofa */}
      <div style={{ position: 'absolute', bottom: '32%', left: '22%', zIndex: 5 }}>
        <CatSprite frame={(walkTick || 0) % 2} scale={2} />
      </div>

      <div style={{ position: 'absolute', bottom: '8%', left: '50%', transform: 'translateX(-50%)',
        fontFamily: 'var(--term)', fontSize: 18, color: 'var(--text-dim)', textShadow: '2px 2px 0 var(--ink)' }}>
        ☾ Adventurers resting · MP regen +5/s ☾
      </div>
    </>
  );
}

// ── Single agent on the scene ──
function Agent({ agent, pos, style, mood, bubble, walkTick, dragging, onClick, onContextMenu, onMouseDown }) {
  const status = pos?.status || agent.statusDefault;
  const sig = AGENT_SIGNATURES[agent.id];
  const showAura = status === 'working' || status === 'busy';
  const showSigEmoji = status === 'busy' && sig;
  const [emojiTick, setEmojiTick] = React.useState(0);
  const walking = !!pos?.walking || dragging;
  const facing = pos?.facing ?? 1;

  React.useEffect(() => {
    if (!showSigEmoji) return;
    const i = setInterval(() => setEmojiTick(t => t + 1), 2400);
    return () => clearInterval(i);
  }, [showSigEmoji]);

  const currentEmoji = sig && sig.idleEmoji[emojiTick % sig.idleEmoji.length];
  const accessoryGlyph = ACCESSORY_GLYPHS[agent.accessory] || null;

  const transitioning = !!pos?.transitioning;
  return (
    <div className={`agent ${style} ${dragging ? 'dragging' : ''} ${transitioning ? 'transitioning' : ''}`}
      style={{
        left: `${pos?.x || agent.x}%`, top: `${pos?.y || agent.y}%`,
        transition: dragging ? 'none' : 'left 0.12s linear, top 0.12s linear',
        cursor: dragging ? 'grabbing' : 'grab',
      }}
      onClick={onClick}
      onContextMenu={onContextMenu}
      onMouseDown={onMouseDown}
    >
      {showAura && sig && (
        <div className="agent-aura" style={{
          background: `radial-gradient(circle, ${sig.aura}66 0%, transparent 70%)`
        }} />
      )}
      {bubble && (
        <SpeechBubble
          key={bubble.key}
          text={bubble.text}
          color={sig?.aura}
          fading={bubble.fading}
        />
      )}
      <span className="agent-tag">{agent.name}</span>
      {accessoryGlyph && (
        <span className="accessory" style={{ color: accessoryGlyph.color }}>{accessoryGlyph.glyph}</span>
      )}
      <div className={`agent-bob ${walking ? 'walking' : 'idle'}`}
        style={{ transform: `scaleX(${facing})` }}>
        <div style={{ position: 'relative' }}>
          <AgentSprite agent={agent} style={style} scale={2} frame={walkTick % 2} />
          {agent.accessory && <AccessoryOverlay kind={agent.accessory} scale={2} />}
        </div>
        <div className={`agent-status ${status}`}></div>
        <MoodRing mood={mood} />
        {showSigEmoji && currentEmoji && (
          <span key={emojiTick} className="signature-emoji" style={{ color: sig.aura }}>
            {currentEmoji}
          </span>
        )}
      </div>
      <div className="agent-shadow"></div>
    </div>
  );
}

// Accessory definitions per agent
const ACCESSORY_GLYPHS = {
  crown:    { glyph: '♛', color: '#fcd34d' },
  circlet:  { glyph: '◆', color: '#fcd34d' },
  hood:     { glyph: '▲', color: '#22d3ee' },
  monocle:  { glyph: '◎', color: '#f97316' },
  glasses:  { glyph: '◫', color: '#a3e635' },
  flower:   { glyph: '✿', color: '#fde047' },
  goggles:  { glyph: '⊙', color: '#dc2626' },
  beret:    { glyph: '◐', color: '#f472b6' },
  scroll:   { glyph: '✎', color: '#60a5fa' },
};

// ── Unified Weather ──
function Weather({ mode, weather }) {
  const dust = React.useMemo(() =>
    Array.from({ length: 18 }).map((_, i) => ({
      id: i, left: Math.random() * 100, top: 30 + Math.random() * 60,
      delay: -Math.random() * 6, duration: 5 + Math.random() * 6,
    })), []);
  const rain = React.useMemo(() =>
    Array.from({ length: 80 }).map((_, i) => ({
      id: i, left: Math.random() * 100,
      delay: -Math.random() * 1.5, duration: 0.6 + Math.random() * 0.5,
    })), []);
  const comets = React.useMemo(() =>
    Array.from({ length: 14 }).map((_, i) => ({
      id: i, left: 20 + Math.random() * 100,
      delay: -Math.random() * 2, duration: 1.2 + Math.random() * 1,
    })), []);
  const snow = React.useMemo(() =>
    Array.from({ length: 60 }).map((_, i) => ({
      id: i, left: Math.random() * 100,
      delay: -Math.random() * 6, duration: 4 + Math.random() * 4,
      size: 2 + Math.random() * 4,
    })), []);
  const embers = React.useMemo(() =>
    Array.from({ length: 12 }).map((_, i) => ({
      id: i, left: 10 + Math.random() * 80, top: 60 + Math.random() * 30,
      delay: -Math.random() * 3, duration: 2.5 + Math.random() * 2,
    })), []);

  const showRain  = weather === 'rain'  || weather === 'storm' || mode === 'storm';
  const showDust  = weather === 'dust';
  const showSnow  = weather === 'snow';
  const showComet = weather === 'comet';

  return (
    <div className="particles">
      {showDust && dust.map(d => (
        <div key={d.id} className="dust" style={{ left: `${d.left}%`, top: `${d.top}%`,
          animationDelay: `${d.delay}s`, animationDuration: `${d.duration}s` }} />
      ))}
      {showRain && rain.map(r => (
        <div key={r.id} className="rain" style={{ left: `${r.left}%`,
          animationDelay: `${r.delay}s`, animationDuration: `${r.duration}s` }} />
      ))}
      {showSnow && snow.map(s => (
        <div key={s.id} className="snow" style={{ left: `${s.left}%`, width: s.size, height: s.size,
          animationDelay: `${s.delay}s`, animationDuration: `${s.duration}s` }} />
      ))}
      {showComet && comets.map(c => (
        <div key={c.id} className="comet" style={{ left: `${c.left}%`,
          animationDelay: `${c.delay}s`, animationDuration: `${c.duration}s` }} />
      ))}
      {embers.map(e => (
        <div key={e.id} className="ember" style={{ left: `${e.left}%`, top: `${e.top}%`,
          animationDelay: `${e.delay}s`, animationDuration: `${e.duration}s` }} />
      ))}
    </div>
  );
}

Object.assign(window, { Stage, Agent, Weather, ACCESSORY_GLYPHS });
