const test = require('node:test');
const assert = require('node:assert/strict');
const { shouldHandleMessage } = require('../message_filter');

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
