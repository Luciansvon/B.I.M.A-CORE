// DesktopMock — generic 3D editor background to demonstrate the "ANISA reads
// what's on my screen" context. NOT a copy of any specific app's chrome —
// minimal generic menu bar, left toolrail, right inspector, center viewport
// with a stylized chair built from a few primitives.

const DM = {
  bg: '#1a1c1f',
  chrome: '#222428',
  chrome2: '#2a2d31',
  border: '#33363b',
  text: '#cdd1d6',
  muted: '#6f757d',
  viewport: '#2c3137',
  viewportGrid: 'rgba(255,255,255,0.04)',
};

function ToolDot({ active, label }) {
  return (
    <div title={label} style={{
      width: 28, height: 28, borderRadius: 6,
      background: active ? '#3b3f45' : 'transparent',
      border: active ? '1px solid #4a4e54' : '1px solid transparent',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: active ? '#e5e7ea' : DM.muted, fontSize: 11,
    }}>{label}</div>
  );
}

function InspectorRow({ label, value, color }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '6px 10px', fontSize: 11, color: DM.text,
      borderBottom: `1px solid ${DM.border}`,
    }}>
      <span style={{ color: DM.muted }}>{label}</span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 }}>
        {color && <span style={{ width: 10, height: 10, borderRadius: 2, background: color, border: `1px solid ${DM.border}` }} />}
        {value}
      </span>
    </div>
  );
}

