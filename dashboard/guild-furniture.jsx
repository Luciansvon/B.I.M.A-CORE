/* GUILD FURNITURE — additional pixel sprites for office-style props
   ───────────────────────────────────────────────────────────────── */

// Projector screen (rolled-down, mounted on wall)
function ProjectorScreenSprite({ scale = 2 }) {
  const grid = [
    'kkkkkkkkkkkkk',
    'kMMMMMMMMMMMk',
    'kwwwwwwwwwwwk',
    'kwwwwwwwwwwwk',
    'kwwwooowwwwwk',
    'kwwwwoowwwwwk',
    'kwwwwwwwwwwwk',
    'kwwwwwwwwwwwk',
    'kwwwyyywwwwwk',
    'kwwwwwwwwwwwk',
    'kkkkkkkkkkkkk',
    '..kkkkkkkkk..',
  ];
  return <PixelSprite grid={grid} scale={scale} />;
}

// Server rack (tall, blinking lights)
function ServerRackSprite({ scale = 2 }) {
  const grid = [
    'kkkkkkkkkk',
    'kKKKKKKKKk',
    'kKgKgKgKKk',
    'kKKKKKKKKk',
    'kKbKbKbKKk',
    'kKKKKKKKKk',
    'kKgKgKgKKk',
    'kKKKKKKKKk',
    'kKbKbKbKKk',
    'kKKKKKKKKk',
    'kKgKgKgKKk',
    'kKKKKKKKKk',
    'kKyKKKKyKk',
    'kkkkkkkkkk',
  ];
  return <PixelSprite grid={grid} scale={scale} />;
}

// Filing cabinet (3-drawer)
function FilingCabinetSprite({ scale = 2 }) {
  const grid = [
    'kkkkkkkkk',
    'kMMMMMMMk',
    'kMmMMMmMk',
    'kMMyMyMMk',
    'kMMMMMMMk',
    'kMmMMMmMk',
    'kMMyMyMMk',
    'kMMMMMMMk',
    'kMmMMMmMk',
    'kMMyMyMMk',
    'kMMMMMMMk',
    'kkkkkkkkk',
  ];
  return <PixelSprite grid={grid} scale={scale} />;
}

// Bin (trash can)
function BinSprite({ scale = 2 }) {
  const grid = [
    '.kkkkkk.',
    'kKKKKKKk',
    'kLLLLLLk',
    'kLkLkLLk',
    'kLLLLLLk',
    'kLkLkLLk',
    'kLLLLLLk',
    'kLkLkLLk',
    'kLLLLLLk',
    '.kkkkkk.',
  ];
  return <PixelSprite grid={grid} scale={scale} />;
}

// Elevator door (vertical, sliding)
function ElevatorDoorSprite({ scale = 2 }) {
  const grid = [
    'kkkkkkkkk',
    'kMMMkMMMk',
    'kMmMkMmMk',
    'kMMMkMMMk',
    'kMMyKyMMk',
    'kMMMkMMMk',
    'kMmMkMmMk',
    'kMMMkMMMk',
    'kMmMkMmMk',
    'kMMMkMMMk',
    'kMMMkMMMk',
    'kMmMkMmMk',
    'kMMMkMMMk',
    'kMMMkMMMk',
    'kkkkkkkkk',
  ];
  return <PixelSprite grid={grid} scale={scale} />;
}

// Wall window (parchment view to outside)
function WindowSprite({ scale = 2 }) {
  const grid = [
    'kkkkkkkkkkk',
    'kMMMMMMMMMk',
    'kMyyykyyyMk',
    'kMyyykyyyMk',
    'kMyyykyyyMk',
    'kMkkkkkkkMk',
    'kMyyykyyyMk',
    'kMyyykyyyMk',
    'kMyyykyyyMk',
    'kMMMMMMMMMk',
    'kkkkkkkkkkk',
  ];
  return <PixelSprite grid={grid} scale={scale} />;
}

// Generic crate / box (for furn-obj-N)
function CrateSprite({ scale = 2 }) {
  const grid = [
    'kkkkkkkk',
    'kMMMMMMk',
    'kMmMMmMk',
    'kMMmmMMk',
    'kMmMMmMk',
    'kMMmmMMk',
    'kMmMMmMk',
    'kkkkkkkk',
  ];
  return <PixelSprite grid={grid} scale={scale} />;
}

// Furniture catalog — id prefix → component + default size
const FURNITURE_CATALOG = {
  'projector-screen': { Comp: ProjectorScreenSprite, w: 26, h: 24 },
  'server-rack':      { Comp: ServerRackSprite,      w: 20, h: 28 },
  'filing-cabinet':   { Comp: FilingCabinetSprite,   w: 18, h: 24 },
  'bin':              { Comp: BinSprite,             w: 16, h: 20 },
  'elevator-door':    { Comp: ElevatorDoorSprite,    w: 18, h: 30 },
  'window':           { Comp: WindowSprite,          w: 22, h: 22 },
  'obj':              { Comp: CrateSprite,           w: 16, h: 16 },
};

function lookupFurniture(id) {
  // ids like "furn-projector-screen-25", "furn-obj-24", "window"
  if (id === 'window') return { type: 'window', ...FURNITURE_CATALOG.window };
  const match = id.match(/^furn-([a-z-]+?)(?:-\d+)?$/);
  if (!match) return null;
  let type = match[1];
  // strip trailing number from compound names too
  type = type.replace(/-\d+$/, '');
  if (FURNITURE_CATALOG[type]) return { type, ...FURNITURE_CATALOG[type] };
  return null;
}

Object.assign(window, {
  ProjectorScreenSprite, ServerRackSprite, FilingCabinetSprite,
  BinSprite, ElevatorDoorSprite, WindowSprite, CrateSprite,
  FURNITURE_CATALOG, lookupFurniture,
});
