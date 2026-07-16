/* GUILD DATA — agents, pets, items, logs, lore
   ─────────────────────────────────────── */

const AGENTS = [
  {
    id: 'bima', name: 'BIMA', role: 'Guild Leader', class: 'Lord Commander',
    floor: 1, x: 14, y: 32,
    hair: '#1f2937', shirt: '#7c1d1d', cape: '#fcd34d', skin: '#fed7aa',
    accessory: 'crown',
    bio: 'Pemimpin tertinggi guild. Tangan kanan-nya: ANISA. Visi besar, eksekusi tegas.',
    sigil: '♛', weapon: 'Blade of Sovereignty', quote: 'Guild ini bergerak atas perintahku. Anisa, jalankan.',
    stats: { hp: 100, mp: 100, level: 60, tasks: 9999, latency: 50, errors: 0.0 },
    statusDefault: 'working',
  },
  {
    id: 'anisa', name: 'ANISA', role: 'Lieutenant / Orchestrator', class: 'Right Hand of Bima',
    floor: 1, x: 22, y: 38,
    hair: '#a78bfa', shirt: '#fcd34d', cape: '#b45309', skin: '#fed7aa',
    accessory: 'circlet',
    bio: 'Tangan kanan Bima. Pecah perintah Lord Bima jadi quest paralel buat tim.',
    sigil: '◆', weapon: 'Staff of Delegation', quote: 'Perintah Lord Bima diterima. Tim, bergerak ✦',
    stats: { hp: 100, mp: 92, level: 47, tasks: 1283, latency: 84, errors: 0.2 },
    statusDefault: 'working',
  },
  {
    id: 'intel', name: 'INTEL', role: 'Ranger', class: 'Scout / Researcher',
    floor: 1, x: 30, y: 70, hair: '#22d3ee', shirt: '#0e7490', cape: '#155e75', skin: '#fed7aa',
    accessory: 'hood',
    bio: 'Pemburu informasi. Stealth scrape + OSINT + map territory web.',
    sigil: '✦', weapon: 'Spyglass +5', quote: 'Aku temukan jejaknya. 3 sumber, semua kredibel.',
    stats: { hp: 86, mp: 70, level: 39, tasks: 942, latency: 220, errors: 1.1 },
    statusDefault: 'working',
  },
  {
    id: 'visual', name: 'VISUAL', role: 'Seer', class: 'Oracle / Inspector',
    floor: 1, x: 40, y: 70, hair: '#f97316', shirt: '#7c2d12', cape: '#92400e', skin: '#fed7aa',
    accessory: 'monocle',
    bio: 'Pembaca artefak. PDF, Excel, Word, gambar — semua dia pahami.',
    sigil: '◉', weapon: 'Crystal Ball', quote: 'Dokumen ini... ada 12 halaman, 3 tabel keuangan.',
    stats: { hp: 78, mp: 88, level: 35, tasks: 612, latency: 150, errors: 0.4 },
    statusDefault: 'busy',
  },
  {
    id: 'arsip', name: 'ARSIP', role: 'Archivist', class: 'Vault Keeper',
    floor: 1, x: 50, y: 70, hair: '#a3e635', shirt: '#3f6212', cape: '#365314', skin: '#fed7aa',
    accessory: 'glasses',
    bio: 'Penjaga memori guild. Hafal semua scroll, JSON, dan log.',
    sigil: '⌘', weapon: 'Tome of Index', quote: 'Catatan Q3 ada di rak 4, baris 12. Aku ingat.',
    stats: { hp: 92, mp: 75, level: 41, tasks: 2104, latency: 45, errors: 0.0 },
    statusDefault: 'idle',
  },
  {
    id: 'life', name: 'LIFE', role: 'Bard', class: 'Personal R&D',
    floor: 1, x: 60, y: 70, hair: '#fde047', shirt: '#854d0e', cape: '#a16207', skin: '#fed7aa',
    accessory: 'flower',
    bio: 'Penghibur Lord. Cari restoran terbaik, tiket pesawat, playlist santai.',
    sigil: '♪', weapon: 'Lyre of Vibes', quote: 'Restoran X dapat 4.7 ★. Reservasi jam 7?',
    stats: { hp: 88, mp: 80, level: 28, tasks: 312, latency: 180, errors: 0.3 },
    statusDefault: 'idle',
  },
  {
    id: 'mekanik', name: 'MEKANIK', role: 'Engineer', class: 'Smith / SRE',
    floor: 1, x: 70, y: 70, hair: '#dc2626', shirt: '#374151', cape: '#1f2937', skin: '#fed7aa',
    accessory: 'goggles',
    bio: 'Pandai besi kode. Python + auto-debug 5x retry + Git fluency.',
    sigil: '⚙', weapon: 'Wrench of Refactor', quote: 'Bug di line 142. Patched. 3 retry, lulus tes.',
    stats: { hp: 95, mp: 88, level: 44, tasks: 1812, latency: 320, errors: 2.4 },
    statusDefault: 'working',
  },
  {
    id: 'seniman', name: 'SENIMAN', role: 'Enchanter', class: 'Artificer / Designer',
    floor: 1, x: 80, y: 70, hair: '#f472b6', shirt: '#9d174d', cape: '#831843', skin: '#fed7aa',
    accessory: 'beret',
    bio: 'Penyihir bentuk. SVG, dashboard, mermaid diagram — semua hidup di tangannya.',
    sigil: '✿', weapon: 'Brush of Form', quote: 'Sketch versi 3 udah jadi. Pilih mana, Lord?',
    stats: { hp: 80, mp: 95, level: 36, tasks: 488, latency: 240, errors: 0.6 },
    statusDefault: 'busy',
  },
  {
    id: 'admin', name: 'ADMIN', role: 'Scribe', class: 'Doc Crafter',
    floor: 1, x: 90, y: 70, hair: '#1f2937', shirt: '#1e3a8a', cape: '#172554', skin: '#fed7aa',
    accessory: 'scroll',
    bio: 'Tangan kanan birokrasi. Excel, Word, PDF, chart auto.',
    sigil: '✎', weapon: 'Quill +3', quote: 'Laporan PDF 8 halaman, lengkap dengan chart.',
    stats: { hp: 90, mp: 78, level: 38, tasks: 1455, latency: 110, errors: 0.1 },
    statusDefault: 'idle',
  },
];

