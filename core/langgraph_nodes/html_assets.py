"""
Anisa CSS Framework — pure inline CSS + JS, no CDN.
Dipakai oleh seniman_node untuk membungkus HTML hasil generate LLM.

Tema dipilih via class di <body>:
  theme-corporate (default biru)
  theme-modern    (gradient ungu)
  theme-minimal   (hitam/putih)
  theme-warm      (orange hangat)
  theme-nature    (hijau)
"""

ANISA_CSS = r"""
:root{
  --c-bg:#0f1115; --c-bg-2:#171a21; --c-fg:#e6e8ee; --c-muted:#9aa3b2;
  --c-accent:#3b82f6; --c-accent-2:#60a5fa; --c-card:#1c2029;
  --c-border:#2a2f3a; --c-success:#10b981; --c-warn:#f59e0b; --c-danger:#ef4444;
  --radius:14px; --shadow:0 10px 30px rgba(0,0,0,.35);
  --font-body:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --font-display:"Segoe UI",Roboto,sans-serif;
}
body.theme-corporate{--c-accent:#2563eb;--c-accent-2:#60a5fa;}
body.theme-modern{--c-accent:#a855f7;--c-accent-2:#ec4899;--c-bg:#0d0a1a;--c-bg-2:#171029;--c-card:#1d1532;}
body.theme-minimal{--c-bg:#fafafa;--c-bg-2:#ffffff;--c-fg:#0a0a0a;--c-muted:#666;--c-card:#fff;--c-border:#e5e5e5;--c-accent:#0a0a0a;--c-accent-2:#525252;--shadow:0 4px 16px rgba(0,0,0,.06);}
body.theme-warm{--c-accent:#f97316;--c-accent-2:#fb923c;--c-bg:#1a0f08;--c-bg-2:#241510;--c-card:#2a1a14;}
body.theme-nature{--c-accent:#10b981;--c-accent-2:#34d399;--c-bg:#0a1612;--c-bg-2:#10211b;--c-card:#15291f;}
body.light{--c-bg:#f8fafc;--c-bg-2:#fff;--c-fg:#0f172a;--c-muted:#64748b;--c-card:#fff;--c-border:#e2e8f0;--shadow:0 4px 16px rgba(15,23,42,.08);}

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:var(--font-body);background:var(--c-bg);color:var(--c-fg);line-height:1.6;min-height:100vh;
  background-image:radial-gradient(circle at 20% 0%,color-mix(in srgb,var(--c-accent) 12%,transparent),transparent 50%),radial-gradient(circle at 80% 100%,color-mix(in srgb,var(--c-accent-2) 10%,transparent),transparent 50%);}
a{color:var(--c-accent-2);text-decoration:none;transition:opacity .2s}
a:hover{opacity:.8}
img{max-width:100%;display:block}

/* ========== LAYOUT ========== */
.container{max-width:1200px;margin:0 auto;padding:0 24px}
.container-narrow{max-width:780px;margin:0 auto;padding:0 24px}
.section{padding:64px 0}
.section-sm{padding:32px 0}
.grid{display:grid;gap:20px}
.grid-2{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
.grid-3{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.grid-4{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.flex{display:flex;gap:16px}
.flex-center{display:flex;align-items:center;justify-content:center;gap:12px}
.flex-between{display:flex;align-items:center;justify-content:space-between;gap:16px}
.flex-col{display:flex;flex-direction:column;gap:12px}

/* ========== TYPOGRAPHY ========== */
h1,h2,h3,h4{font-family:var(--font-display);line-height:1.2;letter-spacing:-.02em;font-weight:700}
h1{font-size:clamp(2rem,5vw,3.5rem);margin-bottom:16px}
h2{font-size:clamp(1.5rem,3vw,2.25rem);margin-bottom:14px}
h3{font-size:1.4rem;margin-bottom:10px}
h4{font-size:1.15rem;margin-bottom:8px}
p{margin-bottom:14px;color:var(--c-fg);opacity:.9}
.lead{font-size:1.2rem;line-height:1.7;color:var(--c-muted);max-width:65ch}
.muted{color:var(--c-muted)}
.gradient-text{background:linear-gradient(135deg,var(--c-accent),var(--c-accent-2));-webkit-background-clip:text;background-clip:text;color:transparent;display:inline-block}

/* ========== HERO ========== */
.hero{padding:80px 0 60px;text-align:center;position:relative;overflow:hidden}
.hero-eyebrow{display:inline-block;padding:6px 14px;background:color-mix(in srgb,var(--c-accent) 20%,transparent);color:var(--c-accent-2);border-radius:99px;font-size:.85rem;font-weight:600;margin-bottom:18px;border:1px solid color-mix(in srgb,var(--c-accent) 30%,transparent)}

/* ========== CARDS ========== */
.card{background:var(--c-card);border:1px solid var(--c-border);border-radius:var(--radius);padding:24px;box-shadow:var(--shadow);transition:transform .25s,border-color .25s}
.card:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--c-accent) 60%,var(--c-border))}
.card-glass{background:color-mix(in srgb,var(--c-card) 60%,transparent);backdrop-filter:blur(10px)}
.card-gradient{background:linear-gradient(135deg,color-mix(in srgb,var(--c-accent) 15%,var(--c-card)),var(--c-card));border-color:color-mix(in srgb,var(--c-accent) 30%,var(--c-border))}

/* ========== STATS / KPI ========== */
.stat{padding:24px;background:var(--c-card);border:1px solid var(--c-border);border-radius:var(--radius);position:relative;overflow:hidden}
.stat::before{content:"";position:absolute;top:0;left:0;width:4px;height:100%;background:linear-gradient(180deg,var(--c-accent),var(--c-accent-2))}
.stat-label{font-size:.85rem;color:var(--c-muted);font-weight:500;letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px}
.stat-value{font-size:2.5rem;font-weight:800;line-height:1;font-family:var(--font-display);background:linear-gradient(135deg,var(--c-accent),var(--c-accent-2));-webkit-background-clip:text;background-clip:text;color:transparent}
.stat-trend{display:inline-flex;align-items:center;gap:4px;font-size:.85rem;margin-top:8px;padding:3px 10px;border-radius:99px;font-weight:600}
.stat-trend.up{background:color-mix(in srgb,var(--c-success) 20%,transparent);color:var(--c-success)}
.stat-trend.down{background:color-mix(in srgb,var(--c-danger) 20%,transparent);color:var(--c-danger)}

/* ========== BUTTONS ========== */
.btn{display:inline-flex;align-items:center;gap:8px;padding:12px 24px;border-radius:10px;font-weight:600;font-size:.95rem;cursor:pointer;border:none;transition:all .2s;text-decoration:none}
.btn-primary{background:linear-gradient(135deg,var(--c-accent),var(--c-accent-2));color:white;box-shadow:0 4px 14px color-mix(in srgb,var(--c-accent) 40%,transparent)}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 6px 20px color-mix(in srgb,var(--c-accent) 50%,transparent)}
.btn-ghost{background:transparent;color:var(--c-fg);border:1px solid var(--c-border)}
.btn-ghost:hover{background:var(--c-card);border-color:var(--c-accent)}

/* ========== TABLE ========== */
.table-wrap{overflow-x:auto;border-radius:var(--radius);border:1px solid var(--c-border);background:var(--c-card)}
table{width:100%;border-collapse:separate;border-spacing:0}
th,td{padding:14px 20px;text-align:left;border-bottom:1px solid var(--c-border);vertical-align:top;line-height:1.55;word-spacing:.04em;white-space:normal}
th{background:color-mix(in srgb,var(--c-accent) 12%,var(--c-card));font-weight:700;font-size:.82rem;text-transform:uppercase;letter-spacing:.06em;color:var(--c-accent-2);white-space:nowrap}
td{font-size:.95rem;color:var(--c-fg)}
td + td, th + th{border-left:1px solid color-mix(in srgb,var(--c-border) 60%,transparent)}
tbody tr{transition:background .15s}
tbody tr:nth-child(even){background:color-mix(in srgb,var(--c-accent) 3%,transparent)}
tbody tr:hover{background:color-mix(in srgb,var(--c-accent) 8%,transparent)}
tbody tr:last-child td{border-bottom:none}

/* ========== REFERENCES / DAFTAR PUSTAKA ========== */
.references{list-style:decimal;padding-left:24px;margin-top:8px;display:flex;flex-direction:column;gap:14px}
.references .ref-item{padding:14px 18px;background:var(--c-card);border:1px solid var(--c-border);border-left:3px solid var(--c-accent);border-radius:8px;font-size:.95rem;line-height:1.65;color:var(--c-fg)}
.references .ref-item a{color:var(--c-accent-2);text-decoration:underline;text-underline-offset:3px;font-weight:500;word-break:break-word}
.references .ref-item a:hover{color:var(--c-accent);text-decoration-thickness:2px}
.references .ref-item em,.references .ref-item i{color:var(--c-accent-2);font-style:italic}

/* ========== BAR CHART (CSS-only) ========== */
.bars{display:flex;flex-direction:column;gap:12px}
.bar-row{display:grid;grid-template-columns:120px 1fr 60px;align-items:center;gap:12px}
.bar-label{font-size:.9rem;color:var(--c-muted);font-weight:500}
.bar-track{height:10px;background:var(--c-bg-2);border-radius:99px;overflow:hidden;position:relative}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--c-accent),var(--c-accent-2));border-radius:99px;width:0;transition:width 1s cubic-bezier(.34,1.56,.64,1)}
.bar-value{font-weight:700;font-size:.9rem;text-align:right}

/* ========== TABS ========== */
.tabs{border-bottom:1px solid var(--c-border);display:flex;gap:4px;margin-bottom:24px;flex-wrap:wrap}
.tab-btn{padding:12px 20px;background:transparent;color:var(--c-muted);border:none;border-bottom:2px solid transparent;cursor:pointer;font-weight:600;font-size:.95rem;transition:all .2s;font-family:inherit}
.tab-btn:hover{color:var(--c-fg)}
.tab-btn.active{color:var(--c-accent-2);border-bottom-color:var(--c-accent)}
.tab-content{display:none}
.tab-content.active{display:block;animation:fadeIn .3s ease}

/* ========== ACCORDION ========== */
.accordion-item{border:1px solid var(--c-border);border-radius:10px;margin-bottom:8px;overflow:hidden;background:var(--c-card)}
.accordion-head{padding:16px 20px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-weight:600;user-select:none}
.accordion-head:hover{background:color-mix(in srgb,var(--c-accent) 5%,transparent)}
.accordion-icon{transition:transform .25s}
.accordion-item.open .accordion-icon{transform:rotate(45deg)}
.accordion-body{max-height:0;overflow:hidden;transition:max-height .3s ease,padding .3s ease;padding:0 20px;color:var(--c-muted)}
.accordion-item.open .accordion-body{max-height:500px;padding:0 20px 16px}

/* ========== TIMELINE ========== */
.timeline{position:relative;padding-left:32px}
.timeline::before{content:"";position:absolute;left:8px;top:0;bottom:0;width:2px;background:var(--c-border)}
.timeline-item{position:relative;padding-bottom:24px}
.timeline-item::before{content:"";position:absolute;left:-30px;top:6px;width:14px;height:14px;border-radius:50%;background:var(--c-accent);box-shadow:0 0 0 4px var(--c-bg)}
.timeline-date{font-size:.85rem;color:var(--c-accent-2);font-weight:600;margin-bottom:4px}

/* ========== BADGE / TAG ========== */
.badge{display:inline-block;padding:4px 10px;border-radius:99px;font-size:.75rem;font-weight:600;background:color-mix(in srgb,var(--c-accent) 20%,transparent);color:var(--c-accent-2);text-transform:uppercase;letter-spacing:.05em}
.badge-success{background:color-mix(in srgb,var(--c-success) 20%,transparent);color:var(--c-success)}
.badge-warn{background:color-mix(in srgb,var(--c-warn) 20%,transparent);color:var(--c-warn)}

/* ========== FOOTER ========== */
.footer{padding:32px 0;border-top:1px solid var(--c-border);text-align:center;color:var(--c-muted);font-size:.9rem;margin-top:64px}

/* ========== UTILS ========== */
.text-center{text-align:center}.text-right{text-align:right}.mt-1{margin-top:8px}.mt-2{margin-top:16px}.mt-3{margin-top:24px}.mt-4{margin-top:32px}.mb-1{margin-bottom:8px}.mb-2{margin-bottom:16px}.mb-3{margin-bottom:24px}.mb-4{margin-bottom:32px}.gap-sm{gap:8px}.gap-lg{gap:32px}

/* ========== ANIMATIONS ========== */
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideUp{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.reveal{opacity:0;transform:translateY(24px);transition:opacity .6s,transform .6s}
.reveal.visible{opacity:1;transform:translateY(0)}

/* ========== THEME TOGGLE ========== */
.theme-toggle{position:fixed;top:20px;right:20px;width:42px;height:42px;border-radius:50%;background:var(--c-card);border:1px solid var(--c-border);cursor:pointer;display:flex;align-items:center;justify-content:center;z-index:100;font-size:1.1rem;transition:all .2s}
.theme-toggle:hover{transform:rotate(15deg);border-color:var(--c-accent)}

/* ========== ICON SVG ========== */
.icon{width:1em;height:1em;display:inline-block;vertical-align:-2px}

/* ========== RESPONSIVE ========== */
@media (max-width:768px){
  .container{padding:0 16px}
  .section{padding:40px 0}
  h1{font-size:2rem}
  .bar-row{grid-template-columns:80px 1fr 50px}
  .theme-toggle{top:12px;right:12px;width:36px;height:36px}
}

/* ========== PRINT ========== */
@media print{.theme-toggle{display:none}body{background:white;color:black}.card{break-inside:avoid}}
"""

