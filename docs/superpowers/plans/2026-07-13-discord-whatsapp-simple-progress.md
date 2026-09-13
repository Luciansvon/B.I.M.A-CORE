# Discord + WhatsApp Simple Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menampilkan satu status kerja sederhana di WhatsApp, mempertahankan status Discord yang sudah ada, dan tetap menyembunyikan stream internal Manager.

**Architecture:** Discord tetap memakai `progress_callback` yang sudah berjalan. WhatsApp membuat satu pesan progress sebelum request backend, lalu helper kecil mengedit pesan itu menjadi jawaban, status voice, atau error dengan fallback ke reply baru bila WhatsApp menolak edit.

**Tech Stack:** Node.js 22, `whatsapp-web.js` 1.34.7, built-in `node:test`, Python pytest untuk regression filter LangGraph.

---

## File Map

- Create: `whatsapp/progress_message.js` — konstanta status dan fallback edit/reply.
- Create: `whatsapp/progress_message.test.js` — regression test tanpa koneksi WhatsApp.
- Modify: `whatsapp/index.js` — pasang siklus hidup pesan progress ke handler aktif.
- Modify: `error_solutions.md` — catat penyebab preview hilang dan solusi minimal.

Catatan git: `whatsapp/index.js` dan `error_solutions.md` sudah memiliki perubahan lokal sebelum task ini. Jangan commit implementation files supaya perubahan lama milik Bima tidak ikut terbawa; tunjukkan diff scoped saja.

### Task 1: Helper progress WhatsApp dengan TDD

**Files:**
- Create: `whatsapp/progress_message.test.js`
- Create: `whatsapp/progress_message.js`

- [ ] **Step 1: Tulis failing test**

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    PROCESSING_MESSAGE,
    VOICE_READY_MESSAGE,
    updateProgressMessage,
} = require('./progress_message');

test('progress labels tetap sederhana dan user-facing', () => {
    assert.equal(PROCESSING_MESSAGE, '⏳ Anisa lagi baca dan proses permintaan...');
    assert.equal(VOICE_READY_MESSAGE, '🎤 Balasan suara siap.');
});

test('jawaban final mengedit pesan progress yang sama', async () => {
    const edits = [];
    const replies = [];
    const progressMessage = { edit: async content => edits.push(content) };
    const sourceMessage = { reply: async content => replies.push(content) };

    const edited = await updateProgressMessage(
        progressMessage,
        sourceMessage,
        'jawaban final',
    );

    assert.equal(edited, true);
    assert.deepEqual(edits, ['jawaban final']);
    assert.deepEqual(replies, []);
});

test('reply baru dipakai hanya saat edit ditolak WhatsApp', async () => {
    const replies = [];
    const progressMessage = { edit: async () => { throw new Error('edit rejected'); } };
    const sourceMessage = { reply: async content => replies.push(content) };

    const edited = await updateProgressMessage(
        progressMessage,
        sourceMessage,
        'jawaban fallback',
    );

    assert.equal(edited, false);
    assert.deepEqual(replies, ['jawaban fallback']);
});
```

- [ ] **Step 2: Jalankan test dan pastikan RED**

Run:

```bash
node --test whatsapp/progress_message.test.js
```

Expected: FAIL dengan `Cannot find module './progress_message'` karena helper belum dibuat.

- [ ] **Step 3: Implementasi minimum**

```javascript
const PROCESSING_MESSAGE = '⏳ Anisa lagi baca dan proses permintaan...';
const VOICE_READY_MESSAGE = '🎤 Balasan suara siap.';

async function updateProgressMessage(progressMessage, sourceMessage, content) {
    try {
        await progressMessage.edit(content);
        return true;
    } catch (error) {
        await sourceMessage.reply(content);
        return false;
    }
}