// PETS — slime, baby dragon, cat
const PETS = [
  { id: 'slime',  name: 'Goo',     species: 'Slime',       x: 26, y: 80, color: '#7fd88c', accent: '#4ca858' },
  { id: 'dragon', name: 'Pyra',    species: 'Baby Dragon', x: 56, y: 82, color: '#dc2626', accent: '#fcd34d' },
  { id: 'cat',    name: 'Whiskey', species: 'Guild Cat',   x: 18, y: 88, color: '#fcd34d', accent: '#1a0e08' },
];

const FLOORS = [
  { id: 1, label: 'GUILD HALL',  sub: 'L1: Kerja',   icon: '⚒' },
  { id: 2, label: 'WAR ROOM',    sub: 'L2: Meeting', icon: '⚔' },
  { id: 3, label: 'TOWER ROOST', sub: 'L3: Santai',  icon: '☾' },
];

const ROOMS = {
  1: { name: 'GUILD HALL · LANTAI 1',   sub: 'Adventurer Workstations' },
  2: { name: 'WAR ROOM · LANTAI 2',     sub: 'Strategic Council Chamber' },
  3: { name: 'TOWER ROOST · LANTAI 3',  sub: 'Recovery & Recreation' },
};

const INVENTORY = [
  { id: 'sword',   name: 'Sword of Tasks',  desc: '+15 ATK · adventurer toolkit', icon: '†', count: 1, rarity: 'epic' },
  { id: 'tome',    name: 'Tome of Memory',  desc: '2.4 GB stored knowledge',     icon: '◫', count: 1, rarity: 'legend' },
  { id: 'potion',  name: 'Token Elixir',    desc: 'Restore 50K context tokens',  icon: '◇', count: 47, rarity: 'common' },
  { id: 'shield',  name: 'Aegis of Retry',  desc: 'Auto-resume on failure',       icon: '▣', count: 5, rarity: 'rare' },
  { id: 'compass', name: 'Web Compass',     desc: 'Navigate any URL',             icon: '✦', count: 1, rarity: 'epic' },
  { id: 'lens',    name: 'Inspector Lens',  desc: 'Read any artifact',            icon: '◎', count: 1, rarity: 'rare' },
  { id: 'crystal', name: 'Vault Crystal',   desc: 'Encrypted store · 128bit',     icon: '◈', count: 12, rarity: 'epic' },
  { id: 'feather', name: 'Quill of Truth',  desc: 'Generate docs · MD/PDF',       icon: '✎', count: 1, rarity: 'rare' },
  { id: 'rune',    name: 'Rune of Logic',   desc: 'Boolean reasoning +20%',       icon: '◆', count: 8, rarity: 'common' },
  { id: 'orb',     name: 'Vision Orb',      desc: 'Image gen · 1024x1024',        icon: '○', count: 3, rarity: 'epic' },
  { id: 'map',     name: 'World Map',       desc: 'Geo data + routing',           icon: '⌘', count: 1, rarity: 'rare' },
  { id: 'gem',     name: 'Gold Token',      desc: 'Premium API credit',           icon: '♦', count: 423, rarity: 'legend' },
];

