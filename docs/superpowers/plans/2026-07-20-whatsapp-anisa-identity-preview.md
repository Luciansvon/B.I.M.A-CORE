# WhatsApp Anisa Identity Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tambahkan preview pemrosesan dan identitas `ANISA` pada jawaban AI WhatsApp.

**Architecture:** Presentasi pesan dipisah ke `whatsapp/message_preview.js` agar format, edit, dan fallback dapat diuji tanpa menyalakan client WhatsApp. `whatsapp/index.js` mengirim preview tepat sebelum request backend, lalu menyerahkan chunk pertama ke helper untuk diedit atau dikirim ulang.

**Tech Stack:** Node.js, `whatsapp-web.js`, built-in `node:test`.

---

### Task 1: Presenter Pesan WhatsApp

**Files:**
- Create: `whatsapp/message_preview.js`
- Create: `whatsapp/test/message_preview.test.js`

- [x] **Step 1: Write the failing tests**

```js
test('formats final text with Anisa identity', () => {
    assert.equal(formatAnisaResponse('Jawaban'), '🤖 *ANISA*\nJawaban');
});

test('edits thinking preview into final response', async () => {
    const preview = { edit: async text => ({ body: text }) };
    const sent = [];
    const mode = await deliverFirstChunk(preview, 'final', text => sent.push(text));
    assert.equal(mode, 'edited');
    assert.deepEqual(sent, []);
});

test('sends final response when preview edit fails', async () => {
    const preview = { edit: async () => null };
    const sent = [];
    const mode = await deliverFirstChunk(preview, 'final', async text => sent.push(text));
    assert.equal(mode, 'sent');
    assert.deepEqual(sent, ['final']);
});
```

- [x] **Step 2: Run test to verify RED**

Run: `node --test whatsapp/test/message_preview.test.js`

Expected: FAIL karena `message_preview.js` belum ada.

- [x] **Step 3: Implement minimal presenter**

```js
const THINKING_PREVIEW = '🧠 *ANISA lagi mikir...*';

function formatAnisaResponse(text) {
    return `🤖 *ANISA*\n${text}`;
}

async function deliverFirstChunk(previewMessage, chunk, sendReply) {
    try {
        const edited = await previewMessage?.edit(chunk);
        if (edited) return 'edited';
    } catch {}
    await sendReply(chunk);
    return 'sent';
}
```

- [x] **Step 4: Run test to verify GREEN**

Run: `node --test whatsapp/test/message_preview.test.js`

Expected: 3 test lulus.

### Task 2: Integrasi Preview ke Handler

**Files:**
- Modify: `whatsapp/index.js`
- Test: `whatsapp/test/message_filter.test.js`

- [x] **Step 1: Import presenter dan simpan reference preview**

```js
const {
    THINKING_PREVIEW,
    formatAnisaResponse,
    deliverFirstChunk,
} = require('./message_preview');

let previewMessage = null;
```

- [x] **Step 2: Kirim preview sebelum backend**

```js
previewMessage = await reply(THINKING_PREVIEW, { waitUntilMsgSent: true });
result = await sendToAnisa(perintah, attachmentPaths);
```

- [x] **Step 3: Edit preview menjadi chunk final**

```js
chunks = smartChunks(formatAnisaResponse(result.response));
await deliverFirstChunk(previewMessage, chunks[0], reply);
```

- [x] **Step 4: Ubah preview menjadi status voice atau error**

```js
await deliverFirstChunk(
    previewMessage,
    formatAnisaResponse('🎤 Jawaban dikirim lewat voice note.'),
    reply,
);
```

- [x] **Step 5: Verify Node suite and syntax**

Run:

```bash
node --test whatsapp/test/message_filter.test.js whatsapp/test/message_preview.test.js
node --check whatsapp/index.js
node --check whatsapp/message_preview.js
```

Expected: seluruh test dan syntax check lulus.

### Task 3: Runtime Verification

**Files:**
- Modify: `docs/WORKLOG.md`
- Modify: `docs/ERROR_SOLUTIONS.md`

- [x] **Step 1: Restart bridge**

Run: `pm2 restart bima-whatsapp`

Expected: `bima-whatsapp` kembali `online`.

- [x] **Step 2: Run live self-chat test**

Kirim `/bot tes preview`, cek preview muncul sebelum backend selesai, lalu pastikan preview diedit menjadi jawaban ber-header `🤖 *ANISA*` atau fallback jawaban baru terkirim.

- [x] **Step 3: Record verified behavior**

Catat hanya hasil aktual, test count, dan fallback yang benar-benar terlihat di runtime.
