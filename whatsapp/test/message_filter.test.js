const test = require('node:test');
const assert = require('node:assert/strict');
const messageFilter = require('../message_filter');
const { shouldHandleMessage } = messageFilter;

test('ignores bridge-generated error replies', () => {
    assert.equal(
        shouldHandleMessage({ body: '❌ Error: r', type: 'chat' }, '/bot', false),
        false,
    );
});

test('accepts prefixed owner commands', () => {
    assert.equal(
        shouldHandleMessage({ body: '/bot ping', type: 'chat' }, '/bot', false),
        true,
    );
});

test('accepts only armed voice notes without prefix', () => {
    assert.equal(shouldHandleMessage({ body: '', type: 'ptt' }, '/bot', true), true);
    assert.equal(shouldHandleMessage({ body: '', type: 'ptt' }, '/bot', false), false);
});

test('keeps outgoing command usable when WhatsApp chat lookup fails transiently', async () => {
    const warnings = [];
    const context = await messageFilter.resolveMessageContext?.(
        {
            fromMe: true,
            from: '628000000000@c.us',
            to: '628111111111@c.us',
            getChat: async () => {
                throw new Error('r');
            },
        },
        (error) => warnings.push(error.message),
    );

    assert.deepEqual(context, {
        chatId: '628111111111@c.us',
        isGroup: false,
        chat: null,
    });
    assert.deepEqual(warnings, ['r']);
});

test('maps LID reply target to its phone-number JID', async () => {
    const calls = [];
    const client = {
        getContactLidAndPhone: async (ids) => {
            calls.push(ids);
            return [{
                lid: '123456789012345@lid',
                pn: '628111111111@c.us',
            }];
        },
    };

    const target = await messageFilter.resolveReplyChatId?.(
        client,
        '123456789012345@lid',
    );

    assert.equal(target, '628111111111@c.us');
    assert.deepEqual(calls, [['123456789012345@lid']]);
});