ANISA_JS = r"""
// Theme toggle (light/dark)
(function(){
  const saved = localStorage.getItem('anisa-theme');
  if(saved === 'light') document.body.classList.add('light');
  const btn = document.querySelector('.theme-toggle');
  if(btn){
    btn.addEventListener('click', () => {
      document.body.classList.toggle('light');
      localStorage.setItem('anisa-theme', document.body.classList.contains('light') ? 'light' : 'dark');
      btn.textContent = document.body.classList.contains('light') ? '🌙' : '☀️';
    });
    btn.textContent = document.body.classList.contains('light') ? '🌙' : '☀️';
  }
})();

// Tabs
document.querySelectorAll('[data-tabs]').forEach(group => {
  const btns = group.querySelectorAll('.tab-btn');
  const contents = group.querySelectorAll('.tab-content');
  btns.forEach((btn, i) => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      contents.forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      if(contents[i]) contents[i].classList.add('active');
    });
  });
});

// Accordion
document.querySelectorAll('.accordion-item').forEach(item => {
  const head = item.querySelector('.accordion-head');
  if(head) head.addEventListener('click', () => item.classList.toggle('open'));
});

// Animated bars (trigger on scroll)
const barObserver = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if(e.isIntersecting){
      const fill = e.target.querySelector('.bar-fill');
      if(fill && fill.dataset.value){
        fill.style.width = fill.dataset.value + '%';
      }
      barObserver.unobserve(e.target);
    }
  });
}, {threshold:.3});
document.querySelectorAll('.bar-row').forEach(b => barObserver.observe(b));

// Animated counters
const counterObserver = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if(e.isIntersecting){
      const el = e.target;
      const target = parseFloat(el.dataset.count || '0');
      const duration = 1200;
      const start = performance.now();
      const prefix = el.dataset.prefix || '';
      const suffix = el.dataset.suffix || '';
      const decimals = parseInt(el.dataset.decimals || '0');
      function tick(now){
        const t = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = prefix + (target * eased).toFixed(decimals) + suffix;
        if(t < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
      counterObserver.unobserve(el);
    }
  });
}, {threshold:.5});
document.querySelectorAll('[data-count]').forEach(c => counterObserver.observe(c));

// Reveal on scroll
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if(e.isIntersecting){
      e.target.classList.add('visible');
      revealObserver.unobserve(e.target);
    }
  });
}, {threshold:.15});
document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));
"""

