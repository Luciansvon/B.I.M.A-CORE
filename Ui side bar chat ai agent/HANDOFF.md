# ANISA — Engineering Handoff (Variant B · Floating Card)

UI sidebar AI assistant. Membaca konteks layar (screenshot) lalu menjawab pertanyaan user. Model: **OpenRouter free tier** (Gemini Flash / DeepSeek / Llama Vision).

> **Semua di stack ini gratis**: Tauri (MIT), Rust (free), React (MIT), OpenRouter free tier (no kartu kredit, cuma verif email). Yang berbayar nanti cuma kalau mau code-signing certificate biar binary tidak kena warning OS (~$100/year buat Apple Developer, optional).

---

## 1. Bentuk produk

| Pilihan | Cocok kalau | Stack rekomendasi |
|---|---|---|
| **Desktop app (recommended)** | Mau capture seluruh layar, apapun app-nya (Blender, Figma, IDE) | **Tauri 2.x** — Rust + system webview, binary ~10MB, security-first, free |
| Electron | Tim lebih nyaman dgn Node.js ecosystem | Electron + `desktopCapturer`, free |
| Browser extension | Cukup capture tab browser doang | Chrome MV3 + side_panel API, free |

Untuk use case "tanya tentang model 3D di Blender", **harus desktop app**. Web app biasa tidak bisa capture window di luar tab-nya.

### Stack rekomendasi (Tauri)

- **Shell**: Tauri 2.x
- **Frontend**: React + Vite (port dari prototype ini)
- **Screen capture**: `tauri-plugin-screenshots` atau `xcap` crate
- **Global hotkey**: `tauri-plugin-global-shortcut` (⌘J / Ctrl+Alt+J)
- **LLM**: OpenRouter → DeepSeek (`deepseek/deepseek-chat` atau vision model untuk image input)
- **Local storage**: `tauri-plugin-store` (history, prefs)

---

## 2. File yang dipakai (Variant B)

```
variant-b-reference.html        ← Fullscreen reference. Open this to see V-B alone.
index.html                      ← Original canvas dengan 3 variations (boleh diabaikan)
assets/
  anisa-shared.jsx              ← Icons, sample data, brand tokens (re-use semua)
  anisa-parts.jsx               ← Chat UI parts (header, message bubble, input, dll)
  anisa-variations.jsx          ← VariantB component (Floating Card shell)
  desktop-mock.jsx              ← 3D editor mockup background (HAPUS — ini cuma demo)
```

Untuk implementasi production, ambil **3 file pertama** dari `assets/`. Buang `desktop-mock.jsx`.

---

## 3. Design tokens

```js
const T = {
  bg: '#0d0e10',                                  // Main sidebar bg
  bgGlass: 'rgba(13, 14, 16, 0.78)',              // V-B uses this + backdrop-filter
  surface: '#151619',                             // Cards, history items, prompts
  surface2: '#1c1e22',                            // Hover, input bg
  surface3: '#23262b',                            // Palette card number badge
  border: '#26292e',                              // Default border
  borderFaint: '#1d1f23',                         // Inner dividers
  text: '#e7e9ec',
  textSec: '#9aa0a8',
  textMute: '#62676f',
  accent: '#10B981',                              // Emerald — primary CTA, active states
  accentDim: 'rgba(16, 185, 129, 0.14)',          // Active bg fill
  accentText: '#34d399',                          // Accent on dark text
};
```

**Fonts**: Inter (UI) + JetBrains Mono (timestamps, file names, token counter).

**Sidebar geometry (V-B)**:
- Width: **420px** (resizable; min ~360, max ~600 recommended)
- Position: floating, anchored top-right, with **16px margin** all sides
- Top offset: 60px (assumes app titlebar of ~60px above; adjust)
- Border radius: **18px**
- Backdrop blur: `blur(20px) saturate(140%)`
- Shadow: `0 24px 60px rgba(0,0,0,0.5)`

---

## 4. States (semua di prototype)

