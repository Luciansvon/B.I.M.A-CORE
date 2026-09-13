function shouldHandleMessage(msg, triggerPrefix, sttActive) {
    const text = (msg.body || '').trim().toLowerCase();
    return text.startsWith(triggerPrefix) || (msg.type === 'ptt' && sttActive);
}

async function resolveMessageContext(msg, onWarning = () => {}) {
    const chatId = msg.fromMe ? msg.to : msg.from;
    let chat = null;
    try {
        chat = await msg.getChat();
    } catch (error) {
        onWarning(error);
    }
    return {
        chatId,
        isGroup: typeof chatId === 'string' && chatId.endsWith('@g.us'),
        chat,
    };
}

async function resolveReplyChatId(client, chatId, onWarning = () => {}) {
    if (typeof chatId !== 'string' || !chatId.endsWith('@lid')) {
        return chatId;
    }
    try {
        const mappings = await client.getContactLidAndPhone([chatId]);
        return mappings?.[0]?.pn || chatId;
    } catch (error) {
        onWarning(error);
        return chatId;
    }
}

module.exports = {
    shouldHandleMessage,
    resolveMessageContext,
    resolveReplyChatId,
};
