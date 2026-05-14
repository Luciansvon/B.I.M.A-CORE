/* GUILD SPRITES — pixel art sprites built from inline SVG
   Each sprite is a small adventurer with class-themed gear.
   ──────────────────────────────────────────────────────── */

// ── Tiny pixel-grid renderer ──
// Convert a string-grid into <rect> pixels. Each char is a color key.
const PALETTE_BASE = {
  '.': null,            // transparent
  'k': '#1a0e08',       // outline / ink
  'K': '#000000',       // hard black
  's': '#fed7aa',       // skin
  'S': '#d49a6f',       // skin shadow
  'w': '#ffffff',       // white (eye)
  'r': '#dc2626',       // red
  'g': '#a3e635',       // green
  'b': '#22d3ee',       // cyan
  'y': '#fcd34d',       // gold
  'o': '#f97316',       // orange
  'p': '#a78bfa',       // purple
  'P': '#f472b6',       // pink
  'm': '#7c2d12',       // brown dark
  'M': '#92400e',       // brown
  'L': '#3a2418',       // boot dark
  'B': '#22c55e',       // bright green
};

function gridToSvg(grid, palette = {}) {
  const pal = { ...PALETTE_BASE, ...palette };
  const rows = grid;
  const h = rows.length;
  const w = rows[0].length;
  const rects = [];
  for (let y = 0; y < h; y++) {
    let runColor = null, runStart = 0;
    for (let x = 0; x <= w; x++) {
      const c = x < w ? rows[y][x] : null;
      const col = c == null ? null : (pal[c] === undefined ? null : pal[c]);
      if (col !== runColor) {
        if (runColor) {
          rects.push(<rect key={`${x}-${y}-${runStart}`} x={runStart} y={y} width={x - runStart} height={1} fill={runColor} />);
        }
        runColor = col;
        runStart = x;
      }
    }
  }
  return { rects, w, h };
}

// Walk-cycle helper: shift sprite vertically alternate frames
function PixelSpriteAnim({ grid, palette, scale = 2, frame = 0, style }) {
  return <PixelSprite grid={grid} palette={palette} scale={scale} style={{ transform: frame ? 'translateY(-1px)' : 'translateY(0)', ...style }} />;
}

function PixelSprite({ grid, palette, scale = 2, style }) {
  const { rects, w, h } = React.useMemo(() => gridToSvg(grid, palette), [grid, palette]);
  return (
    <svg
      width={w * scale} height={h * scale}
      viewBox={`0 0 ${w} ${h}`}
      shapeRendering="crispEdges"
      style={{ display: 'block', imageRendering: 'pixelated', ...style }}
    >
      {rects}
    </svg>
  );
}

// ── Agent sprite (chibi) — 14×18 grid ──
// Class differentiated by hair (h) and shirt (c) and cape (P).
// Letters: h=hair, c=chest/shirt, P=cape, w=weapon, K=outline, s=skin
const CHIBI_GRID = [
  '....KKKKKK....',
  '...KhhhhhhK...',
  '..KhhhhhhhhK..',
  '..KhhsssshhK..',
  '..KhsswssswK..',  // eyes
  '..KsssKssKsK..',
  '..KsswwwwsKK..',
  '...KsssssKK...',
  '..KKcccccKK...',
  '..KcPcccPcK...',
  '.KPcccccccPK..',
  '.KPcccccccPK..',
  '.KPcccccccPK..',
  '..KccccccK....',
  '..KcccKcccK...',
  '..KLLKKKLLK...',
  '..KLLK.KLLK...',
  '..KKK...KKK...',
];

// Tall sprite — 14×22
const TALL_GRID = [
  '....KKKKKK....',
  '...KhhhhhhK...',
  '..KhhhhhhhhK..',
  '..KhhssssShK..',
  '..KhsswssswK..',
  '..KsssKssKsK..',
  '..KsswwwwsKK..',
  '...KKsssKK....',
  '..KKcccccKK...',
  '..KcPcccPcK...',
  '.KPcccccccPK..',
  '.KPcccccccPK..',
  '.KPcccccccPK..',
  '.KPcccccccPK..',
  '..KccccccK....',
  '..KcccKcccK...',
  '..KccKKKccK...',
  '..KLLK.KLLK...',
  '..KLLK.KLLK...',
  '..KKK...KKK...',
  '..............',
  '..............',
];

function AgentSprite({ agent, style = 'chibi', scale = 2, frame = 0 }) {
  const grid = style === 'tall' ? TALL_GRID : CHIBI_GRID;
  const palette = {
    'h': agent.hair,
    'c': agent.shirt,
    'P': agent.cape,
    's': agent.skin,
    'S': '#c89060',
  };
  // frame 1: shift legs slightly for walk illusion
  return <PixelSprite grid={grid} palette={palette} scale={scale}
    style={{ transform: frame ? 'translateY(-1px)' : 'translateY(0)', transition: 'transform 0.1s' }} />;
}