# Template detection — keyword → template type
TEMPLATE_KEYWORDS = {
    "dashboard": ["dashboard", "kpi", "metrik", "statistik", "monitoring", "analytics", "tracker"],
    "article": ["artikel", "blog", "esai", "tulisan", "story", "narasi", "berita"],
    "showcase": ["showcase", "portofolio", "portfolio", "galeri", "gallery", "produk", "katalog"],
    "report": ["laporan visual", "report visual", "infografik", "infographic", "ringkasan", "summary"],
    "landing": ["landing", "promosi", "campaign", "launching", "produk baru", "tawaran"],
}

def detect_template(user_request: str) -> str:
    """Auto-detect tipe template berdasarkan keywords di request."""
    req_lower = user_request.lower()
    scores = {tpl: sum(1 for kw in kws if kw in req_lower) for tpl, kws in TEMPLATE_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "dashboard"  # default

def detect_theme(user_request: str) -> str:
    """Auto-detect tema visual berdasarkan tone request."""
    req_lower = user_request.lower()
    if any(k in req_lower for k in ["minimalis", "minimal", "bersih", "putih", "simple"]):
        return "theme-minimal"
    if any(k in req_lower for k in ["kreatif", "creative", "berani", "vibrant", "modern", "ungu", "pink"]):
        return "theme-modern"
    if any(k in req_lower for k in ["hangat", "warm", "orange", "matahari", "santai"]):
        return "theme-warm"
    if any(k in req_lower for k in ["alam", "nature", "hijau", "eco", "organik", "lingkungan"]):
        return "theme-nature"
    return "theme-corporate"  # default

TEMPLATE_GUIDES = {
    "dashboard": """
TEMPLATE: DASHBOARD KPI
Struktur wajib (urut):
1. <header class="container"> dengan judul + subtitle
2. <section class="section"><div class="container"> berisi grid stats (.grid .grid-3 atau .grid-4) — minimal 3 kartu .stat dengan .stat-label, .stat-value (pakai data-count untuk animasi), .stat-trend
3. <section class="section"><div class="container"> berisi .grid .grid-2 → kiri: .card berisi bar chart (.bars > .bar-row dengan data-value pada .bar-fill), kanan: .card berisi tabel data
4. Optional: tabs (.tabs .tab-btn .tab-content) untuk multi-view data
5. <footer class="footer container"> timestamp + sumber
""",
    "article": """
TEMPLATE: ARTICLE/BLOG
Struktur wajib:
1. <header class="hero container-narrow"> dengan .hero-eyebrow (kategori), h1 (judul), .lead (intro)
2. <section class="container-narrow"> body artikel: paragraf, h2, h3, blockquote, lists. Pakai .reveal untuk animasi scroll
3. Insert .card-gradient sesekali untuk highlight kutipan
4. Footer dengan author + tanggal
""",
    "showcase": """
TEMPLATE: SHOWCASE/PORTFOLIO
Struktur wajib:
1. .hero centered dengan h1 + lead
2. .container .grid .grid-3 berisi banyak .card (item portfolio): tiap card punya h3, p, badge, "Lihat Detail" link
3. Optional: tabs untuk filter kategori
4. CTA section di akhir
""",
    "report": """
TEMPLATE: REPORT VISUAL
Struktur wajib:
1. Hero dengan judul laporan + tanggal + author di .badge
2. Stats grid (.grid .grid-4) ringkasan angka kunci
3. Section dengan .timeline untuk kronologi/tahapan
4. Section dengan .bars untuk perbandingan data
5. Tabel detail di .table-wrap
6. Kesimpulan dalam .card-gradient
""",
    "landing": """
TEMPLATE: LANDING PAGE
Struktur wajib:
1. .hero besar dengan h1 (gradient-text), .lead, dan dua tombol .btn-primary + .btn-ghost
2. .grid .grid-3 features section (3-6 kartu fitur dengan icon SVG inline + h3 + p)
3. .grid .grid-2 dengan teks + visual mock (CSS only)
4. .accordion FAQ section (4-6 item)
5. CTA card-gradient besar di akhir
""",
}

def build_html_skeleton(title: str, body_html: str, theme: str = "theme-corporate", timestamp: str = "") -> str:
    """Wrap LLM-generated body HTML dengan CSS framework + theme + interactivity."""
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<style>{ANISA_CSS}</style>
</head>
<body class="{theme}">
<button class="theme-toggle" aria-label="Toggle theme">☀️</button>
{body_html}
<footer class="footer">
  <div class="container">
    Dibuat oleh <strong>Anisa (B.I.M.A Core)</strong> · {timestamp}
  </div>
</footer>
<script>{ANISA_JS}</script>
</body>
</html>"""