module.exports = {
    PROCESSING_MESSAGE,
    VOICE_READY_MESSAGE,
    updateProgressMessage,
};
```

- [ ] **Step 4: Jalankan test dan pastikan GREEN**

Run:

```bash
node --test whatsapp/progress_message.test.js
```

Expected: 3 test PASS, 0 FAIL.

### Task 2: Integrasi satu pesan progress ke handler WhatsApp

**Files:**
- Modify: `whatsapp/index.js:17-24`
- Modify: `whatsapp/index.js:533-738`

- [ ] **Step 1: Import helper**

Tambahkan setelah import modul lokal/Node:

```javascript
const {
    PROCESSING_MESSAGE,
    VOICE_READY_MESSAGE,
    updateProgressMessage,
} = require('./progress_message');
```

- [ ] **Step 2: Simpan pesan progress dalam scope handler**

Ubah awal handler menjadi:

```javascript
async function handleMessage(msg) {
    let progressMessage = null;
    try {
```

Setelah log request ke Anisa dan sebelum `typingInterval`, tambahkan:

```javascript
        progressMessage = await msg.reply(PROCESSING_MESSAGE);
```

- [ ] **Step 3: Ganti pesan progress pada seluruh terminal path**

Untuk respons kosong:

```javascript
        if (!result?.response) {
            await updateProgressMessage(
                progressMessage,
                msg,
                '😵 Tidak ada respons. Coba lagi.',
            );
            return;
        }
```

Untuk respons teks:

```javascript
        let chunks = [];
        if (!skipTextReply) {
            chunks = smartChunks(result.response);
            await updateProgressMessage(progressMessage, msg, chunks[0]);
            for (let i = 1; i < chunks.length; i++) {
                await new Promise(r => setTimeout(r, 500));
                await chat.sendMessage(chunks[i]);
            }
        } else {
            await updateProgressMessage(progressMessage, msg, VOICE_READY_MESSAGE);
        }
```

Untuk exception handler:

```javascript
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
```

- [ ] **Step 4: Verifikasi syntax dan helper**

Run:

```bash
node --check whatsapp/index.js
node --test whatsapp/progress_message.test.js
```

Expected: syntax exit 0; 3 test PASS.

### Task 3: Catat regresi dan verifikasi runtime

**Files:**
- Modify: `error_solutions.md`
- Test: `tests/test_manager_routing.py`

- [ ] **Step 1: Tambahkan Log 82 tanpa mengubah log lama**

```markdown
## Log 82: Preview Kerja Hilang Setelah Stream Manager Diblokir
* **Masalah**: Discord/WhatsApp tidak lagi memberi preview yang cukup jelas saat Anisa memproses request setelah hardening Manager.
* **Root Cause**: Stream `manager_node` sengaja diblokir agar tag `[ROUTE: ...]` dan narasi internal tidak bocor; WhatsApp hanya mempertahankan indikator typing tanpa pesan status.
* **Solusi**: Pertahankan filter stream Manager dan status node Discord. Di WhatsApp, kirim satu pesan status umum lalu edit pesan yang sama menjadi jawaban, status voice, atau error tanpa menambah protokol streaming.
* **Verifikasi**: Helper progress lulus 3 test, `node --check whatsapp/index.js` lulus, regression filter Manager tetap lulus, dan `bima-whatsapp` online setelah restart.
```

Tambahkan juga error penyusunan plan yang terjadi pada sesi ini:

```markdown
## Log 83: Patch Plan Ditolak karena Prefix Baris Hilang
* **Masalah**: Percobaan pertama membuat plan gagal dengan `invalid hunk` dan file plan tidak terbentuk.
* **Root Cause**: Satu baris command di blok Markdown tidak diawali prefix `+` yang diwajibkan format `Add File` pada `apply_patch`.
* **Solusi**: Pastikan setiap baris file baru memiliki prefix patch, lalu ulangi patch. Percobaan kedua berhasil tanpa perubahan parsial dari percobaan pertama.
```

- [ ] **Step 2: Pastikan filter keamanan Discord tetap hijau**

Run:

```bash
source bima_env/bin/activate
python -m pytest tests/test_manager_routing.py::test_manager_stream_event_is_not_user_facing -q
```

Expected: 1 test PASS.

- [ ] **Step 3: Periksa diff scoped**

Run:

```bash
git diff --check -- whatsapp/index.js whatsapp/progress_message.js whatsapp/progress_message.test.js error_solutions.md
git diff -w -- whatsapp/index.js error_solutions.md
```

Expected: tidak ada whitespace error; diff semantik hanya siklus progress WA serta Log 82–83.

- [ ] **Step 4: Restart bridge WhatsApp dan cek startup**

Run:

```bash
pm2 restart bima-whatsapp
pm2 logs bima-whatsapp --nostream --lines 80
pm2 list
```

Expected: `bima-whatsapp` online tanpa syntax/runtime error baru.

- [ ] **Step 5: Handoff smoke manual**

Kirim dari WhatsApp:

```text
/bot tes preview
```

Expected: satu pesan `⏳ Anisa lagi baca dan proses permintaan...` muncul, kemudian pesan itu berubah menjadi jawaban final. Discord tetap menunjukkan status Manager/tim tanpa tag `[ROUTE: ...]`.
