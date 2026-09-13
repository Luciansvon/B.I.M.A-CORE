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
