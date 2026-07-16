/**
 * B.I.M.A Core — WhatsApp Web JS Bridge
 * 
 * Menghubungkan WhatsApp ke Anisa (LangGraph engine) via WA Bridge Server.
 * Bridge server jalan di port 8001, terpisah dari dashboard.
 * 
 * Fitur:
 * - QR code di terminal untuk login WA Web pertama kali
 * - Session persist (LocalAuth) — tidak perlu scan ulang
 * - Owner-only mode (hanya nomor OWNER yang bisa akses)
 * - Support attachment (gambar, dokumen)
 * - Smart chunking untuk response panjang
 * - Rate limiting per-user
 * - Typing indicator saat memproses
 */

const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const QRCode = require('qrcode');
const axios = require('axios');
const path = require('path');
const fs = require('fs');
const mime = require('mime-types');
const {
    PROCESSING_MESSAGE,
    VOICE_READY_MESSAGE,
    updateProgressMessage,
} = require('./progress_message');
const { sanitizeForWhatsApp } = require('./sanitize');
require('dotenv').config({ path: path.resolve(__dirname, '..', '.env') });

// ============================================================
// CONFIG
// ============================================================
const CONFIG = {
    // WA Bridge server (core/wa_server.py, port 8001)
    bridgeUrl: process.env.WA_BRIDGE_URL || 'http://127.0.0.1:8001',
    bridgeToken: process.env.WA_BRIDGE_TOKEN || '',

    // Whitelist nomor (comma-separated, format: 628xxx — tanpa + atau spasi) — kosong = open dengan password
    ownerNumbers: (process.env.WA_OWNER_NUMBER || '').split(',').map(s => s.trim()).filter(Boolean),

    // Trigger prefix — bot cuma respons kalau pesan mulai dengan ini
    triggerPrefix: (process.env.WA_TRIGGER || '/bot').toLowerCase(),

    // Password gate (kalau owner whitelist kosong, password wajib untuk login)
    botPassword: process.env.WA_BOT_PASSWORD || '',
    sessionMs: parseInt(process.env.WA_SESSION_MINUTES || '60') * 60 * 1000,

    // Bot name
    botName: process.env.WA_BOT_NAME || 'Anisa',

    // Rate limit (detik antar pesan)
    rateLimitSeconds: parseInt(process.env.WA_RATE_LIMIT || '5'),

    // Max response length per chunk
    maxChunkLength: parseInt(process.env.WA_MAX_CHUNK || '4000'),

    // Request timeout (ms) — LangGraph bisa lama
    requestTimeout: parseInt(process.env.WA_TIMEOUT || '300000'),

    // Output directory untuk simpan attachment
    outputDir: path.resolve(__dirname, '..', 'outputs'),
};

if (!CONFIG.ownerNumbers.length && !CONFIG.botPassword) {
    console.warn('⚠️  WA_OWNER_NUMBER & WA_BOT_PASSWORD kosong — bot terbuka tanpa filter (tidak aman).');
}

if (!fs.existsSync(CONFIG.outputDir)) {
    fs.mkdirSync(CONFIG.outputDir, { recursive: true });
}

// ============================================================
// STT ARMING — voice note default ignored, harus armed via "/bot stt" (TTL 60s)
// Key: msg.from (chat ID, e.g. "62812xxx@c.us") — consistent fromMe & received.
// ============================================================
const STT_ARM_TTL_MS = 60 * 1000;
const sttArmed = new Map(); // chatId (msg.from) -> expiry timestamp ms
function isSttArmed(chatId) {
    const exp = sttArmed.get(chatId);
    if (!exp) return false;
    if (exp < Date.now()) { sttArmed.delete(chatId); return false; }
    return true;
}

// ============================================================
// LOGGER
// ============================================================
function log(level, msg) {
    const ts = new Date().toISOString().replace('T', ' ').substring(0, 19);
    const icons = { INFO: '✅', WARN: '⚠️', ERROR: '❌', DEBUG: '🔍' };
    console.log(`${ts} | ${icons[level] || '•'} [WA] ${msg}`);
}

// ============================================================
// SESSION (PASSWORD GATE)
// ============================================================
const authedSessions = new Map(); // senderId -> expiry timestamp (null = permanent)
const SESSION_FILE = path.join(__dirname, '.sessions.json');

