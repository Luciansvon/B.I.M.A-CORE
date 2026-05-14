// Three ANISA sidebar variations + the wrapper artboard component.
// Each variation is a complete laptop-screen frame: desktop mockup + sidebar.

const ART_W = 1440;
const ART_H = 900;

function ArtboardFrame({ children, label }) {
  return (
    <div style={{
      width: ART_W, height: ART_H,
      background: '#0a0a0b',
      position: 'relative',
      overflow: 'hidden',
      fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      <DesktopMock />
      {children}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// VARIATION A — Edge Dock
// Sharp, full-height sidebar nailed to the right edge.
// ═══════════════════════════════════════════════════════════════════════════
function VariantA({ state, collapsed, onCollapseToggle }) {
  const T = window.ANISA_T;
  const width = 400;

  if (collapsed) {
    return (
      <div style={{
        position: 'absolute', top: 0, right: 0, height: '100%',
        width: 44, background: T.surface,
        borderLeft: `1px solid ${T.border}`,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        padding: '12px 0', gap: 10, zIndex: 10,
      }}>
        <button onClick={onCollapseToggle} style={{
          width: 32, height: 32, borderRadius: 8, border: 0,
          background: 'transparent', color: T.textSec, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icons.ChevronLeft size={16} />
        </button>
        <div style={{ position: 'relative' }}>
          <AnisaMark size={28} />
          {/* Notification dot — there's a fresh reply waiting */}
          <span style={{
            position: 'absolute', top: -2, right: -2,
            width: 10, height: 10, borderRadius: '50%',
            background: T.accent,
            boxShadow: '0 0 0 2px #151619, 0 0 8px rgba(16,185,129,0.6)',
          }}>
            <span style={{
              position: 'absolute', inset: 0, borderRadius: '50%',
              background: T.accent, opacity: 0.6,
              animation: 'anisaPulse 1.6s ease-out infinite',
            }} />
          </span>
        </div>
        <div style={{ width: 28, height: 1, background: T.border }} />
        <button style={{ width: 32, height: 32, borderRadius: 8, border: 0, background: 'transparent', color: T.textSec, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icons.Camera size={15} />
        </button>
        <button style={{ width: 32, height: 32, borderRadius: 8, border: 0, background: 'transparent', color: T.textSec, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icons.History size={15} />
        </button>
        <button style={{ width: 32, height: 32, borderRadius: 8, border: 0, background: 'transparent', color: T.textSec, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icons.Plus size={15} />
        </button>
      </div>
    );
  }

  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, height: '100%',
      width, background: T.bg,
      borderLeft: `1px solid ${T.border}`,
      display: 'flex', flexDirection: 'column',
      zIndex: 10,
      boxShadow: '-12px 0 32px rgba(0,0,0,0.35)',
    }}>
      {/* Resize edge */}
      <div style={{
        position: 'absolute', left: -3, top: 0, bottom: 0, width: 6,
        cursor: 'col-resize', zIndex: 5,
      }}>
        <div style={{ position: 'absolute', left: 2, top: '50%', transform: 'translateY(-50%)', width: 2, height: 30, borderRadius: 2, background: T.border }} />
      </div>
      <ChatHeader onCollapse={onCollapseToggle} />
      <ChatBody state={state} />
      <InputArea capturing={state === 'capture'} />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// VARIATION B — Floating Card
// Rounded panel floating with margin around it, subtle glass effect.
// ═══════════════════════════════════════════════════════════════════════════
function VariantB({ state, collapsed, onCollapseToggle }) {
  const T = window.ANISA_T;

  if (collapsed) {
    return (
      <button onClick={onCollapseToggle} style={{
        position: 'absolute', bottom: 24, right: 24,
        height: 56, padding: '0 18px 0 14px', borderRadius: 28,
        background: T.bg, border: `1px solid ${T.border}`,
        display: 'flex', alignItems: 'center', gap: 10, zIndex: 10,
        cursor: 'pointer',
        boxShadow: '0 12px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(16,185,129,0.08)',
        color: T.text, fontFamily: 'Inter, sans-serif', fontSize: 13, fontWeight: 500,
      }}>
        <div style={{ position: 'relative' }}>
          <AnisaMark size={32} />
          <span style={{
            position: 'absolute', top: -1, right: -1,
            width: 10, height: 10, borderRadius: '50%',
            background: T.accent,
            boxShadow: '0 0 0 2px #0d0e10',
          }}>
            <span style={{
              position: 'absolute', inset: 0, borderRadius: '50%',
              background: T.accent, opacity: 0.6,
              animation: 'anisaPulse 1.6s ease-out infinite',
            }} />
          </span>
        </div>
        <span>Ask ANISA</span>
        <span style={{
          padding: '2px 6px', borderRadius: 4,
          background: T.surface2, color: T.textMute,
          fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 500,
        }}>⌘ J</span>
      </button>
    );
  }

  return (
    <div style={{
      position: 'absolute', top: 60, right: 16, bottom: 16,
      width: 420,
      background: T.bgGlass,
      backdropFilter: 'blur(20px) saturate(140%)',
      WebkitBackdropFilter: 'blur(20px) saturate(140%)',
      border: `1px solid ${T.border}`,
      borderRadius: 18,
      display: 'flex', flexDirection: 'column',
      zIndex: 10,
      overflow: 'hidden',
      boxShadow: '0 24px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.02) inset',
    }}>
      {/* Resize edge */}
      <div style={{
        position: 'absolute', left: -3, top: '50%', transform: 'translateY(-50%)',
        width: 6, height: 60, cursor: 'col-resize',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{ width: 3, height: 36, borderRadius: 2, background: T.border }} />
      </div>
      <ChatHeader onCollapse={onCollapseToggle} compact />
      <ChatBody state={state} />
      <InputArea capturing={state === 'capture'} />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// VARIATION C — Rail + Thread
// Two-column: narrow always-visible history rail + main chat panel.
// ═══════════════════════════════════════════════════════════════════════════
function VariantC({ state, collapsed, onCollapseToggle }) {
  const T = window.ANISA_T;
  const railW = 64;
  const chatW = 400;

  if (collapsed) {
    return (
      <div style={{
        position: 'absolute', top: 0, right: 0, height: '100%',
        width: railW, background: T.bg,
        borderLeft: `1px solid ${T.border}`,
        display: 'flex', flexDirection: 'column',
        zIndex: 10,
      }}>
        <div style={{ padding: '12px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <button onClick={onCollapseToggle} style={{ width: 36, height: 36, borderRadius: 8, border: 0, background: 'transparent', color: T.textSec, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icons.ChevronLeft size={16} />
          </button>
          <AnisaMark size={32} />
          <div style={{ width: 32, height: 1, background: T.border, margin: '4px 0' }} />
          <RailBtn active><Icons.Sparkle size={16} /></RailBtn>
          <RailBtn><Icons.History size={16} /></RailBtn>
          <RailBtn><Icons.Camera size={16} /></RailBtn>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, height: '100%',
      width: railW + chatW, display: 'flex',
      zIndex: 10,
      boxShadow: '-12px 0 32px rgba(0,0,0,0.4)',
    }}>
      {/* Rail with conversations */}
      <div style={{
        width: railW, background: '#0a0b0c',
        borderLeft: `1px solid ${T.border}`,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        padding: '14px 0', gap: 8,
      }}>
        <AnisaMark size={32} />
        <button title="New chat" style={{
          width: 40, height: 40, borderRadius: 10, border: `1px dashed ${T.border}`,
          background: 'transparent', color: T.textSec, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginTop: 4,
        }}>
          <Icons.Plus size={16} />
        </button>
        <div style={{ width: 32, height: 1, background: T.border, margin: '4px 0' }} />
        {/* Conversation avatars / dots */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, overflowY: 'auto', alignItems: 'center', width: '100%' }}>
          {ANISA_HISTORY.slice(0, 6).map((h, i) => (
            <button key={h.id} title={h.title} style={{
              width: 40, height: 40, borderRadius: 10, border: 0,
              background: h.active ? T.accentDim : T.surface,
              color: h.active ? T.accentText : T.textSec,
              boxShadow: h.active ? `inset 0 0 0 1.5px rgba(16,185,129,0.35)` : 'none',
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 13, fontWeight: 600, fontFamily: 'Inter, sans-serif',
              position: 'relative',
            }}>
              {/* Initials or first letter of title */}
              {h.title[0]}
              {h.active && <span style={{ position: 'absolute', left: -10, top: '50%', transform: 'translateY(-50%)', width: 3, height: 18, borderRadius: 2, background: T.accent }} />}
            </button>
          ))}
        </div>
        <button onClick={onCollapseToggle} style={{
          width: 36, height: 36, borderRadius: 8, border: 0,
          background: 'transparent', color: T.textSec, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icons.ChevronRight size={16} />
        </button>
      </div>

      {/* Main chat */}
      <div style={{
        width: chatW, background: T.bg,
        borderLeft: `1px solid ${T.borderFaint}`,
        display: 'flex', flexDirection: 'column',
        position: 'relative',
      }}>
        {/* Resize edge */}
        <div style={{
          position: 'absolute', left: -3, top: 0, bottom: 0, width: 6,
          cursor: 'col-resize', zIndex: 5,
        }}>
          <div style={{ position: 'absolute', left: 2, top: '50%', transform: 'translateY(-50%)', width: 2, height: 30, borderRadius: 2, background: T.border }} />
        </div>
        {/* Thread title header (different from other variants — shows thread context) */}
        <div style={{
          padding: '12px 16px', borderBottom: `1px solid ${T.borderFaint}`,
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text, letterSpacing: -0.1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Warna kursi 3D minimalis
            </div>
            <div style={{ fontSize: 11, color: T.textMute, marginTop: 2, display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: T.accent }} />
              Active · ANISA watching screen
            </div>
          </div>
          <HeaderBtn title="Pin"><Icons.Pin size={15} /></HeaderBtn>
          <HeaderBtn title="More"><Icons.More size={15} /></HeaderBtn>
        </div>
        <ChatBody state={state} />
        <InputArea capturing={state === 'capture'} />
      </div>
    </div>
  );
}

function RailBtn({ active, children }) {
  const T = window.ANISA_T;
  const [h, setH] = React.useState(false);
  return (
    <button onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)} style={{
      width: 40, height: 40, borderRadius: 10, border: 0,
      background: active ? T.accentDim : (h ? T.surface2 : 'transparent'),
      color: active ? T.accentText : T.textSec,
      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>{children}</button>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Artboard wrapper with state switcher overlay (above the chrome)
// ═══════════════════════════════════════════════════════════════════════════
function VariantArtboard({ Variant }) {
  const [state, setState] = React.useState('reply');
  const [collapsed, setCollapsed] = React.useState(false);

  return (
    <div style={{ position: 'relative', width: ART_W, height: ART_H + 56, fontFamily: 'Inter, sans-serif' }}>
      {/* State switcher above artboard */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 48,
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '0 4px',
      }}>
        <StateSwitcher value={state} onChange={setState} />
        <button onClick={() => setCollapsed(c => !c)} style={{
          padding: '6px 12px', borderRadius: 8,
          background: collapsed ? window.ANISA_T.accentDim : '#0a0a0b',
          border: `1px solid ${collapsed ? 'rgba(16,185,129,0.3)' : '#1a1d22'}`,
          color: collapsed ? window.ANISA_T.accentText : window.ANISA_T.textSec,
          fontSize: 11, fontFamily: 'Inter, sans-serif', fontWeight: 500,
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 5,
        }}>
          {collapsed ? 'Collapsed →' : '← Expanded'}
        </button>
      </div>
      <div style={{ position: 'absolute', top: 56, left: 0, width: ART_W, height: ART_H }}>
        <ArtboardFrame>
          <Variant state={state} collapsed={collapsed} onCollapseToggle={() => setCollapsed(c => !c)} />
        </ArtboardFrame>
      </div>
    </div>
  );
}

window.VariantA = VariantA;
window.VariantB = VariantB;
window.VariantC = VariantC;
window.VariantArtboard = VariantArtboard;
window.ART_W = ART_W;
window.ART_H = ART_H;