// ── BIG desk (workstation, wider) — 18x10 ──
const BIG_DESK_GRID = [
  '..................',
  '.MMMMMMMMMMMMMMMM.',
  'MmmmmmmmmmmmmmmmmM',
  'Mmmmyymmmmmmyymmmm',
  'MmmmmmmmmmmmmmmmmM',
  'KKKKKKKKKKKKKKKKKK',
  'K.K.K.K.K.K.K.K.KK',
  'K.K.K.K.K.K.K.K.KK',
  'K.K.K.K.K.K.K.K.KK',
  'KKKKKKKKKKKKKKKKKK',
];
function BigDeskSprite({ scale = 2 }) {
  return <PixelSprite grid={BIG_DESK_GRID} scale={scale} />;
}

// ── Sofa — 18x10 ──
const SOFA_GRID = [
  'mmmmmmmmmmmmmmmmmm',
  'mPPPPPPPPPPPPPPPPm',
  'mPrrrrPrrrrPrrrrPm',
  'mPrrrrPrrrrPrrrrPm',
  'mPPPPPPPPPPPPPPPPm',
  'mPrrrrrrrrrrrrrrPm',
  'mPrrrrrrrrrrrrrrPm',
  'mPPPPPPPPPPPPPPPPm',
  'mmmmmmmmmmmmmmmmmm',
  'KKK..........KKK..',
];
function SofaSprite({ scale = 2 }) {
  const palette = { 'P': '#7c2d12', 'r': '#dc2626' };
  return <PixelSprite grid={SOFA_GRID} palette={palette} scale={scale} />;
}

// ── Workstation / desk (anvil-ish) — pixel ──
const DESK_GRID = [
  '..............',
  '..MMMMMMMMMM..',
  '.MmmmmmmmmmmM.',
  'MmmmmmmmmmmmmM',
  'KKKKKKKKKKKKKK',
  'K.K.K.K.K.K.KK',
  'K.K.K.K.K.K.KK',
  'KKKKKKKKKKKKKK',
];

function DeskSprite({ scale = 3 }) {
  return <PixelSprite grid={DESK_GRID} scale={scale} />;
}

// ── Monitor / scrying screen — 14x10 ──
const MONITOR_GRID = [
  'KKKKKKKKKKKKKK',
  'KbbbbbbbbbbbbK',
  'KbgggbbbbbgbK.',
  'Kbgbgbbbgbgbb.',
  'KbgggbbgggbbbK',
  'KbbbbbbbbbbbbK',
  'KbbbbbBBbbbbbK',
  'KKKKKKKKKKKKKK',
  '..KKKKKKKKKK..',
  '.KMMMMMMMMMMK.',
];

function MonitorSprite({ scale = 2, glow = '#22d3ee' }) {
  const palette = { 'b': glow, 'B': '#a3e635' };
  return <PixelSprite grid={MONITOR_GRID} palette={palette} scale={scale} />;
}

// ── Door / archway ──
const DOOR_GRID = [
  '..MMMMMM..',
  '.MmmmmmmM.',
  'MmmmmmmmmM',
  'MmKKKKKKmM',
  'MmKkkkkKmM',
  'MmKkbkkKmM',
  'MmKkkkkKmM',
  'MmKkkkkKmM',
  'MmKkkkkKmM',
  'MmKkkkkKmM',
  'MmKKKKKKmM',
  'MmmmmmmmmM',
  'KKKKKKKKKK',
];

function DoorSprite({ scale = 3 }) {
  return <PixelSprite grid={DOOR_GRID} scale={scale} />;
}

// ── Bookshelf ──
const BOOKSHELF_GRID = [
  'MMMMMMMMMMMM',
  'MmmmmmmmmmmM',
  'MmrrrgggbbbM',
  'MmrrrgggbbbM',
  'MmrrrgggbbbM',
  'MmmmmmmmmmmM',
  'MmyyyppprbbM',
  'MmyyyppprbbM',
  'MmyyyppprbbM',
  'MmmmmmmmmmmM',
  'MmrrgggyyybM',
  'MmrrgggyyybM',
  'MmrrgggyyybM',
  'MmmmmmmmmmmM',
  'MMMMMMMMMMMM',
];

function BookshelfSprite({ scale = 3 }) {
  return <PixelSprite grid={BOOKSHELF_GRID} scale={scale} />;
}

// ── Anvil + fire (forge) ──
const ANVIL_GRID = [
  '..oooo....',
  '.oyyyo....',
  'ooyyyoo...',
  '.KKKKKK...',
  '.KkkkkK...',
  'KKKKKKKK..',
  'K.K.K.KK..',
  'KKKKKKKK..',
];