function loadSessions() {
    try {
        if (fs.existsSync(SESSION_FILE)) {
            const data = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8'));
            for (const [jid, exp] of Object.entries(data)) authedSessions.set(jid, exp);
            log('INFO', `Restored ${authedSessions.size} authed session(s) from disk`);
        }
    } catch (e) { log('WARN', `Gagal load sessions: ${e.message}`); }
}

function saveSessions() {
    try {
        fs.writeFileSync(SESSION_FILE, JSON.stringify(Object.fromEntries(authedSessions)));
    } catch (e) { log('WARN', `Gagal save sessions: ${e.message}`); }
}

function isAuthed(senderId) {
    if (!authedSessions.has(senderId)) return false;
    const exp = authedSessions.get(senderId);
    if (exp === null) return true; // permanent
    if (Date.now() > exp) { authedSessions.delete(senderId); saveSessions(); return false; }
    return true;
}

function login(senderId, permanent = false) {
    authedSessions.set(senderId, permanent ? null : Date.now() + CONFIG.sessionMs);
    saveSessions();
}

function logout(senderId) {
    authedSessions.delete(senderId);
    saveSessions();
}

loadSessions();

// ============================================================
// ADMIN OVERRIDES (whitelist + password runtime control)
// File overlay di atas .env — survive restart, hot-reload tiap admin command
// ============================================================
const ADMIN_OVERRIDES_FILE = path.join(__dirname, '.admin-overrides.json');

function loadOverrides() {
    try {
        if (fs.existsSync(ADMIN_OVERRIDES_FILE)) {
            return JSON.parse(fs.readFileSync(ADMIN_OVERRIDES_FILE, 'utf8'));
        }
    } catch (e) { log('WARN', `Gagal load admin overrides: ${e.message}`); }
    return {};
}

function saveOverrides(data) {
    try {
        fs.writeFileSync(ADMIN_OVERRIDES_FILE, JSON.stringify(data, null, 2));
        return true;
    } catch (e) { log('ERROR', `Gagal save admin overrides: ${e.message}`); return false; }
}

function getEffectiveOwners() {
    const ov = loadOverrides();
    if (Array.isArray(ov.ownerNumbers)) return ov.ownerNumbers.filter(Boolean);
    return CONFIG.ownerNumbers;
}

function getEffectivePassword() {
    const ov = loadOverrides();
    // String kosong = password OFF (gate disabled). Field absent = pakai env.
    if (typeof ov.botPassword === 'string') return ov.botPassword;
    return CONFIG.botPassword;
}

function isValidWaNumber(num) {
    return /^628\d{8,12}$/.test((num || '').trim());
}

// ============================================================
// ADMIN COMMAND HANDLERS — wl, password, session
// ============================================================
async function handleWlCommand(msg, args, senderPhone) {
    const ov = loadOverrides();
    const effective = getEffectiveOwners();
    const fromOverride = Array.isArray(ov.ownerNumbers);
    const trimmed = (args || '').trim();

    if (!trimmed || trimmed === 'list') {
        const lines = [`📋 *Whitelist* (source: ${fromOverride ? 'override' : 'env'})`];
        if (effective.length === 0) {
            lines.push('  _(kosong — bot terbuka untuk semua nomor)_');
        } else {
            effective.forEach((n, i) => lines.push(`  ${i + 1}. \`${n}\``));
        }
        await msg.reply(lines.join('\n'));
        return;
    }

    const [sub, ...rest] = trimmed.split(/\s+/);
    const num = (rest.join('') || '').trim();

    if (sub === 'add') {
        if (!isValidWaNumber(num)) {
            await msg.reply('❌ Format salah. Pakai: `wl add 628xxx` (tanpa + atau spasi, prefix 628 wajib)');
            return;
        }
        const next = [...effective];
        if (next.includes(num)) {
            await msg.reply(`ℹ️ Nomor \`${num}\` udah ada di whitelist.`);
            return;
        }
        next.push(num);
        if (saveOverrides({ ...ov, ownerNumbers: next })) {
            await msg.reply(`✅ Added \`${num}\`. Whitelist sekarang ${next.length} nomor.`);
        } else {
            await msg.reply('❌ Gagal save override file.');
        }
        return;
    }

    if (sub === 'rm' || sub === 'remove') {
        if (!num) { await msg.reply('❌ Pakai: `wl rm 628xxx`'); return; }
        if (num === senderPhone) {
            await msg.reply('🛑 Dilarang hapus nomor sendiri (anti-lockout). Edit `whatsapp/.admin-overrides.json` manual atau minta nomor lain.');
            return;
        }
        const next = effective.filter(n => n !== num);
        if (next.length === effective.length) {
            await msg.reply(`ℹ️ Nomor \`${num}\` gak ada di whitelist.`);
            return;
        }
        if (saveOverrides({ ...ov, ownerNumbers: next })) {
            await msg.reply(`✅ Removed \`${num}\`. Whitelist sekarang ${next.length} nomor.`);
        } else {
            await msg.reply('❌ Gagal save override file.');
        }
        return;
    }

    if (sub === 'reset') {
        const { ownerNumbers, ...keep } = ov;
        if (saveOverrides(keep)) {
            await msg.reply(`✅ Whitelist revert ke .env (${CONFIG.ownerNumbers.length} nomor).`);
        } else {
            await msg.reply('❌ Gagal save override file.');
        }
        return;
    }

    await msg.reply('❌ Sub-command gak dikenal. Pilihan: `wl`, `wl add <num>`, `wl rm <num>`, `wl reset`');
}