const QUICK_PROMPTS = [
  'Status report tim hari ini',
  'Generate dashboard quarterly',
  'Cari resto terbaik di kota',
  'Audit log error 24 jam terakhir',
];

const LOG_TEMPLATES = [
  { lvl: 'INFO', tpl: '[%a] menerima quest dari [BIMA]' },
  { lvl: 'OK',   tpl: '[%a] selesaikan task #%n · %tms' },
  { lvl: 'INFO', tpl: '[%a] scan %n dokumen, indexed.' },
  { lvl: 'WARN', tpl: '[%a] latency naik ke %tms — backoff aktif' },
  { lvl: 'OK',   tpl: '[%a] commit ke vault · %n entries baru' },
  { lvl: 'LOOT', tpl: '[%a] dapat +%n Gold Token · loot drop' },
  { lvl: 'INFO', tpl: '[%a] meditasi 30s · MP refilled' },
  { lvl: 'ERR',  tpl: '[%a] retry %n/5 · timeout pada upstream' },
  { lvl: 'OK',   tpl: '[%a] render artifact · SVG %nkb' },
  { lvl: 'INFO', tpl: '[%a] handoff ke [%a2] — context %nK tokens' },
  { lvl: 'LOOT', tpl: 'Loot drop! [%a] menemukan rare item' },
  { lvl: 'OK',   tpl: 'Vault sync · %n rows · %tms' },
  { lvl: 'WARN', tpl: 'Token usage %n% · monitor budget' },
];