function AnvilSprite({ scale = 3 }) {
  return <PixelSprite grid={ANVIL_GRID} scale={scale} />;
}

// ── Cauldron ──
const CAULDRON_GRID = [
  '..gggg..',
  '.gggggg.',
  'KKKKKKKK',
  'KmmmmmmK',
  'KmmmmmmK',
  'KmmmmmmK',
  '.KmmmmK.',
  '..KKKK..',
];

function CauldronSprite({ scale = 3 }) {
  return <PixelSprite grid={CAULDRON_GRID} scale={scale} />;
}

// ── Vault chest ──
const CHEST_GRID = [
  '.MMMMMMMM.',
  'MyyyyyyyyM',
  'MyKyyyyKyM',
  'MyyyKKyyyM',
  'MyyyKKyyyM',
  'MyKyyyyKyM',
  'MyyyyyyyyM',
  'KKKKKKKKKK',
];

function ChestSprite({ scale = 3 }) {
  return <PixelSprite grid={CHEST_GRID} scale={scale} />;
}

// ── Round table (war room) ──
const ROUND_TABLE_GRID = [
  '..KKKKKKKK..',
  '.KMmmmmmmMK.',
  'KMmmmmmmmmMK',
  'KMmmKKKKmmMK',
  'KMmmmmmmmmMK',
  'KMmmmmmmmmMK',
  '.KMmmmmmmMK.',
  '..KKKKKKKK..',
];

function RoundTableSprite({ scale = 3 }) {
  return <PixelSprite grid={ROUND_TABLE_GRID} scale={scale} />;
}

// ── Banner ──
const BANNER_GRID = [
  'KKKKKKKK',
  'KrrrrrrK',
  'KryyyyrK',
  'KryKKyrK',
  'KryyyyrK',
  'KrrrrrrK',
  'KrrrrrrK',
  '.KrrrrK.',
  '..KrrK..',
  '...KK...',
];

function BannerSprite({ scale = 3, color = '#dc2626' }) {
  return <PixelSprite grid={BANNER_GRID} palette={{ 'r': color }} scale={scale} />;
}

// ── Brazier (fire bowl) ──
const BRAZIER_GRID = [
  '...oo...',
  '..oyo...',
  '.oyyyo..',
  '.ooyo...',
  'KKKKKKKK',
  'KmmmmmmK',
  '.KKKKKK.',
  '..K..K..',
  '..K..K..',
];

function BrazierSprite({ scale = 3 }) {
  return <PixelSprite grid={BRAZIER_GRID} scale={scale} />;
}

// ── Plant in pot ──
const PLANT_GRID = [
  '..ggg...',
  '.gBgBg..',
  'gggggg..',
  '.gBgg...',
  '..gg....',
  '.MMMM...',
  'MmmmmM..',
  'MKKKKM..',
];

function PlantSprite({ scale = 3 }) {
  return <PixelSprite grid={PLANT_GRID} scale={scale} />;
}