async function handlePasswordCommand(msg, args) {
    const ov = loadOverrides();
    const sub = (args || '').trim();
    const prefix = CONFIG.triggerPrefix;

    if (!sub) {
        const effPw = getEffectivePassword();
        const fromOverride = typeof ov.botPassword === 'string';
        const status = effPw ? `aktif (${effPw.length} char)` : 'OFF — login gate disabled';
        await msg.reply(
            `🔐 *Password gate:* ${status}\n` +
            `Source: ${fromOverride ? 'override' : 'env'}\n\n` +
            `Ganti: \`${prefix} password <baru>\`\n` +
            `Matiin: \`${prefix} password off\`\n` +
            `Revert ke .env: \`${prefix} password reset\``
        );
        return;
    }

    if (sub === 'off') {
        if (saveOverrides({ ...ov, botPassword: '' })) {
            await msg.reply('✅ Password gate dimatikan. Sesi yang udah login tetep valid sampai logout.');
        } else {
            await msg.reply('❌ Gagal save override file.');
        }
        return;
    }

    if (sub === 'reset') {
        const { botPassword, ...keep } = ov;
        if (saveOverrides(keep)) {
            const fallback = CONFIG.botPassword ? `aktif (${CONFIG.botPassword.length} char)` : 'OFF';
            await msg.reply(`✅ Password revert ke .env (${fallback}).`);
        } else {
            await msg.reply('❌ Gagal save override file.');
        }
        return;
    }

    if (sub.length < 4) {
        await msg.reply('❌ Password min 4 karakter.');
        return;
    }

    if (saveOverrides({ ...ov, botPassword: sub })) {
        await msg.reply(
            `✅ Password baru udah aktif.\n` +
            `⚠️ Sesi lama yang udah login *tetap valid* sampai logout manual.\n` +
            `Force logout semua: \`${prefix} session kick all\``
        );
    } else {
        await msg.reply('❌ Gagal save override file.');
    }
}

async function handleSessionCommand(msg, args, senderPhone) {
    const sub = (args || '').trim();

    if (!sub || sub === 'list') {
        const entries = [...authedSessions.entries()];
        if (entries.length === 0) {
            await msg.reply('📋 Gak ada session aktif.');
            return;
        }
        const lines = ['📋 *Active sessions:*'];
        entries.forEach(([jid, exp], i) => {
            const phone = jid.replace('@c.us', '').replace('@lid', '');
            const expStr = exp === null ? 'permanen' : `expire ${new Date(exp).toLocaleString('id-ID')}`;
            lines.push(`  ${i + 1}. \`${phone}\` — ${expStr}`);
        });
        await msg.reply(lines.join('\n'));
        return;
    }

    const [verb, target] = sub.split(/\s+/);

    if (verb === 'kick') {
        if (!target) { await msg.reply('❌ Pakai: `session kick 628xxx` atau `session kick all`'); return; }

        if (target === 'all') {
            const n = authedSessions.size;
            authedSessions.clear();
            saveSessions();
            await msg.reply(`✅ Force logout semua (${n} session).`);
            return;
        }

        if (target === senderPhone) {
            await msg.reply('🛑 Dilarang kick diri sendiri.');
            return;
        }

        let kicked = 0;
        for (const jid of [...authedSessions.keys()]) {
            const phone = jid.replace('@c.us', '').replace('@lid', '');
            if (phone === target) {
                authedSessions.delete(jid);
                kicked++;
            }
        }
        saveSessions();
        if (kicked === 0) {
            await msg.reply(`ℹ️ Nomor \`${target}\` gak ada di session list.`);
        } else {
            await msg.reply(`✅ Kicked \`${target}\` (${kicked} session).`);
        }
        return;
    }

    await msg.reply('❌ Sub-command gak dikenal. Pilihan: `session`, `session kick <num>`, `session kick all`');
}

