const test = require('node:test');
const assert = require('node:assert/strict');
const preview = require('../message_preview');

test('formats final text with Anisa identity', () => {
    assert.equal(
        preview.formatAnisaResponse?.('Jawaban'),
        '🤖 *ANISA*\nJawaban',
    );
});

test('edits thinking preview into final response', async () => {
    const edits = [];
    const sent = [];
    const previewMessage = {
        edit: async (text) => {
            edits.push(text);
            return { body: text };
        },
    };

    const mode = await preview.deliverFirstChunk?.(
        previewMessage,
        'final',
        async text => sent.push(text),
    );

    assert.equal(mode, 'edited');
    assert.deepEqual(edits, ['final']);
    assert.deepEqual(sent, []);
});

test('sends final response when preview edit is unavailable', async () => {
    const sent = [];
    const previewMessage = { edit: async () => null };

    const mode = await preview.deliverFirstChunk?.(
        previewMessage,
        'final',
        async text => sent.push(text),
    );

    assert.equal(mode, 'sent');
    assert.deepEqual(sent, ['final']);
});

test('recovers the sent preview when self-chat send returns no Message', async () => {
    const target = {
        body: '🧠 *ANISA lagi mikir...*',
        fromMe: true,
        edit: async () => target,
    };
    const client = {
        getChatById: async () => ({
            fetchMessages: async () => [
                { body: 'pesan lain', fromMe: true },
                target,
            ],
        }),
    };

    const recovered = await preview.resolveSentPreview?.(
        client,
        '628111111111@c.us',
        null,
        '🧠 *ANISA lagi mikir...*',
    );

    assert.equal(recovered, target);
});
