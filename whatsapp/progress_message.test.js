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
    const progressMessage = {
        edit: async () => {
            throw new Error('edit rejected');
        },
    };
    const sourceMessage = { reply: async content => replies.push(content) };

    const edited = await updateProgressMessage(
        progressMessage,
        sourceMessage,
        'jawaban fallback',
    );

    assert.equal(edited, false);
    assert.deepEqual(replies, ['jawaban fallback']);
});