| State | Trigger | What shows |
|---|---|---|
| `empty` | First open, no active conversation | Welcome + quick prompt cards + recent history (3 items) |
| `capture` | User clicks 📷 / triggers screen capture | Scanning animation, "Reading your screen", progress bar |
| `typing` | Request sent, waiting for first token | Animated dots + "ANISA sedang berpikir…" |
| `streaming` | Tokens arriving from LLM | Partial reply + blinking caret + Stop button + tok/s counter |
| `reply` | Stream complete | Full message + action row (copy / regen / 👍 👎) + follow-up chips |
| `history` | User clicks history icon | Searchable list grouped by time bucket |

Plus **collapsed** mode — pill button bottom-right with `Ask ANISA · ⌘J`.

---

## 5. Core components (reusable)

Defined in `anisa-parts.jsx`:

- `<AnisaMark size={N} />` — brand mark (emerald gradient "A")
- `<ChatHeader />` — top bar with brand, status dot, action icons
- `<ContextChip capturing={bool} />` — current screen indicator
- `<UserMessage text withScreenshot />` — user bubble (optionally with attached viewport thumbnail)
- `<AnisaMessage>` — wrapper for AI message with action row
- `<ReplyRenderer blocks={[...]} />` — renders rich content (paragraphs, palette cards, lists)
- `<TypingBubble />` — three-dot loader
- `<InputArea capturing />` — textarea + camera/attach/mic/send + quick actions
- `<HistoryItem item />` — single history row
- `<QuickPromptItem icon label />` — empty-state suggestion card

---

## 6. LLM integration outline (OpenRouter — FREE tier)

### Free models di OpenRouter (per Mei 2026 — selalu cek dashboard, bisa berubah)

| Model | Vision? | Free tier limit | Catatan |
|---|---|---|---|
| `deepseek/deepseek-chat-v3-0324:free` | ❌ Text only | ~50 req/day (variable) | Chat utama DeepSeek. Bagus untuk QnA tapi butuh OCR dulu untuk baca layar. |
| `deepseek/deepseek-r1:free` | ❌ Text only | ~50 req/day | Reasoning model, slower tapi lebih akurat untuk analisis kompleks. |
| `google/gemini-2.0-flash-exp:free` | ✅ Vision | Generous, ~1000/day | **Rekomendasi untuk MVP** — vision-capable, cepat, gratis. |
| `meta-llama/llama-3.2-11b-vision-instruct:free` | ✅ Vision | ~50 req/day | Open weights, vision OK. |
| `qwen/qwen2.5-vl-72b-instruct:free` | ✅ Vision | Variable | Vision bagus, kadang offline. |

**Strategi yang gua saranin:**

1. **Primary**: `google/gemini-2.0-flash-exp:free` untuk semua request (vision + text). Kasih limit fallback.
2. **Fallback ke DeepSeek**: kalau Gemini rate-limit kena, fallback ke `deepseek/deepseek-chat-v3-0324:free` + OCR pass dulu pakai Tesseract.js (gratis, local, no API).
3. **Cap user-side**: simpan counter di local store, kasih warning user kalau hampir kena daily limit.

> ⚠️ Free model di OpenRouter butuh `:free` suffix dan akun OpenRouter (verifikasi email aja, no kartu kredit). Rate limit dibagi rata di semua user free, jadi bisa kena 429 — handle dengan retry + fallback.

### Endpoint
```
POST https://openrouter.ai/api/v1/chat/completions
Authorization: Bearer ${OPENROUTER_API_KEY}
Content-Type: application/json
HTTP-Referer: https://your-app-id          # required for free tier attribution
X-Title: ANISA                              # shows in OpenRouter dashboard
```

### Request body (Gemini, vision + streaming)
```js
{
  "model": "google/gemini-2.0-flash-exp:free",
  "stream": true,
  "messages": [
    { "role": "system", "content": SYSTEM_PROMPT },
    { "role": "user", "content": [
      { "type": "text", "text": "nis 3d furnitur ini cocok pake warna apa ya?" },
      { "type": "image_url", "image_url": { "url": "data:image/png;base64,..." } }
    ]}
  ]
}
```

