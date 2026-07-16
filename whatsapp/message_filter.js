function shouldHandleMessage(msg, triggerPrefix, sttActive) {
    const text = (msg.body || '').trim().toLowerCase();
    return text.startsWith(triggerPrefix) || (msg.type === 'ptt' && sttActive);
}

module.exports = { shouldHandleMessage };