// ============================================================
// RATE LIMITER
// ============================================================
const rateLimitStore = new Map();

function isRateLimited(userId) {
    const now = Date.now();
    const last = rateLimitStore.get(userId) || 0;
    if (now - last < CONFIG.rateLimitSeconds * 1000) return true;
    rateLimitStore.set(userId, now);
    for (const [key, ts] of rateLimitStore) {
        if (now - ts > 60000) rateLimitStore.delete(key);
    }
    return false;
}

// ============================================================
// SMART CHUNKING
// ============================================================
function smartChunks(text, limit = CONFIG.maxChunkLength) {
    const lines = text.split('\n');
    const chunks = [];
    let current = '';
    let inCode = false;
    let codeLang = '';

    for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('```')) {
            if (!inCode) { inCode = true; codeLang = trimmed.substring(3).trim(); }
            else { inCode = false; codeLang = ''; }
        }
        if (current.length + line.length + 1 > limit && current) {
            if (inCode) current += '\n```';
            chunks.push(current);
            current = inCode ? '```' + codeLang + '\n' + line : line;
        } else {
            current += (current ? '\n' : '') + line;
        }
    }
    if (current) chunks.push(current);
    return chunks.length ? chunks : [text.substring(0, limit)];
}

// ============================================================
// KIRIM KE BRIDGE SERVER
// ============================================================
async function sendToAnisa(message, senderId, attachmentPaths = []) {
    try {
        const res = await axios.post(`${CONFIG.bridgeUrl}/chat`, {
            message,
            sender_id: senderId,
            token: CONFIG.bridgeToken,
            attachment_paths: attachmentPaths,
        }, {
            headers: { 'Content-Type': 'application/json' },
            timeout: CONFIG.requestTimeout,
        });
        return res.data;
    } catch (error) {
        if (error.response) {
            const s = error.response.status;
            if (s === 429) return { status: 'error', response: '⏳ Anisa sedang proses pesan lain. Tunggu ya...' };
            if (s === 401) return { status: 'error', response: '🔐 Token bridge tidak valid.' };
            return { status: 'error', response: `❌ Error ${s}: ${error.response.data?.error || ''}` };
        }
        if (error.code === 'ECONNREFUSED') return { status: 'error', response: '🔌 Backend belum aktif. Jalankan main.py dulu.' };
        if (error.code === 'ECONNABORTED') return { status: 'error', response: '⏰ Timeout — coba lagi atau sederhanakan perintahnya.' };
        return { status: 'error', response: `❌ ${error.message}` };
    }
}

// ============================================================
// DOWNLOAD ATTACHMENT DARI WA
// ============================================================
async function downloadAttachment(msg) {
    try {
        if (!msg.hasMedia) return null;
        const media = await msg.downloadMedia();
        if (!media) return null;

        const ext = mime.extension(media.mimetype) || 'bin';
        const filename = `wa_${Math.random().toString(16).substring(2, 10)}.${ext}`;
        const filepath = path.join(CONFIG.outputDir, filename);
        fs.writeFileSync(filepath, Buffer.from(media.data, 'base64'));

        log('INFO', `Attachment: ${filename} (${fs.statSync(filepath).size} bytes)`);
        return filepath;
    } catch (error) {
        log('ERROR', `Gagal download attachment: ${error.message}`);
        return null;
    }
}

