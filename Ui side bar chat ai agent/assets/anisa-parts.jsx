// Shared chat UI parts used by all three ANISA variations.
// Each variation imports these and wraps them in its own shell chrome.

// ─────────── Theme tokens ───────────
const T = {
  bg: '#0d0e10',
  bgGlass: 'rgba(13, 14, 16, 0.78)',
  surface: '#151619',
  surface2: '#1c1e22',
  surface3: '#23262b',
  border: '#26292e',
  borderFaint: '#1d1f23',
  text: '#e7e9ec',
  textSec: '#9aa0a8',
  textMute: '#62676f',
  accent: '#10B981',
  accentDim: 'rgba(16, 185, 129, 0.14)',
  accentText: '#34d399',
};

window.ANISA_T = T;

// ─────────── ANISA brand mark ───────────
function AnisaMark({ size = 22 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: size * 0.32,
      background: `linear-gradient(135deg, ${T.accent} 0%, #059669 100%)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Inter, sans-serif', fontWeight: 700, fontSize: size * 0.5,
      color: '#02110a', letterSpacing: -0.5,
      boxShadow: `0 0 0 1px rgba(16,185,129,0.3), 0 2px 8px rgba(16,185,129,0.2)`,
    }}>A</div>
  );
}

// ─────────── State switcher (visible above each sidebar) ───────────
const ANISA_STATES = [
  { id: 'empty', label: 'Empty' },
  { id: 'capture', label: 'Capturing' },
  { id: 'typing', label: 'Thinking' },
  { id: 'streaming', label: 'Streaming' },
  { id: 'reply', label: 'Reply' },
  { id: 'history', label: 'History' },
];

function StateSwitcher({ value, onChange }) {
  return (
    <div style={{
      display: 'flex', gap: 4, padding: 4,
      background: '#0a0a0b', border: '1px solid #1a1d22',
      borderRadius: 10,
    }}>
      {ANISA_STATES.map(s => {
        const active = value === s.id;
        return (
          <button key={s.id} onClick={() => onChange(s.id)} style={{
            border: 0, padding: '5px 10px', borderRadius: 6,
            background: active ? '#1c1e22' : 'transparent',
            color: active ? T.text : T.textSec,
            fontSize: 11, fontFamily: 'Inter, sans-serif', fontWeight: 500,
            cursor: 'pointer', letterSpacing: 0.2,
            boxShadow: active ? `inset 0 0 0 1px ${T.border}` : 'none',
          }}>{s.label}</button>
        );
      })}
    </div>
  );
}

// ─────────── Header ───────────
function ChatHeader({ onCollapse, onHistory, compact, showResize }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: compact ? '10px 12px' : '12px 14px',
      borderBottom: `1px solid ${T.borderFaint}`,
      flex: '0 0 auto',
    }}>
      <AnisaMark size={compact ? 22 : 26} />
      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
        <div style={{ fontFamily: 'Inter, sans-serif', fontWeight: 600, fontSize: 14, color: T.text, letterSpacing: -0.1, lineHeight: 1.15 }}>
          ANISA
        </div>
        <div style={{ fontSize: 11, color: T.textMute, display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: T.accent, boxShadow: `0 0 6px ${T.accent}` }} />
          Watching your screen
        </div>
      </div>
      <HeaderBtn onClick={onHistory} title="History"><Icons.History size={15} /></HeaderBtn>
      <HeaderBtn title="New chat"><Icons.Plus size={15} /></HeaderBtn>
      <HeaderBtn title="Settings"><Icons.Settings size={15} /></HeaderBtn>
      {onCollapse && (
        <HeaderBtn onClick={onCollapse} title="Collapse"><Icons.ChevronRight size={15} /></HeaderBtn>
      )}
    </div>
  );
}

function HeaderBtn({ children, onClick, title }) {
  const [h, setH] = React.useState(false);
  return (
    <button onClick={onClick} title={title}
      onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{
        width: 28, height: 28, borderRadius: 7, border: 0,
        background: h ? T.surface2 : 'transparent',
        color: h ? T.text : T.textSec,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', flex: '0 0 auto',
    }}>{children}</button>
  );
}

// ─────────── Context chip (the "I see what you're looking at" indicator) ───────────
function ContextChip({ capturing }) {
  return (
    <div style={{
      margin: '12px 14px 0',
      padding: '8px 10px',
      borderRadius: 10,
      background: capturing ? T.accentDim : T.surface,
      border: `1px solid ${capturing ? 'rgba(16,185,129,0.35)' : T.borderFaint}`,
      display: 'flex', alignItems: 'center', gap: 10,
      fontFamily: 'Inter, sans-serif',
      transition: 'all 0.2s',
    }}>
      <div style={{
        width: 36, height: 28, borderRadius: 5,
        background: capturing
          ? `repeating-linear-gradient(45deg, rgba(16,185,129,0.4) 0 6px, rgba(16,185,129,0.15) 6px 12px)`
          : '#2a2d33',
        flex: '0 0 auto', position: 'relative', overflow: 'hidden',
        border: `1px solid ${capturing ? 'rgba(16,185,129,0.5)' : T.border}`,
      }}>
        {!capturing && (
          <div style={{ position: 'absolute', inset: 2, background: '#3a3f46', borderRadius: 3 }}>
            <div style={{ position: 'absolute', left: '50%', top: '55%', transform: 'translate(-50%,-50%)', width: 14, height: 10, background: '#8a6b4a', borderRadius: 1 }} />
            <div style={{ position: 'absolute', left: '50%', top: '40%', transform: 'translate(-50%,-50%)', width: 14, height: 8, background: '#c9bfae', borderRadius: 1 }} />
          </div>
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11.5, color: T.text, fontWeight: 500, lineHeight: 1.2 }}>
          {capturing ? 'Capturing screen…' : 'chair_lounge_v3.scene'}
        </div>
        <div style={{ fontSize: 10.5, color: T.textMute, marginTop: 1, fontFamily: 'JetBrains Mono, monospace' }}>
          {capturing ? 'Analyzing geometry & color' : 'Material tab · 1,248 verts'}
        </div>
      </div>
      <button title="Re-capture" style={{
        border: 0, background: 'transparent', color: T.textSec,
        padding: 4, cursor: 'pointer', display: 'flex',
      }}>
        <Icons.Camera size={14} />
      </button>
    </div>
  );
}

// ─────────── Quick prompt cards (empty state) ───────────
function QuickPrompts() {
  return (
    <div style={{ padding: '0 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
      {ANISA_QUICK_PROMPTS.map((p, i) => {
        const I = Icons[p.icon];
        return <QuickPromptItem key={i} icon={<I size={14} />} label={p.label} />;
      })}
    </div>
  );
}

function QuickPromptItem({ icon, label }) {
  const [h, setH] = React.useState(false);
  return (
    <button onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)} style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '10px 12px', borderRadius: 10,
      background: h ? T.surface2 : T.surface,
      border: `1px solid ${h ? T.border : T.borderFaint}`,
      color: T.text, fontSize: 12.5, fontFamily: 'Inter, sans-serif',
      cursor: 'pointer', textAlign: 'left', width: '100%',
      transition: 'all 0.12s',
    }}>
      <span style={{ color: T.accentText, display: 'flex' }}>{icon}</span>
      <span style={{ flex: 1 }}>{label}</span>
      <Icons.ChevronRight size={13} style={{ color: T.textMute }} />
    </button>
  );
}

// ─────────── Empty state body ───────────
function EmptyBody() {
  return (
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      <ContextChip capturing={false} />
      <div style={{ padding: '20px 14px 14px', fontFamily: 'Inter, sans-serif' }}>
        <div style={{ fontSize: 19, fontWeight: 600, color: T.text, letterSpacing: -0.4, lineHeight: 1.2 }}>
          Halo, gimana kabarmu?
        </div>
        <div style={{ fontSize: 13, color: T.textSec, marginTop: 6, lineHeight: 1.5 }}>
          Aku ANISA. Tanya apa aja tentang yang ada di layarmu — atau pilih salah satu di bawah.
        </div>
      </div>
      <QuickPrompts />
      <div style={{ padding: '20px 14px 14px', fontSize: 10.5, color: T.textMute, textTransform: 'uppercase', letterSpacing: 1.2, fontWeight: 600 }}>
        Recent
      </div>
      <div style={{ padding: '0 14px 16px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {ANISA_HISTORY.slice(0, 3).map(h => <HistoryItem key={h.id} item={h} compact />)}
      </div>
    </div>
  );
}

// ─────────── Capturing state body ───────────
function CapturingBody() {
  return (
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      <ContextChip capturing={true} />
      <div style={{ padding: '14px', flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 18 }}>
        <div style={{ position: 'relative', width: 140, height: 100, borderRadius: 12, overflow: 'hidden', border: `1px solid ${T.border}` }}>
          <div style={{ position: 'absolute', inset: 0, background: '#2c3137' }} />
          <div style={{ position: 'absolute', inset: 4, background: '#3a3f46', borderRadius: 8 }} />
          {/* Scanning line */}
          <div style={{
            position: 'absolute', left: 0, right: 0, top: 0, height: 28,
            background: `linear-gradient(180deg, transparent, ${T.accentDim}, ${T.accent})`,
            animation: 'anisaScan 1.6s linear infinite',
          }} />
          {/* Corner brackets */}
          {[[0,0], [1,0], [0,1], [1,1]].map(([x,y], i) => (
            <div key={i} style={{
              position: 'absolute', width: 14, height: 14,
              borderTop: y === 0 ? `2px solid ${T.accent}` : 'none',
              borderBottom: y === 1 ? `2px solid ${T.accent}` : 'none',
              borderLeft: x === 0 ? `2px solid ${T.accent}` : 'none',
              borderRight: x === 1 ? `2px solid ${T.accent}` : 'none',
              left: x === 0 ? 6 : 'auto', right: x === 1 ? 6 : 'auto',
              top: y === 0 ? 6 : 'auto', bottom: y === 1 ? 6 : 'auto',
            }} />
          ))}
        </div>
        <div style={{ textAlign: 'center', fontFamily: 'Inter, sans-serif' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: T.text, marginBottom: 4 }}>Reading your screen</div>
          <div style={{ fontSize: 12, color: T.textSec, lineHeight: 1.5, maxWidth: 240, fontFamily: 'JetBrains Mono, monospace' }}>
            detecting geometry · sampling colors · reading viewport
          </div>
        </div>
        <div style={{ width: '70%', height: 3, background: T.surface, borderRadius: 99, overflow: 'hidden' }}>
          <div style={{ width: '60%', height: '100%', background: T.accent, borderRadius: 99, animation: 'anisaProgress 1.4s ease-in-out infinite' }} />
        </div>
      </div>
    </div>
  );
}

// ─────────── User message bubble (with optional attached screenshot) ───────────
function UserMessage({ text, withScreenshot }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '6px 14px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, maxWidth: '88%' }}>
        {withScreenshot && <UserAttachedScreenshot />}
        <div style={{
          padding: '10px 13px',
          borderRadius: '14px 14px 4px 14px',
          background: T.surface2,
          border: `1px solid ${T.border}`,
          fontFamily: 'Inter, sans-serif',
          fontSize: 13, lineHeight: 1.5, color: T.text,
        }}>
          {text}
        </div>
      </div>
    </div>
  );
}

// Tiny screenshot thumbnail that the user attached when sending — mimics the
// real captured viewport so the question reads as "about THIS view".
function UserAttachedScreenshot() {
  return (
    <div style={{
      position: 'relative',
      width: 200, height: 130, borderRadius: 10, overflow: 'hidden',
      border: `1px solid ${T.border}`,
      background: '#2c3137',
      boxShadow: '0 4px 14px rgba(0,0,0,0.35)',
    }}>
      {/* Mini chair viewport */}
      <div style={{ position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 70%, #353a40 0%, #25282c 60%, #1c1e22 100%)',
      }} />
      {/* Grid floor */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: 'linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)',
        backgroundSize: '10px 10px',
        transform: 'perspective(200px) rotateX(60deg) translateZ(-20px)',
        transformOrigin: '50% 100%',
        maskImage: 'radial-gradient(ellipse at 50% 30%, black 30%, transparent 80%)',
      }} />
      {/* Tiny chair silhouette */}
      <div style={{ position: 'absolute', left: '50%', top: '52%', transform: 'translate(-50%,-50%)' }}>
        <div style={{ width: 56, height: 36, background: '#c9bfae', borderRadius: 2 }} />
        <div style={{ width: 56, height: 22, background: '#a89e8c', borderRadius: 2, marginTop: -2 }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2, padding: '0 4px' }}>
          <div style={{ width: 5, height: 14, background: '#8a6b4a' }} />
          <div style={{ width: 5, height: 14, background: '#8a6b4a' }} />
        </div>
      </div>
      {/* Attribution caption */}
      <div style={{
        position: 'absolute', left: 8, bottom: 6,
        display: 'flex', alignItems: 'center', gap: 4,
        padding: '3px 7px', borderRadius: 4,
        background: 'rgba(10,11,13,0.75)', backdropFilter: 'blur(6px)',
        fontSize: 10, color: T.text, fontFamily: 'JetBrains Mono, monospace',
      }}>
        <Icons.Camera size={10} />
        chair_lounge_v3 · viewport
      </div>
    </div>
  );
}

// ─────────── Typing indicator ───────────
function TypingBubble() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px' }}>
      <AnisaMark size={20} />
      <div style={{
        padding: '10px 14px', borderRadius: 14,
        background: T.surface, border: `1px solid ${T.borderFaint}`,
        display: 'flex', gap: 4, alignItems: 'center',
      }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: 6, height: 6, borderRadius: '50%', background: T.textSec,
            animation: `anisaDot 1.2s ease-in-out ${i * 0.18}s infinite`,
          }} />
        ))}
      </div>
      <span style={{ fontSize: 11.5, color: T.textMute, fontFamily: 'Inter, sans-serif' }}>ANISA sedang berpikir…</span>
    </div>
  );
}

// ─────────── Renderer for the rich reply ───────────
function ReplyRenderer({ blocks }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontFamily: 'Inter, sans-serif', fontSize: 13.5, lineHeight: 1.6, color: T.text }}>
      {blocks.map((b, i) => {
        if (b.type === 'p') return <p key={i} style={{ margin: 0 }} dangerouslySetInnerHTML={{ __html: mdBold(b.text) }} />;
        if (b.type === 'h') return <div key={i} style={{ fontSize: 12, fontWeight: 600, color: T.textSec, textTransform: 'uppercase', letterSpacing: 1, marginTop: 4 }}>{b.text}</div>;
        if (b.type === 'ul') return (
          <ul key={i} style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {b.items.map((it, j) => <li key={j}>{it}</li>)}
          </ul>
        );
        if (b.type === 'palette') return (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {b.items.map((p, j) => <PaletteCard key={j} num={j + 1} {...p} />)}
          </div>
        );
        return null;
      })}
    </div>
  );
}

function mdBold(s) {
  return s.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#fff;font-weight:600">$1</strong>');
}

function PaletteCard({ num, name, sub, colors }) {
  return (
    <div style={{
      padding: 10, borderRadius: 10,
      background: T.surface, border: `1px solid ${T.borderFaint}`,
      display: 'flex', alignItems: 'center', gap: 12,
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: 7,
        background: T.surface3, color: T.textSec,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 600, fontFamily: 'JetBrains Mono, monospace',
        flex: '0 0 auto',
      }}>{num}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 600, color: T.text, lineHeight: 1.2 }}>{name}</div>
        <div style={{ fontSize: 11, color: T.textMute, marginTop: 2 }}>{sub}</div>
      </div>
      <div style={{ display: 'flex', gap: 3, flex: '0 0 auto' }}>
        {colors.map((c, i) => (
          <div key={i} style={{ width: 16, height: 28, borderRadius: 3, background: c, border: '1px solid rgba(255,255,255,0.06)' }} />
        ))}
      </div>
    </div>
  );
}

// ─────────── ANISA message wrapper with action row ───────────
function AnisaMessage({ children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '4px 14px 0' }}>
      <div style={{ display: 'flex', gap: 10 }}>
        <AnisaMark size={22} />
        <div style={{ flex: 1, minWidth: 0, paddingTop: 1 }}>
          {children}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 2, paddingLeft: 32 }}>
        {[
          { i: 'Copy', t: 'Copy' },
          { i: 'Refresh', t: 'Regenerate' },
          { i: 'ThumbUp', t: 'Good' },
          { i: 'ThumbDown', t: 'Bad' },
        ].map(b => {
          const I = Icons[b.i];
          return <ActionBtn key={b.i} title={b.t}><I size={13} /></ActionBtn>;
        })}
      </div>
    </div>
  );
}

function ActionBtn({ children, title }) {
  const [h, setH] = React.useState(false);
  return (
    <button onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)} title={title} style={{
      width: 26, height: 26, borderRadius: 6, border: 0,
      background: h ? T.surface2 : 'transparent',
      color: h ? T.text : T.textMute, cursor: 'pointer',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>{children}</button>
  );
}

// ─────────── Reply state body ───────────
function ReplyBody() {
  const scrollRef = React.useRef(null);
  return (
    <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, paddingBottom: 12 }}>
      <ContextChip capturing={false} />
      <div style={{ padding: '4px 0' }}>
        <UserMessage text={ANISA_SAMPLE_USER_Q} withScreenshot />
      </div>
      <AnisaMessage>
        <ReplyRenderer blocks={ANISA_SAMPLE_REPLY} />
      </AnisaMessage>
      <div style={{ display: 'flex', gap: 6, padding: '4px 14px', flexWrap: 'wrap' }}>
        <FollowupChip>Render setting Blender</FollowupChip>
        <FollowupChip>Variasi material lain</FollowupChip>
        <FollowupChip>Padu dengan sofa?</FollowupChip>
      </div>
    </div>
  );
}

// ─────────── Streaming state body (partial reply being written) ───────────
function StreamingBody() {
  // Only the first two blocks of the reply, with the last paragraph truncated
  // mid-sentence + blinking caret.
  const partialBlocks = [
    ANISA_SAMPLE_REPLY[0],
    ANISA_SAMPLE_REPLY[1],
    { type: 'p', text: 'Kalau dindingnya off-white dan lantainya kayu terang, **#1 Walnut + Cream Bouclé** paling tidak ribet — kontrasnya cukup tanpa terlalu' },
  ];
  return (
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, paddingBottom: 12 }}>
      <ContextChip capturing={false} />
      <div style={{ padding: '4px 0' }}>
        <UserMessage text={ANISA_SAMPLE_USER_Q} withScreenshot />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '4px 14px 0' }}>
        <div style={{ display: 'flex', gap: 10 }}>
          <AnisaMark size={22} />
          <div style={{ flex: 1, minWidth: 0, paddingTop: 1, position: 'relative' }}>
            <ReplyRenderer blocks={partialBlocks} />
            {/* Blinking caret at end of last block */}
            <span style={{
              display: 'inline-block', width: 8, height: 14,
              background: T.accent, marginLeft: 2, verticalAlign: '-2px',
              animation: 'anisaCaret 1s steps(2, end) infinite',
              borderRadius: 1,
            }} />
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 32, marginTop: 2 }}>
          <button style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '5px 10px', borderRadius: 7,
            background: T.surface2, border: `1px solid ${T.border}`,
            color: T.textSec, fontSize: 11, fontFamily: 'Inter, sans-serif',
            cursor: 'pointer',
          }}>
            <Icons.Stop size={11} />
            Stop generating
          </button>
          <span style={{ fontSize: 10.5, color: T.textMute, fontFamily: 'JetBrains Mono, monospace' }}>
            ~ 240 tok · 18 tok/s
          </span>
        </div>
      </div>
    </div>
  );
}

function FollowupChip({ children }) {
  const [h, setH] = React.useState(false);
  return (
    <button onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)} style={{
      padding: '6px 10px', borderRadius: 99,
      background: h ? T.surface2 : 'transparent',
      border: `1px solid ${h ? T.border : T.borderFaint}`,
      color: h ? T.text : T.textSec, fontSize: 11.5,
      fontFamily: 'Inter, sans-serif', cursor: 'pointer',
      display: 'flex', alignItems: 'center', gap: 5,
    }}>
      <Icons.Sparkle size={11} style={{ color: T.accentText }} />
      {children}
    </button>
  );
}

// ─────────── Typing state body ───────────
function TypingBody() {
  return (
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <ContextChip capturing={false} />
      <div style={{ padding: '4px 0' }}>
        <UserMessage text={ANISA_SAMPLE_USER_Q} withScreenshot />
      </div>
      <TypingBubble />
    </div>
  );
}

// ─────────── History state body ───────────
function HistoryBody() {
  return (
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px 14px 6px', display: 'flex', gap: 8, alignItems: 'center' }}>
        <div style={{
          flex: 1, height: 32, borderRadius: 8,
          background: T.surface, border: `1px solid ${T.borderFaint}`,
          display: 'flex', alignItems: 'center', gap: 8, padding: '0 10px',
        }}>
          <Icons.Search size={14} style={{ color: T.textMute }} />
          <span style={{ fontSize: 12, color: T.textMute, fontFamily: 'Inter, sans-serif' }}>Search conversations</span>
        </div>
        <HeaderBtn title="New"><Icons.Plus size={15} /></HeaderBtn>
      </div>
      <div style={{ padding: '8px 14px 4px', fontSize: 10.5, color: T.textMute, textTransform: 'uppercase', letterSpacing: 1.2, fontWeight: 600 }}>Today</div>
      <div style={{ padding: '0 14px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {ANISA_HISTORY.slice(0, 2).map(h => <HistoryItem key={h.id} item={h} />)}
      </div>
      <div style={{ padding: '14px 14px 4px', fontSize: 10.5, color: T.textMute, textTransform: 'uppercase', letterSpacing: 1.2, fontWeight: 600 }}>Yesterday</div>
      <div style={{ padding: '0 14px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {ANISA_HISTORY.slice(2, 4).map(h => <HistoryItem key={h.id} item={h} />)}
      </div>
      <div style={{ padding: '14px 14px 4px', fontSize: 10.5, color: T.textMute, textTransform: 'uppercase', letterSpacing: 1.2, fontWeight: 600 }}>Earlier</div>
      <div style={{ padding: '0 14px 16px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {ANISA_HISTORY.slice(4).map(h => <HistoryItem key={h.id} item={h} />)}
      </div>
    </div>
  );
}

function HistoryItem({ item, compact }) {
  const [h, setH] = React.useState(false);
  return (
    <button onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)} style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: compact ? '8px 10px' : '9px 10px',
      borderRadius: 8, border: 0,
      background: item.active ? T.accentDim : (h ? T.surface2 : 'transparent'),
      color: T.text, cursor: 'pointer', textAlign: 'left',
      fontFamily: 'Inter, sans-serif',
      boxShadow: item.active ? `inset 0 0 0 1px rgba(16,185,129,0.25)` : 'none',
    }}>
      <Icons.History size={13} style={{ color: item.active ? T.accentText : T.textMute, flex: '0 0 auto' }} />
      <span style={{ flex: 1, fontSize: 12.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {item.title}
      </span>
      <span style={{ fontSize: 10.5, color: T.textMute, flex: '0 0 auto' }}>{item.time}</span>
    </button>
  );
}

// ─────────── Input area ───────────
function InputArea({ showActions = true, placeholder = "Tanya tentang yang di layar…", capturing }) {
  return (
    <div style={{ flex: '0 0 auto', padding: '10px 12px 12px', borderTop: `1px solid ${T.borderFaint}` }}>
      {showActions && (
        <div style={{ display: 'flex', gap: 4, marginBottom: 8, overflowX: 'auto' }}>
          {ANISA_QUICK_ACTIONS.map((a, i) => {
            const I = Icons[a.icon];
            return (
              <button key={i} style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '5px 9px', borderRadius: 7,
                background: T.surface, border: `1px solid ${T.borderFaint}`,
                color: T.textSec, fontSize: 11, fontFamily: 'Inter, sans-serif',
                cursor: 'pointer', flex: '0 0 auto',
              }}>
                <I size={12} />
                {a.label}
              </button>
            );
          })}
        </div>
      )}
      <div style={{
        background: T.surface, borderRadius: 12,
        border: `1px solid ${capturing ? 'rgba(16,185,129,0.4)' : T.border}`,
        padding: '10px 10px 8px',
        boxShadow: capturing ? `0 0 0 3px ${T.accentFaint || 'rgba(16,185,129,0.08)'}` : 'none',
        transition: 'border-color 0.15s',
      }}>
        <div style={{
          minHeight: 22, fontSize: 13, fontFamily: 'Inter, sans-serif',
          color: T.textMute, lineHeight: 1.5,
        }}>{placeholder}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 8 }}>
          <InputBtn title="Screenshot"><Icons.Camera size={15} /></InputBtn>
          <InputBtn title="Attach"><Icons.Attach size={15} /></InputBtn>
          <InputBtn title="Mic"><Icons.Mic size={15} /></InputBtn>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 10.5, color: T.textMute, fontFamily: 'JetBrains Mono, monospace', marginRight: 6 }}>
            DeepSeek · openrouter
          </span>
          <button style={{
            width: 30, height: 30, borderRadius: 8, border: 0,
            background: T.accent, color: '#022b1c',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer',
          }}>
            <Icons.Send size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}

function InputBtn({ children, title }) {
  const [h, setH] = React.useState(false);
  return (
    <button onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)} title={title} style={{
      width: 28, height: 28, borderRadius: 7, border: 0,
      background: h ? T.surface2 : 'transparent',
      color: h ? T.text : T.textSec, cursor: 'pointer',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>{children}</button>
  );
}

// ─────────── Typing state body (now also shows attached screenshot) ───────────
// Updated to use withScreenshot for consistency with reply/streaming.
// (TypingBody defined above didn't have it — we override the user msg here.)

// ─────────── Body switcher ───────────
function ChatBody({ state }) {
  switch (state) {
    case 'empty': return <EmptyBody />;
    case 'capture': return <CapturingBody />;
    case 'typing': return <TypingBody />;
    case 'streaming': return <StreamingBody />;
    case 'reply': return <ReplyBody />;
    case 'history': return <HistoryBody />;
    default: return <EmptyBody />;
  }
}

// expose
Object.assign(window, {
  AnisaMark, StateSwitcher, ChatHeader, HeaderBtn,
  ChatBody, InputArea,
});