// ── Visual accessory overlay rendered ON the chibi sprite ──
// Coordinates assume the chibi 14x18 grid; scale must match sprite scale.
function AccessoryOverlay({ kind, scale = 2 }) {
  const SZ = (n) => n * scale;
  const wrap = { position: 'absolute', top: 0, left: 0, pointerEvents: 'none' };

  if (kind === 'crown') {
    // gold spiked crown sitting on hair (row 0-1)
    return <svg style={wrap} width={SZ(14)} height={SZ(18)} viewBox="0 0 14 18" shapeRendering="crispEdges">
      <rect x="3" y="0" width="1" height="2" fill="#fcd34d"/>
      <rect x="5" y="0" width="1" height="3" fill="#fcd34d"/>
      <rect x="7" y="0" width="1" height="2" fill="#fcd34d"/>
      <rect x="9" y="0" width="1" height="3" fill="#fcd34d"/>
      <rect x="11" y="0" width="1" height="2" fill="#fcd34d"/>
      <rect x="3" y="1" width="9" height="2" fill="#fcd34d"/>
      <rect x="3" y="0" width="9" height="1" fill="#1a0e08" opacity="0.0"/>
      <rect x="6" y="2" width="1" height="1" fill="#dc2626"/>
      <rect x="9" y="2" width="1" height="1" fill="#dc2626"/>
      <rect x="3" y="3" width="9" height="1" fill="#92400e"/>
    </svg>;
  }
  if (kind === 'circlet') {
    return <svg style={wrap} width={SZ(14)} height={SZ(18)} viewBox="0 0 14 18" shapeRendering="crispEdges">
      <rect x="3" y="2" width="9" height="1" fill="#fcd34d"/>
      <rect x="7" y="3" width="1" height="1" fill="#fcd34d"/>
      <rect x="6" y="3" width="1" height="1" fill="#dc2626"/>
    </svg>;
  }
  if (kind === 'hood') {
    // ranger hood drawn over the head
    return <svg style={wrap} width={SZ(14)} height={SZ(18)} viewBox="0 0 14 18" shapeRendering="crispEdges">
      <rect x="2" y="0" width="11" height="1" fill="#155e75"/>
      <rect x="1" y="1" width="13" height="2" fill="#155e75"/>
      <rect x="1" y="3" width="2" height="3" fill="#155e75"/>
      <rect x="11" y="3" width="2" height="3" fill="#155e75"/>
      <rect x="0" y="2" width="1" height="2" fill="#0e3a45"/>
      <rect x="13" y="2" width="1" height="2" fill="#0e3a45"/>
    </svg>;
  }
  if (kind === 'monocle') {
    return <svg style={wrap} width={SZ(14)} height={SZ(18)} viewBox="0 0 14 18" shapeRendering="crispEdges">
      <rect x="8" y="4" width="3" height="1" fill="#fcd34d"/>
      <rect x="8" y="6" width="3" height="1" fill="#fcd34d"/>
      <rect x="8" y="5" width="1" height="1" fill="#fcd34d"/>
      <rect x="10" y="5" width="1" height="1" fill="#fcd34d"/>
      <rect x="11" y="6" width="1" height="3" fill="#fcd34d"/>
    </svg>;
  }
  if (kind === 'glasses') {
    return <svg style={wrap} width={SZ(14)} height={SZ(18)} viewBox="0 0 14 18" shapeRendering="crispEdges">
      <rect x="3" y="4" width="3" height="2" fill="none" stroke="#1a0e08" strokeWidth="0.5"/>
      <rect x="8" y="4" width="3" height="2" fill="none" stroke="#1a0e08" strokeWidth="0.5"/>
      <rect x="3" y="4" width="3" height="2" fill="#a3e635" opacity="0.4"/>
      <rect x="8" y="4" width="3" height="2" fill="#a3e635" opacity="0.4"/>
      <rect x="6" y="5" width="2" height="1" fill="#1a0e08"/>
    </svg>;
  }
  if (kind === 'flower') {
    return <svg style={wrap} width={SZ(14)} height={SZ(18)} viewBox="0 0 14 18" shapeRendering="crispEdges">
      <rect x="2" y="2" width="1" height="1" fill="#f472b6"/>
      <rect x="3" y="1" width="1" height="1" fill="#f472b6"/>
      <rect x="3" y="3" width="1" height="1" fill="#f472b6"/>
      <rect x="4" y="2" width="1" height="1" fill="#f472b6"/>
      <rect x="3" y="2" width="1" height="1" fill="#fde047"/>
    </svg>;
  }
  if (kind === 'goggles') {
    return <svg style={wrap} width={SZ(14)} height={SZ(18)} viewBox="0 0 14 18" shapeRendering="crispEdges">
      <rect x="3" y="3" width="3" height="3" fill="#1a0e08"/>
      <rect x="8" y="3" width="3" height="3" fill="#1a0e08"/>
      <rect x="4" y="4" width="1" height="1" fill="#22d3ee"/>
      <rect x="9" y="4" width="1" height="1" fill="#22d3ee"/>
      <rect x="6" y="4" width="2" height="1" fill="#1a0e08"/>
    </svg>;
  }
  if (kind === 'beret') {
    return <svg style={wrap} width={SZ(14)} height={SZ(18)} viewBox="0 0 14 18" shapeRendering="crispEdges">
      <rect x="3" y="0" width="9" height="2" fill="#831843"/>
      <rect x="2" y="1" width="11" height="1" fill="#831843"/>
      <rect x="11" y="0" width="1" height="1" fill="#fcd34d"/>
    </svg>;
  }
  if (kind === 'scroll') {
    return <svg style={wrap} width={SZ(14)} height={SZ(18)} viewBox="0 0 14 18" shapeRendering="crispEdges">
      <rect x="0" y="10" width="3" height="4" fill="#fed7aa"/>
      <rect x="0" y="10" width="3" height="1" fill="#92400e"/>
      <rect x="0" y="13" width="3" height="1" fill="#92400e"/>
    </svg>;
  }
  return null;
}

Object.assign(window, {
  PixelSprite, PixelSpriteAnim, AgentSprite,
  DeskSprite, BigDeskSprite, SofaSprite,
  MonitorSprite, DoorSprite, BookshelfSprite,
  AnvilSprite, CauldronSprite, ChestSprite, RoundTableSprite,
  BannerSprite, BrazierSprite, PlantSprite,
  AccessoryOverlay,
});
