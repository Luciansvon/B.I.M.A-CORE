const test = require('node:test');
const assert = require('node:assert/strict');

const { sanitizeForWhatsApp } = require('../sanitize');


test('keeps inline code content unchanged', () => {
    assert.equal(sanitizeForWhatsApp('`__init__`'), '__init__');
    assert.equal(
        sanitizeForWhatsApp("`if __name__=='__main__':`"),
        "if __name__=='__main__':"
    );
});


test('protects an unclosed fenced block to end of message', () => {
    assert.equal(sanitizeForWhatsApp('```py\n__init__'), '```py\n__init__');
});


test('preserves balanced parentheses in markdown URLs', () => {
    assert.equal(
        sanitizeForWhatsApp('[x](https://en.wikipedia.org/wiki/Foo_(bar))'),
        'x: https://en.wikipedia.org/wiki/Foo_(bar)'
    );
});


test('still converts narrative emphasis', () => {
    assert.equal(
        sanitizeForWhatsApp('**tebal** dan __juga__'),
        '*tebal* dan *juga*'
    );
});