// ============================================================
// HELP
// ============================================================
function getHelpMessage() {
    return `✨ *${CONFIG.botName} — B.I.M.A Core* ✨

Kirim pesan langsung, aku proses lewat LangGraph engine.

🧠 Orkestrasi & memori
📂 Baca PDF/Excel/Word/gambar
📚 Search vault Obsidian
📝 Generate dokumen
🔍 Riset web & OSINT
🌤️ YouTube, cuaca, schedule
🎨 Dashboard HTML, SVG
🔧 Python sandbox

📎 Kirim file + pesan → otomatis dianalisis

*Special commands:*
\`!qc\` — QC gambar kerja (PDF/PNG/JPG/DXF + caption \`!qc\`)
\`!qc diff\` — Bandingin 2 revisi drawing (2 attachment)
\`!cutlist\` — Cutting list optimizer (panel kayu/plywood)
\`!cutlist last\` — Pakai BOM auto-extracted dari \`!qc\` terakhir

*Bot commands:* \`help\` \`ping\` \`status\` \`logout\`

*Admin commands* (perlu udah login):
\`wl\` — list whitelist
\`wl add 628xxx\` / \`wl rm 628xxx\` / \`wl reset\`
\`password\` — cek status / \`password <baru>\` / \`password off\` / \`password reset\`
\`session\` — list session aktif / \`session kick 628xxx\` / \`session kick all\``;
}

// ============================================================
// WHATSAPP CLIENT
// ============================================================
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, '.wwebjs_auth'),
    }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
        ],
    },
});

client.on('qr', (qr) => {
    log('INFO', '📱 Scan QR code ini dari WhatsApp:');
    console.log('');
    qrcode.generate(qr, { small: true });
    console.log('');
    const qrPath = path.join(CONFIG.outputDir, 'wa_qr.png');
    QRCode.toFile(qrPath, qr, { width: 512, margin: 2 }, (err) => {
        if (err) log('WARN', `Gagal save QR PNG: ${err.message}`);
        else log('INFO', `QR juga disimpan ke: ${qrPath}`);
    });
});

client.on('authenticated', () => log('INFO', '🔐 Auth OK'));
client.on('auth_failure', (msg) => {
    log('ERROR', `Auth gagal: ${msg}. Hapus .wwebjs_auth/ dan coba lagi.`);
});

client.on('ready', () => {
    log('INFO', `🚀 ${CONFIG.botName} WA Bridge ONLINE`);
    log('INFO', `   Bridge: ${CONFIG.bridgeUrl}`);
    log('INFO', `   Owner: ${CONFIG.ownerNumbers.join(', ') || 'SEMUA'}`);
    log('INFO', `   Trigger: "${CONFIG.triggerPrefix}"`);
});

client.on('disconnected', (reason) => {
    log('WARN', `Terputus: ${reason}`);
});

