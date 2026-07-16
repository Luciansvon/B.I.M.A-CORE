# WhatsApp Error Reply Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menghentikan loop pesan `❌ Error: r` tanpa mematikan dukungan command `/bot` dari HP utama.

**Architecture:** Saring event `message_create` secara sinkron sebelum operasi WhatsApp Web apa pun. Hanya command ber-prefix atau voice note yang sudah di-arm boleh masuk ke `getChat()`; pesan balasan bot berhenti di filter dan tidak dapat memicu recursive error reply.

**Tech Stack:** Node.js 22, `whatsapp-web.js`, built-in `node:test`, PM2.

---

### Task 1: Reproduksi loop sebagai regression test

**Files:**
- Create: `whatsapp/test/message_filter.test.js`
- Create: `whatsapp/message_filter.js`

- [x] **Step 1: Tulis test yang menolak balasan error bot dan menerima command owner**

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { shouldHandleMessage } = require('../message_filter');

test('ignores bridge-generated error replies', () => {
    assert.equal(shouldHandleMessage({ body: '❌ Error: r', type: 'chat' }, '/bot', false), false);
});

test('accepts prefixed owner commands', () => {
    assert.equal(shouldHandleMessage({ body: '/bot ping', type: 'chat' }, '/bot', false), true);
});

test('accepts only armed voice notes without prefix', () => {
    assert.equal(shouldHandleMessage({ body: '', type: 'ptt' }, '/bot', true), true);
    assert.equal(shouldHandleMessage({ body: '', type: 'ptt' }, '/bot', false), false);
});
```

- [x] **Step 2: Jalankan test dan pastikan RED**

Run: `cd whatsapp && node --test test/message_filter.test.js`

Expected: FAIL dengan `Cannot find module '../message_filter'`.

- [x] **Step 3: Buat filter minimum**

```javascript
function shouldHandleMessage(msg, triggerPrefix, sttActive) {
    const text = (msg.body || '').trim().toLowerCase();
    return text.startsWith(triggerPrefix) || (msg.type === 'ptt' && sttActive);
}

module.exports = { shouldHandleMessage };
```

- [x] **Step 4: Jalankan test dan pastikan GREEN**

Run: `cd whatsapp && node --test test/message_filter.test.js`

Expected: 3 test PASS.

### Task 2: Putus recursive error reply di handler

**Files:**
- Modify: `whatsapp/index.js:15-20`
- Modify: `whatsapp/index.js:533-570`
- Modify: `whatsapp/index.js:734-738`

- [x] **Step 1: Import filter, hitung state pesan, dan return sebelum `msg.getChat()`**

```javascript
const { shouldHandleMessage } = require('./message_filter');

async function handleMessage(msg) {
    try {
        const text = msg.body?.trim() || '';
        const lower = text.toLowerCase();
        const prefix = CONFIG.triggerPrefix;
        const isVoiceNote = msg.type === 'ptt';
        const sttActive = isVoiceNote && isSttArmed(msg.from);

        if (!shouldHandleMessage(msg, prefix, sttActive)) return;

        const chat = await msg.getChat();
```

- [x] **Step 2: Hapus deklarasi/filter duplikat setelah `getChat()` dan pertahankan alur command yang ada**

Expected: `text`, `lower`, `prefix`, `isVoiceNote`, dan `sttActive` hanya dihitung sekali sebelum `getChat()`.

- [x] **Step 3: Sanitasi pesan error untuk user**

```javascript
    } catch (error) {
        log('ERROR', `${error.message}`);
        try { await msg.reply('❌ WhatsApp gagal memproses pesan. Coba sekali lagi.'); } catch {}
    }
```

- [x] **Step 4: Verifikasi test dan syntax**

Run: `cd whatsapp && node --test test/message_filter.test.js && node --check index.js && node --check message_filter.js`

Expected: seluruh test PASS dan kedua syntax check exit 0.

### Task 3: Dokumentasi insiden dan verifikasi runtime

**Files:**
- Modify: `error_solutions.md`

- [x] **Step 1: Tambahkan log insiden**

```markdown
## Log 100: WhatsApp Bridge Mengirim `❌ Error: r` Berulang
* **Masalah**: Satu kegagalan WhatsApp Web memicu ratusan balasan `❌ Error: r` melalui event `message_create`.
* **Root Cause**: Handler memanggil `msg.getChat()` sebelum menyaring event balasan bot. Saat `getChat()` melempar `r`, blok `catch` membalas error; balasan itu memicu `message_create` baru dan mengulang siklus.
* **Solusi**: Saring prefix/armed voice sebelum operasi async WhatsApp, pertahankan detail error hanya di log, dan kirim pesan generik ke user.
* **Verifikasi**: Unit test filter, syntax check Node, restart PM2, health endpoint, dan log startup WA tanpa kemunculan baru `❌ [WA] r`.
```

- [x] **Step 2: Restart service terkait**

Run: `source bima_env/bin/activate && pm2 restart anisa-v3 bima-whatsapp --update-env`

Expected: `anisa-v3` dan `bima-whatsapp` berstatus `online`.

- [x] **Step 3: Jalankan smoke test**

Run: `curl -fsS http://127.0.0.1:8001/health && pm2 logs bima-whatsapp --nostream --lines 80`

Expected: health `{"status":"ok","busy":false}`, WA bridge `ONLINE`, dan tidak ada kemunculan baru `❌ [WA] r`.

- [x] **Step 4: Jalankan regression suite terfokus**

Run: `source bima_env/bin/activate && pytest -q tests/test_healthcheck.py`

Expected: PASS.
