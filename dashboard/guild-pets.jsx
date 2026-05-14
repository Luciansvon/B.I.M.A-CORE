/* GUILD PETS — slime, baby dragon, cat sprites + behavior
   ──────────────────────────────────────────────────────── */

function SlimeSprite({ scale = 2, color = '#7fd88c', accent = '#4ca858', frame = 0 }) {
  const palette = { 'g': color, 'd': accent, 'h': '#ffffff' };
  const f0 = [
    '...kkkkk...',
    '..kggggggk.',
    '.kggghggggk',
    'kgggggggggk',
    'kgddgggdggk',
    'kgggggggggk',
    'kkkkkkkkkkk',
  ];
  const f1 = [
    '..kkkkkkk..',
    '.kgggggggk.',
    'kggghggggk.',
    'kgggggggggk',
    'kgddgggdggk',
    'kkkkkkkkkkk',
    '...........',
  ];
  return <PixelSprite grid={frame ? f1 : f0} palette={palette} scale={scale} />;
}

function BabyDragonSprite({ scale = 2, color = '#dc2626', accent = '#fcd34d', frame = 0 }) {
  const palette = { 'r': color, 'y': accent, 'k': '#1a0e08', 'w': '#ffffff' };
  const f0 = [
    '..kkk...kkk...',
    '.krrrk.krrrk..',
    '.krrrkkrrrk...',
    'kkrrrrrrrrkk..',
    'kyrrwrrrwrrkkk',
    'kyrrkrrrkrrrrk',
    'kkrrrrrrrrrrkk',
    '.kyrrrrrrrrk..',
    '.kkyyrrrryyk..',
    '..kkkk.kkkk...',
  ];
  const f1 = [
    '..kkk...kkk...',
    '.krrrk.krrrk..',
    'kkrrrkkrrrk...',
    '.krrrrrrrrkk..',
    'kyrrwrrrwrrkkk',
    'kyrrkrrrkrrrrk',
    '.krrrrrrrrrrkk',
    '.kyrrrrrrrrk..',
    '..kkyyrrryyk..',
    '...kkk.kkkk...',
  ];
  return <PixelSprite grid={frame ? f1 : f0} palette={palette} scale={scale} />;
}

function CatSprite({ scale = 2, color = '#fcd34d', accent = '#1a0e08', frame = 0 }) {
  const palette = { 'y': color, 'k': accent, 'w': '#ffffff', 'p': '#fda4af' };
  const f0 = [
    'k.k....k.k.',
    'kykk..kkyk.',
    'kyyykkkyykk',
    'kywyyyyywyk',
    'kyykpkkyyyk',
    'kkyyyyyykkk',
    '.kyykyykk..',
    '.kkk.kkk...',
  ];
  const f1 = [
    'k.k....k.k.',
    'kykk..kkyk.',
    'kyyykkkyykk',
    'kywyyyyywyk',
    'kyykpkkyyyk',
    'kkyyyyyykkk',
    '..kykkkyk..',
    '..kk...kk..',
  ];
  return <PixelSprite grid={frame ? f1 : f0} palette={palette} scale={scale} />;
}

function PetSprite({ pet, frame = 0, scale = 2 }) {
  if (pet.id === 'slime')  return <SlimeSprite color={pet.color} accent={pet.accent} frame={frame} scale={scale} />;
  if (pet.id === 'dragon') return <BabyDragonSprite color={pet.color} accent={pet.accent} frame={frame} scale={scale} />;
  return <CatSprite color={pet.color} accent={pet.accent} frame={frame} scale={scale} />;
}

// Pet wandering hook
function usePets(initialPets) {
  const [pets, setPets] = React.useState(() => initialPets.map(p => ({ ...p, frame: 0 })));
  React.useEffect(() => {
    const i = setInterval(() => {
      setPets(prev => prev.map(p => {
        const dx = (Math.random() - 0.5) * 1.2;
        const dy = (Math.random() - 0.5) * 0.6;
        return {
          ...p,
          x: Math.max(4, Math.min(96, p.x + dx)),
          y: Math.max(75, Math.min(94, p.y + dy)),
          frame: (p.frame + 1) % 2,
        };
      }));
    }, 700);
    return () => clearInterval(i);
  }, []);
  return pets;
}

Object.assign(window, { SlimeSprite, BabyDragonSprite, CatSprite, PetSprite, usePets });