// ============================================================
// MESSAGE HANDLER
// ============================================================
async function handleMessage(msg) {
    let progressMessage = null;
    try {
        const chat = await msg.getChat();
        if (chat.isGroup) return;
        // Allow fromMe (user sendiri kirim) HANYA kalau pesan diawalin prefix — biar lu bisa pake bot dari HP utama tanpa loop ke balasan bot.
        // Pengecualian: voice note (ptt) bypass prefix HANYA kalau STT armed (user udah text "/bot stt" 60s terakhir).
        if (msg.fromMe) {
            const t = (msg.body || '').trim().toLowerCase();
            const isPtt = msg.type === 'ptt';
            if (!t.startsWith(CONFIG.triggerPrefix) && !(isPtt && isSttArmed(msg.from))) return;
        }

        // Resolve sender ke nomor telepon (handle @lid hash WhatsApp)
        let senderPhone = '';
        try {
            const contact = await msg.getContact();
            senderPhone = contact?.number || '';
        } catch {}
        const rawId = msg.from.replace('@c.us', '').replace('@lid', '');
        const senderId = senderPhone || rawId;

        const effOwners = getEffectiveOwners();
        if (effOwners.length &&
            !effOwners.includes(senderPhone) &&
            !effOwners.includes(rawId)) return;

        const text = msg.body?.trim() || '';
        const lower = text.toLowerCase();
        const prefix = CONFIG.triggerPrefix;

        // Voice note (ptt) bypass prefix HANYA kalau STT armed (user text "/bot stt" 60s terakhir).
        // Default: voice note tanpa armed = silent ignore (gak spam transcribe semua voice).
        // Arming key pakai msg.from (chat ID) — konsisten antara fromMe & received.
        const isVoiceNote = msg.type === 'ptt';
        const sttActive = isVoiceNote && isSttArmed(msg.from);

        // Cuma proses kalau pesan diawalin prefix — KECUALI armed voice note
        if (!sttActive && !lower.startsWith(prefix)) return;

        // Disarm STT setelah voice note dipakai (1 voice per arm)
        if (sttActive) sttArmed.delete(msg.from);

        log('INFO', `${senderId}: "${sttActive ? '[voice note → STT]' : text.substring(0, 80)}"`);

        // Body setelah prefix (voice note armed: skip prefix strip, body kosong)
        const afterPrefix = sttActive ? '' : text.substring(prefix.length).trim();
        const afterLower = afterPrefix.toLowerCase();

        // Login: "/bot login <password>"
        if (afterLower.startsWith('login')) {
            const pw = afterPrefix.substring('login'.length).trim();
            const effPw = getEffectivePassword();
            if (!effPw) {
                await msg.reply('⚠️ Password belum di-set di server. Hubungi admin.');
            } else if (pw === effPw) {
                login(msg.from, true);
                await msg.reply(`🔓 Login OK. Session permanen — pakai \`${prefix} logout\` kalau mau keluar.\n\nLanjut: \`${prefix} <pesan>\``);
            } else {
                await msg.reply('❌ Password salah.');
            }
            return;
        }

        // Logout: "/bot logout"
        if (afterLower === 'logout') {
            logout(msg.from);
            await msg.reply('🔒 Logout.');
            return;
        }

        // Gate: wajib login kalau password di-set
        if (getEffectivePassword() && !isAuthed(msg.from)) {
            await msg.reply(`🔒 Login dulu: \`${prefix} login <password>\``);
            return;
        }

        // Public commands (setelah lolos gate)
        if (afterLower === 'help' || afterLower === 'bantuan') {
            await msg.reply(getHelpMessage()); return;
        }
        if (afterLower === 'ping') {
            const t = Date.now();
            try {
                await axios.get(`${CONFIG.bridgeUrl}/health`, { timeout: 5000 });
                await msg.reply(`🏓 Pong! (${Date.now() - t}ms)`);
            } catch { await msg.reply('🔌 Backend tidak merespons.'); }
            return;
        }
        if (afterLower === 'status') {
            try {
                const r = await axios.get(`${CONFIG.bridgeUrl}/health`, { timeout: 5000 });
                await msg.reply(`📊 Backend: OK | Busy: ${r.data.busy ? 'Ya' : 'Tidak'}`);
            } catch { await msg.reply('🔌 Backend tidak merespons.'); }
            return;
        }
        // Arm STT 60 detik — voice note berikutnya bakal di-transcribe via faster-whisper.
        // Anisa otomatis reply pakai voice (TTS auto-mirror) — gak perlu command terpisah buat TTS.
        // Key: msg.from (chat ID) — konsisten antara fromMe & received messages.
        if (['stt', 'tts', 'voice', 'suara', 'v', 'note', 'vn'].includes(afterLower)) {
            sttArmed.set(msg.from, Date.now() + STT_ARM_TTL_MS);
            log('INFO', `STT armed for ${msg.from} (TTL ${STT_ARM_TTL_MS / 1000}s)`);
            await msg.reply('🎤 Voice mode aktif 60 detik. Kirim voice note — Anisa bales pakai voice juga.');
            return;
        }

        // Admin commands — semua require user udah lolos gate (whitelist + login kalo password aktif)
        if (afterLower === 'wl' || afterLower.startsWith('wl ')) {
            await handleWlCommand(msg, afterPrefix.substring(2).trim(), senderPhone);
            return;
        }
        if (afterLower === 'password' || afterLower.startsWith('password ')) {
            await handlePasswordCommand(msg, afterPrefix.substring(8).trim());
            return;
        }
        if (afterLower === 'session' || afterLower.startsWith('session ')) {
            await handleSessionCommand(msg, afterPrefix.substring(7).trim(), senderPhone);
            return;
        }

        const body = afterPrefix;

        if (!body && !msg.hasMedia) return;
        if (isRateLimited(senderId)) return;

        await chat.sendStateTyping();

        // Download attachment
        const attachmentPaths = [];
        if (msg.hasMedia) {
            const fp = await downloadAttachment(msg);
            if (fp) attachmentPaths.push(fp);
        }

        // STT-active voice note: perintah kosong, backend STT yang generate dari transcript.
        // File attachment biasa: fallback "analisis file ini" + auto-append "baca file".
        let perintah = body || (attachmentPaths.length && !sttActive ? 'analisis file ini' : '');
        if (!perintah && !sttActive) return;

        if (!sttActive && attachmentPaths.length && !['gambar','foto','pdf','lihat','analisis','baca'].some(k => perintah.toLowerCase().includes(k))) {
            perintah += ' baca file';
        }

        log('INFO', `→ Anisa: "${perintah.substring(0, 80) || '[voice note → STT]'}"`);

        progressMessage = await msg.reply(PROCESSING_MESSAGE);

        // Keep "typing..." indicator hidup selama LangGraph proses (re-trigger tiap 8s)
        const typingInterval = setInterval(() => {
            chat.sendStateTyping().catch(() => {});
        }, 8000);

        let result;
        try {
            result = await sendToAnisa(perintah, senderId, attachmentPaths);
        } finally {
            clearInterval(typingInterval);
            await chat.clearState().catch(() => {});
        }

        if (!result?.response) {
            await updateProgressMessage(
                progressMessage,
                msg,
                '😵 Tidak ada respons. Coba lagi.',
            );
            return;
        }

        // TTS auto-mirror: kalau backend kirim voice_file (input voice → reply voice juga)
        // voice_mode 'full'   → voice doang, skip kirim text duplicate (reply <=80 chars)
        // voice_mode 'opener' → text full + voice basa-basi LLM-generated (reply >80 chars)
        const voiceFile = result.voice_file;
        const voiceMode = result.voice_mode;
        const skipTextReply = voiceMode === 'full' && voiceFile && fs.existsSync(voiceFile);

        let chunks = [];
        if (!skipTextReply) {
            chunks = smartChunks(sanitizeForWhatsApp(result.response));
            await updateProgressMessage(progressMessage, msg, chunks[0]);
            for (let i = 1; i < chunks.length; i++) {
                await new Promise(r => setTimeout(r, 500));
                await chat.sendMessage(chunks[i]);
            }
        } else {
            await updateProgressMessage(progressMessage, msg, VOICE_READY_MESSAGE);
        }

        // Kirim voice note kalau ada
        if (voiceFile && fs.existsSync(voiceFile)) {
            try {
                const voiceMedia = MessageMedia.fromFilePath(voiceFile);
                await new Promise(r => setTimeout(r, 300));
                await chat.sendMessage(voiceMedia, { sendAudioAsVoice: true });
            } catch (e) { log('WARN', `Gagal kirim voice note: ${e.message}`); }
        }

        // Kirim output files
        if (result.output_files?.length) {
            for (const fp of result.output_files) {
                try {
                    if (fs.existsSync(fp)) {
                        const media = MessageMedia.fromFilePath(fp);
                        await new Promise(r => setTimeout(r, 300));
                        await chat.sendMessage(media, { caption: `📎 ${path.basename(fp)}` });
                    }
                } catch (e) { log('WARN', `Gagal kirim file: ${e.message}`); }
            }
        }

        log('INFO', `✓ ${chunks.length} chunk, ${result.output_files?.length || 0} files${voiceFile ? ` + voice(${voiceMode})` : ''}`);
    } catch (error) {
        log('ERROR', `${error.message}`);
        try {
            if (progressMessage) {
                await updateProgressMessage(
                    progressMessage,
                    msg,
                    `❌ Error: ${error.message}`,
                );
            } else {
                await msg.reply(`❌ Error: ${error.message}`);
            }
        } catch (replyError) {
            log('ERROR', `Gagal kirim status error: ${replyError.message}`);
        }
    }
}

// Pakai message_create biar pesan fromMe (lu kirim dari HP utama) juga ke-handle
client.on('message_create', handleMessage);

// ============================================================
// SHUTDOWN
// ============================================================
process.on('SIGINT', async () => { await client.destroy(); process.exit(0); });
process.on('SIGTERM', async () => { await client.destroy(); process.exit(0); });

// ============================================================
// START
// ============================================================
log('INFO', '🚀 Starting WA Bridge...');
log('INFO', `   Bridge: ${CONFIG.bridgeUrl}`);
client.initialize();
