const THINKING_PREVIEW = '🧠 *ANISA lagi mikir...*';

function formatAnisaResponse(text) {
    return `🤖 *ANISA*\n${text}`;
}

async function deliverFirstChunk(
    previewMessage,
    chunk,
    sendReply,
    onWarning = () => {},
) {
    try {
        const edited = await previewMessage?.edit(chunk);
        if (edited) return 'edited';
    } catch (error) {
        onWarning(error);
    }
    await sendReply(chunk);
    return 'sent';
}

async function resolveSentPreview(
    client,
    chatId,
    previewMessage,
    previewText,
    onWarning = () => {},
) {
    if (previewMessage) return previewMessage;
    try {
        const chat = await client.getChatById(chatId);
        const messages = await chat.fetchMessages({ limit: 8 });
        return [...messages]
            .reverse()
            .find(message => (
                message.fromMe
                && message.body === previewText
            )) || null;
    } catch (error) {
        onWarning(error);
        return null;
    }
}

module.exports = {
    THINKING_PREVIEW,
    formatAnisaResponse,
    deliverFirstChunk,
    resolveSentPreview,
};