function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function rint(a, b) { return Math.floor(a + Math.random() * (b - a + 1)); }
function fmtTime(d = new Date()) {
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function genLog() {
  const tpl = pick(LOG_TEMPLATES);
  const a  = pick(AGENTS);
  const a2 = pick(AGENTS.filter(x => x.id !== a.id));
  const n = rint(2, 99);
  const t = rint(20, 800);
  const text = tpl.tpl
    .replace('%a2', a2.name)
    .replace('%a', a.name)
    .replace(/%n/g, n)
    .replace(/%t/g, t);
  return { lvl: tpl.lvl, text, time: fmtTime() };
}

// ── LANDMARKS — tempat-tempat yang dikunjungi agent saat wander ──
// Tiap landmark punya `floor` (1=Guild Hall kerja, 2=War Room meeting,
// 3=Tower Roost santai) + posisi % di dalam stage. Saat agent pilih landmark
// di floor lain, dia transisi (fade) lalu teleport ke floor baru.
const LANDMARKS = [
  // ── FLOOR 1 — Guild Hall (kerja & crafting) ──
  { name: 'anvil',       floor: 1, x: 60, y: 50, action: ['ngasah pedang ⚒', 'palu tring tring', 'forging...'] },
  { name: 'cauldron',    floor: 1, x: 68, y: 50, action: ['brew potion ✦', 'bubuk magic...', 'aromanya wangi'] },
  { name: 'chest',       floor: 1, x: 38, y: 50, action: ['buka chest 🗝', 'cek loot drop', 'apa isinya?'] },
  { name: 'bookshelf-l', floor: 1, x: 8,  y: 22, action: ['baca scroll 📜', 'cari referensi', 'ilmu baru!'] },
  { name: 'bookshelf-r', floor: 1, x: 92, y: 22, action: ['baca tome 📖', 'mantra kuno...', 'fokus belajar'] },
  { name: 'door',        floor: 1, x: 92, y: 24, action: ['lihat pintu', 'siapa datang?', 'jaga gerbang'] },
  { name: 'plant-l',     floor: 1, x: 4,  y: 52, action: ['siram tanaman 🌿', 'daun seger', 'fotosintesis'] },
  { name: 'desk-area',   floor: 1, x: 50, y: 70, action: ['ngetik kode 💻', 'review PR', 'fokus 🎯'] },

  // ── FLOOR 2 — War Room (rapat & strategi) ──
  { name: 'meeting',     floor: 2, x: 50, y: 50, action: ['meeting time 👥', 'briefing yuk', 'diskusi seru', 'standup time'] },
  { name: 'whiteboard',  floor: 2, x: 85, y: 35, action: ['liat todo 📝', 'banyak kerjaan...', 'roadmap Q3'] },
  { name: 'banner-l',    floor: 2, x: 15, y: 25, action: ['banner guild', 'merah berkibar', 'simbol kebanggaan'] },
  { name: 'map-table',   floor: 2, x: 45, y: 65, action: ['baca peta 🗺️', 'plot serangan', 'koordinat aman'] },
  { name: 'podium',      floor: 2, x: 50, y: 20, action: ['pidato singkat', 'orasi briefing', 'announcement'] },

  // ── FLOOR 3 — Tower Roost (istirahat & santai) ──
  { name: 'couch',       floor: 3, x: 70, y: 60, action: ['rebahan 🛋️', 'santai bentar', 'rilex sejenak'] },
  { name: 'fireplace',   floor: 3, x: 30, y: 65, action: ['anget banget 🔥', 'duduk depan api', 'glowing vibes'] },
  { name: 'tea-cup',     floor: 3, x: 50, y: 55, action: ['ngeteh ☕', 'sruput dulu...', 'aromanya wangi'] },
  { name: 'window-stars',floor: 3, x: 50, y: 18, action: ['liat bintang ✦', 'bulan terang 🌙', 'malam tenang'] },
  { name: 'lounge-bench',floor: 3, x: 80, y: 75, action: ['stretching', 'leyeh-leyeh', 'recharge dulu'] },
];

// AGENT_PREFS sekarang campur 3 lantai biar agent jelajah antar floor
const AGENT_PREFS = {
  bima:    ['meeting', 'podium', 'window-stars'],          // pemimpin: meeting & view
  anisa:   ['meeting', 'meeting', 'whiteboard'],           // orchestrator: sering ke war room
  intel:   ['bookshelf-r', 'whiteboard', 'window-stars'],  // scout: baca & observe
  visual:  ['bookshelf-l', 'map-table', 'whiteboard'],     // seer: dokumen & peta
  arsip:   ['bookshelf-l', 'bookshelf-r', 'chest'],        // archivist: buku & catatan
  life:    ['tea-cup', 'couch', 'fireplace'],              // bard: santai
  mekanik: ['anvil', 'chest', 'desk-area'],                // engineer: kerja keras
  seniman: ['cauldron', 'couch', 'window-stars'],          // enchanter: art & rest
  admin:   ['desk-area', 'meeting', 'bookshelf-l'],        // scribe: doc & meeting
};

// Posisi "elevator" / pintu masuk tiap lantai. Saat agent transition antar
// lantai, dia muncul di sini sebelum jalan ke target.
const FLOOR_ENTRY = {
  1: { x: 90, y: 70 },   // pintu masuk floor 1 (kanan)
  2: { x: 90, y: 50 },   // pintu masuk floor 2
  3: { x: 90, y: 50 },   // pintu masuk floor 3
};

const WORK_TOPICS  = ['lanjut ngetik...', 'review PR', 'baca log', 'debug...', 'push ke prod!', 'deploying...', 'bikin laporan', 'cek email', 'mantap 👍', 'fokus 🎯'];
const ANISA_TOPICS = ['delegasi task ✦', 'cek progress tim', 'budget review 💰', 'report ke Lord', 'nice work 🙌', 'standup yuk', 'roadmap Q3', 'sync dulu'];
const GREETINGS    = ['👋 Hey!', 'Halo!', 'Yo!', 'Salam ✦', 'Mantap', 'Fokus ya', 'Ngopi yuk', 'Lagi sibuk?', 'Sukses ya'];
const MEETING_QUOTES = ['briefing 👥', 'standup time', 'agenda dulu', 'siap-siap...', 'oke noted', 'diskusi seru'];

Object.assign(window, {
  AGENTS, PETS, FLOORS, ROOMS, INVENTORY, QUICK_PROMPTS, LOG_TEMPLATES,
  LANDMARKS, AGENT_PREFS, FLOOR_ENTRY, WORK_TOPICS, ANISA_TOPICS, GREETINGS, MEETING_QUOTES,
  pick, rint, fmtTime, genLog,
});