### Streaming handler (frontend)
- Open `fetch` with `ReadableStream`, baca SSE line by line
- On each `data: {...}` → append `choices[0].delta.content` → trigger re-render dari `<StreamingBody>`
- On `data: [DONE]` → swap state ke `reply`

### Fallback / rate-limit handling
```js
const MODELS = [
  'google/gemini-2.0-flash-exp:free',           // primary, vision
  'meta-llama/llama-3.2-11b-vision-instruct:free', // fallback vision
  'deepseek/deepseek-chat-v3-0324:free',        // fallback text-only (run OCR first)
];

async function askAnisa(text, imageB64) {
  for (const model of MODELS) {
    try {
      return await streamChat(model, text, imageB64);
    } catch (e) {
      if (e.status === 429) continue;  // rate limited, try next
      throw e;
    }
  }
  throw new Error('Semua model rate-limited. Coba lagi nanti.');
}
```

### Optional: OCR fallback (gratis, local)

Kalau ujung-ujungnya jatuh ke text-only DeepSeek, jalankan OCR di Rust side pakai `tesseract-rs` atau pre-process di JS pakai `tesseract.js`:

```js
import Tesseract from 'tesseract.js';
const { data: { text } } = await Tesseract.recognize(imageB64, 'eng+ind');
// Then send `text` as context to DeepSeek
```

### System prompt (suggested)
```
You are ANISA, a helpful AI assistant that can see the user's screen.
The user works in Indonesian (casual, "nis", "gua", "lo"). Reply in Indonesian
unless they switch to English. Be concise but warm. When relevant, reference
specific elements you can see in their screenshot.
```

### Screen capture (Tauri)
```rust
// src-tauri/src/main.rs
use xcap::Monitor;

#[tauri::command]
fn capture_screen() -> Result<String, String> {
    let monitor = Monitor::all().map_err(|e| e.to_string())?
        .into_iter().next().ok_or("no monitor")?;
    let image = monitor.capture_image().map_err(|e| e.to_string())?;
    // Encode to base64 PNG
    let mut buf = Vec::new();
    image.write_to(&mut std::io::Cursor::new(&mut buf), image::ImageFormat::Png)
        .map_err(|e| e.to_string())?;
    Ok(format!("data:image/png;base64,{}", base64::encode(&buf)))
}
```

---

## 7. Persistence

- **Conversations**: SQLite via `tauri-plugin-sql`. Schema: `conversations(id, title, created_at, updated_at)` + `messages(id, conversation_id, role, content, image_b64, created_at)`
- **Settings**: `tauri-plugin-store` JSON file (model choice, hotkey, theme override, OpenRouter key — encrypt with `tauri-plugin-stronghold` or OS keyring)

---

## 8. UX behaviours yang sudah ada di prototype

- Hover state di semua button
- Notification dot dengan pulse di collapsed avatar (ada reply baru)
- Capture context chip berubah hijau + striped pattern saat capturing
- Streaming caret blink + Stop button + token/s counter
- Follow-up chips di bawah reply (clickable suggested next questions)
- Quick action chips di atas input (Summarize / Explain / Translate)
- Drag handle di edge kiri untuk resize

---

## 9. Yang masih perlu kamu putuskan / build

- [ ] Error states (rate limited, no network, invalid API key)
- [ ] Auth flow buat OpenRouter API key
- [ ] Region selector (mau capture full screen, window aktif, atau drag-select area?)
- [ ] OCR pass sebelum kirim ke LLM (kalau model bukan vision) — pakai Tesseract atau cloud OCR
- [ ] Onboarding (request permission untuk screen recording di macOS)
- [ ] Auto-update (`tauri-plugin-updater`)

---

Pertanyaan? Tinggal tanya.
