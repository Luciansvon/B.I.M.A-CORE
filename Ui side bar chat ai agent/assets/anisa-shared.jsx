// Shared bits for ANISA chat sidebar variations:
// — icon set (inline SVG, stroke-based, 1.5px)
// — sample messages
// — state machine helper

const ANISA_ACCENT = '#10B981';
const ANISA_ACCENT_DIM = 'rgba(16, 185, 129, 0.12)';
const ANISA_ACCENT_FAINT = 'rgba(16, 185, 129, 0.06)';

// ─────────── Icons ───────────
const Icon = ({ d, size = 16, stroke = 1.5, fill = 'none', style }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke="currentColor"
       strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" style={style}>
    {typeof d === 'string' ? <path d={d} /> : d}
  </svg>
);

const Icons = {
  Send: (p) => <Icon {...p} d="M5 12l14-7-5 14-3-6-6-1z" />,
  Camera: (p) => <Icon {...p} d={<>
    <path d="M3 7h3l2-2h8l2 2h3v12H3z" />
    <circle cx="12" cy="13" r="3.5" />
  </>} />,
  Sparkle: (p) => <Icon {...p} d={<>
    <path d="M12 3l1.8 4.7L18.5 9l-4.7 1.8L12 15l-1.8-4.2L5.5 9l4.7-1.3z" />
    <path d="M19 15l.7 1.8L21.5 17.5l-1.8.7L19 20l-.7-1.8L16.5 17.5l1.8-.7z" />
  </>} />,
  Plus: (p) => <Icon {...p} d="M12 5v14M5 12h14" />,
  ChevronRight: (p) => <Icon {...p} d="M9 6l6 6-6 6" />,
  ChevronLeft: (p) => <Icon {...p} d="M15 6l-6 6 6 6" />,
  ChevronDown: (p) => <Icon {...p} d="M6 9l6 6 6-6" />,
  Close: (p) => <Icon {...p} d="M6 6l12 12M18 6L6 18" />,
  More: (p) => <Icon {...p} d={<>
    <circle cx="5" cy="12" r="1" fill="currentColor" />
    <circle cx="12" cy="12" r="1" fill="currentColor" />
    <circle cx="19" cy="12" r="1" fill="currentColor" />
  </>} />,
  History: (p) => <Icon {...p} d={<>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 4v4h4" />
    <path d="M12 8v4l3 2" />
  </>} />,
  Mic: (p) => <Icon {...p} d={<>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </>} />,
  Attach: (p) => <Icon {...p} d="M21 11l-9 9a5 5 0 1 1-7-7l9-9a3.5 3.5 0 1 1 5 5l-8.5 8.5a2 2 0 1 1-3-3l7.5-7.5" />,
  Settings: (p) => <Icon {...p} d={<>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </>} />,
  Edit: (p) => <Icon {...p} d="M12 20h9M16.5 3.5a2.12 2.12 0 1 1 3 3L7 19l-4 1 1-4z" />,
  Copy: (p) => <Icon {...p} d={<>
    <rect x="9" y="9" width="13" height="13" rx="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </>} />,
  Refresh: (p) => <Icon {...p} d={<>
    <path d="M21 12a9 9 0 1 1-3-6.7" />
    <path d="M21 4v5h-5" />
  </>} />,
  ThumbUp: (p) => <Icon {...p} d="M7 22h10a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-4l1.5-4.5A2 2 0 0 0 12.6 3L7 11v11zM3 11h4v11H3z" />,
  ThumbDown: (p) => <Icon {...p} d="M17 2H7a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h4l-1.5 4.5A2 2 0 0 0 11.4 21L17 13V2zM21 13h-4V2h4z" />,
  Stop: (p) => <Icon {...p} d={<rect x="6" y="6" width="12" height="12" rx="1.5" />} />,
  Resize: (p) => <Icon {...p} d="M8 5h8M8 12h8M8 19h8" />,
  Translate: (p) => <Icon {...p} d={<>
    <path d="M3 5h12M9 3v2c0 5-3 8-6 9M5 9c0 3 4 5 8 5" />
    <path d="M13 21l5-12 5 12M15 17h6" />
  </>} />,
  Book: (p) => <Icon {...p} d="M4 4h12a3 3 0 0 1 3 3v14a3 3 0 0 0-3-3H4zM4 4v15" />,
  Code: (p) => <Icon {...p} d="M8 6l-6 6 6 6M16 6l6 6-6 6" />,
  Search: (p) => <Icon {...p} d={<>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.3-4.3" />
  </>} />,
  Pin: (p) => <Icon {...p} d="M12 2v8l5 5H7l5-5M12 15v7" />,
  Crop: (p) => <Icon {...p} d="M6 2v16h16M2 6h16v16" />,
};

// ─────────── Sample data ───────────

const ANISA_SAMPLE_USER_Q = "nis 3d furnitur ini cocok pake warna apa ya? buat ruang tamu modern minimalis";

const ANISA_SAMPLE_REPLY = [
  { type: 'p', text: "Dilihat dari bentuknya — kursi lounge dengan kaki ramping & backrest lengkung — ini siluet yang fleksibel. Untuk ruang tamu modern minimalis, tiga arah palet yang aman:" },
  { type: 'palette', items: [
    { name: 'Walnut + Cream Bouclé', sub: 'Hangat, klasik, mudah dipadu', colors: ['#3b2a1d', '#e8dcc4', '#8a7560'] },
    { name: 'Matte Black + Sage', sub: 'Modern, sedikit dramatis', colors: ['#1a1a1a', '#9aa897', '#d4d2cc'] },
    { name: 'Natural Oak + Terracotta', sub: 'Cozy, sedikit playful', colors: ['#c9a574', '#b25a3e', '#efe6d8'] },
  ]},
  { type: 'p', text: "Kalau dindingnya off-white dan lantainya kayu terang, **#1 Walnut + Cream Bouclé** paling tidak ribet — kontrasnya cukup tanpa terlalu berisik." },
  { type: 'h', text: 'Tips finishing' },
  { type: 'ul', items: [
    "Pakai matte / satin finish; hindari glossy untuk look minimalis.",
    "Kalau frame walnut, jaga undertone tetap warm — jangan campur dengan kayu cool seperti ash.",
    "Untuk upholstery, 90/10 wool blend di bouclé bikin tahan lama tanpa kaku.",
  ]},
  { type: 'p', text: "Mau aku breakdown render setting buat masing-masing palette di Blender?" },
];

const ANISA_HISTORY = [
  { id: 'h1', title: 'Warna kursi 3D minimalis', time: 'Sekarang', active: true },
  { id: 'h2', title: 'Subdivision surface vs bevel modifier', time: '2j lalu' },
  { id: 'h3', title: 'UV unwrap untuk fabric texture', time: 'Kemarin' },
  { id: 'h4', title: 'Lighting setup studio HDRI', time: 'Kemarin' },
  { id: 'h5', title: 'Export GLB ke Three.js viewer', time: '3 hari lalu' },
  { id: 'h6', title: 'Reference image board mood', time: '5 hari lalu' },
  { id: 'h7', title: 'Polycount budget untuk web', time: '1 minggu lalu' },
];

const ANISA_QUICK_PROMPTS = [
  { icon: 'Sparkle', label: 'Saran warna & material' },
  { icon: 'Book',    label: 'Jelaskan apa yang di layar' },
  { icon: 'Translate', label: 'Terjemahkan teks ini' },
  { icon: 'Code',    label: 'Tulis snippet untuk ini' },
];

const ANISA_QUICK_ACTIONS = [
  { icon: 'Sparkle', label: 'Summarize' },
  { icon: 'Book',    label: 'Explain' },
  { icon: 'Translate', label: 'Translate' },
];

// Expose globals so sibling Babel scripts can use them.
Object.assign(window, {
  ANISA_ACCENT, ANISA_ACCENT_DIM, ANISA_ACCENT_FAINT,
  Icon, Icons,
  ANISA_SAMPLE_USER_Q, ANISA_SAMPLE_REPLY,
  ANISA_HISTORY, ANISA_QUICK_PROMPTS, ANISA_QUICK_ACTIONS,
});