// Simple stylized chair built as a CSS 3D scene. No SVG figurative drawing —
// just transformed boxes.
function ChairScene({ scale = 1 }) {
  const wood = '#8a6b4a';
  const woodDark = '#5a432d';
  const fabric = '#c9bfae';
  const fabricDark = '#a89e8c';
  const s = scale;
  const px = (n) => `${n * s}px`;

  const face = (color, w, h, transform, extra = {}) => ({
    position: 'absolute',
    width: px(w), height: px(h),
    background: color,
    transformStyle: 'preserve-3d',
    transformOrigin: '0 0',
    transform,
    ...extra,
  });

  return (
    <div style={{
      position: 'relative',
      width: '100%', height: '100%',
      perspective: '1400px',
      perspectiveOrigin: '50% 60%',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        position: 'relative',
        width: 0, height: 0,
        transformStyle: 'preserve-3d',
        transform: 'rotateX(58deg) rotateZ(-32deg)',
      }}>
        {/* Seat top */}
        <div style={face(fabric, 180, 180, `translate3d(${px(-90)}, ${px(-90)}, ${px(80)})`)} />
        {/* Seat side (front) */}
        <div style={face(fabricDark, 180, 22, `translate3d(${px(-90)}, ${px(90)}, ${px(80)}) rotateX(-90deg)`)} />
        <div style={face(fabricDark, 22, 180, `translate3d(${px(90)}, ${px(-90)}, ${px(80)}) rotateY(90deg)`)} />
        {/* Backrest */}
        <div style={face(fabric, 180, 130, `translate3d(${px(-90)}, ${px(-90)}, ${px(80)}) rotateX(80deg) translateZ(${px(0)})`)} />
        <div style={face(fabricDark, 22, 130, `translate3d(${px(90)}, ${px(-90)}, ${px(80)}) rotateX(80deg) rotateY(90deg)`)} />
        {/* Legs (4 wood posts going down from seat corners) */}
        {[
          [-86, -86], [70, -86], [-86, 70], [70, 70],
        ].map(([x, y], i) => (
          <React.Fragment key={i}>
            <div style={face(wood, 16, 80, `translate3d(${px(x)}, ${px(y)}, ${px(0)}) rotateX(90deg)`)} />
            <div style={face(woodDark, 16, 80, `translate3d(${px(x + 16)}, ${px(y)}, ${px(0)}) rotateX(90deg) rotateY(90deg)`)} />
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

function DesktopMock() {
  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: DM.bg,
      color: DM.text,
      fontFamily: 'Inter, system-ui, sans-serif',
      fontSize: 12,
      overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Menu bar */}
      <div style={{
        height: 32, background: DM.chrome,
        borderBottom: `1px solid ${DM.border}`,
        display: 'flex', alignItems: 'center', gap: 18,
        paddingLeft: 80, paddingRight: 16,
        fontSize: 12, color: DM.text,
      }}>
        {/* Window dots (generic, not OS-specific) */}
        <div style={{ position: 'absolute', left: 14, top: 11, display: 'flex', gap: 6 }}>
          {['#ff5f57', '#febc2e', '#28c840'].map((c, i) => (
            <div key={i} style={{ width: 11, height: 11, borderRadius: '50%', background: c, opacity: 0.85 }} />
          ))}
        </div>
        {['File', 'Edit', 'View', 'Object', 'Render', 'Window', 'Help'].map(m => (
          <span key={m} style={{ color: DM.muted, fontSize: 12 }}>{m}</span>
        ))}
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: DM.muted }}>
          chair_lounge_v3.scene
        </span>
      </div>

      {/* Tabs row */}
      <div style={{
        height: 30, background: DM.chrome2, borderBottom: `1px solid ${DM.border}`,
        display: 'flex', alignItems: 'stretch', paddingLeft: 12,
      }}>
        {['Modeling', 'Sculpt', 'UV', 'Material', 'Render', 'Animation'].map((t, i) => (
          <div key={t} style={{
            padding: '0 14px', display: 'flex', alignItems: 'center',
            fontSize: 11, color: i === 3 ? '#e5e7ea' : DM.muted,
            borderRight: `1px solid ${DM.border}`,
            background: i === 3 ? DM.viewport : 'transparent',
            borderBottom: i === 3 ? `2px solid ${ANISA_ACCENT}` : '2px solid transparent',
          }}>{t}</div>
        ))}
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* Left toolrail */}
        <div style={{
          width: 44, background: DM.chrome,
          borderRight: `1px solid ${DM.border}`,
          padding: '8px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
        }}>
          {['◉', '⊞', '◐', '⊿', '✎', '⌖', '✦', '⬚'].map((g, i) => (
            <ToolDot key={i} active={i === 2} label={g} />
          ))}
          <div style={{ width: 24, height: 1, background: DM.border, margin: '6px 0' }} />
          {['⟲', '⤢', '⌗', '◯'].map((g, i) => (
            <ToolDot key={i} active={false} label={g} />
          ))}
        </div>

        {/* Viewport */}
        <div style={{
          flex: 1, position: 'relative',
          background: `
            radial-gradient(ellipse at 50% 70%, #353a40 0%, #25282c 60%, #1c1e22 100%),
            ${DM.viewport}
          `,
          overflow: 'hidden',
        }}>
          {/* Grid floor */}
          <div style={{
            position: 'absolute', inset: 0,
            backgroundImage: `
              linear-gradient(${DM.viewportGrid} 1px, transparent 1px),
              linear-gradient(90deg, ${DM.viewportGrid} 1px, transparent 1px)
            `,
            backgroundSize: '32px 32px',
            transform: 'perspective(800px) rotateX(62deg) translateZ(-80px)',
            transformOrigin: '50% 100%',
            opacity: 0.6,
            maskImage: 'radial-gradient(ellipse at 50% 30%, black 30%, transparent 80%)',
          }} />

          {/* Axis indicator (bottom-left) */}
          <div style={{ position: 'absolute', bottom: 12, left: 12, fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: DM.muted, lineHeight: 1.4 }}>
            <div><span style={{ color: '#e85959' }}>X</span> 0.000</div>
            <div><span style={{ color: '#7bbd3a' }}>Y</span> 0.000</div>
            <div><span style={{ color: '#3a8de8' }}>Z</span> 0.420</div>
          </div>

          {/* Top-right viewport HUD */}
          <div style={{ position: 'absolute', top: 10, right: 12, display: 'flex', gap: 6, fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: DM.muted }}>
            <span>Perspective</span><span>·</span><span>1/3</span>
          </div>

          {/* Chair */}
          <div style={{ position: 'absolute', inset: 0 }}>
            <ChairScene scale={0.9} />
          </div>

          {/* Selection bounding box hint */}
          <div style={{
            position: 'absolute', left: '50%', top: '50%',
            transform: 'translate(-50%, -42%)',
            width: 280, height: 280,
            border: `1px dashed ${ANISA_ACCENT}`,
            opacity: 0.5,
            pointerEvents: 'none',
            borderRadius: 2,
          }} />
          <div style={{
            position: 'absolute', left: '50%', top: '50%',
            transform: 'translate(140px, 100px)',
            fontFamily: 'JetBrains Mono, monospace', fontSize: 10,
            color: ANISA_ACCENT, opacity: 0.8,
          }}>Chair.001</div>
        </div>

        {/* Right inspector */}
        <div style={{
          width: 240, background: DM.chrome,
          borderLeft: `1px solid ${DM.border}`,
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ padding: '8px 10px', fontSize: 11, color: DM.muted, borderBottom: `1px solid ${DM.border}`, fontWeight: 500, letterSpacing: 0.3, textTransform: 'uppercase' }}>
            Object · Chair.001
          </div>
          <InspectorRow label="Position X" value="0.000" />
          <InspectorRow label="Position Y" value="0.000" />
          <InspectorRow label="Position Z" value="0.420" />
          <InspectorRow label="Rotation" value="0° 0° 0°" />
          <InspectorRow label="Scale" value="1.00" />
          <div style={{ padding: '10px 10px 6px', fontSize: 11, color: DM.muted, fontWeight: 500, letterSpacing: 0.3, textTransform: 'uppercase' }}>
            Material
          </div>
          <InspectorRow label="Base color" value="#C9BFAE" color="#c9bfae" />
          <InspectorRow label="Roughness" value="0.62" />
          <InspectorRow label="Metallic" value="0.00" />
          <InspectorRow label="Frame wood" value="#8A6B4A" color="#8a6b4a" />
          <div style={{ flex: 1 }} />
          <div style={{ padding: '6px 10px', fontSize: 10, color: DM.muted, borderTop: `1px solid ${DM.border}`, fontFamily: 'JetBrains Mono, monospace' }}>
            Verts 1,248 · Tris 2,360
          </div>
        </div>
      </div>

      {/* Status bar */}
      <div style={{
        height: 22, background: DM.chrome,
        borderTop: `1px solid ${DM.border}`,
        display: 'flex', alignItems: 'center', gap: 16,
        padding: '0 12px', fontSize: 10, color: DM.muted,
        fontFamily: 'JetBrains Mono, monospace',
      }}>
        <span>Saved · 2m ago</span>
        <span>·</span>
        <span>GPU 38%</span>
        <span>·</span>
        <span>RAM 4.1GB</span>
        <div style={{ flex: 1 }} />
        <span style={{ color: ANISA_ACCENT }}>● ANISA active</span>
      </div>
    </div>
  );
}

window.DesktopMock = DesktopMock;
