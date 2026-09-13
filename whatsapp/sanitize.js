'use strict';


function protectCode(text) {
    const tokens = [];
    let output = '';
    let index = 0;

    while (index < text.length) {
        if (text.startsWith('```', index)) {
            const close = text.indexOf('```', index + 3);
            const end = close === -1 ? text.length : close + 3;
            const token = `\u0000CODE${tokens.length}\u0000`;
            tokens.push(text.slice(index, end));
            output += token;
            index = end;
            continue;
        }

        if (text[index] === '`') {
            const close = text.indexOf('`', index + 1);
            if (close !== -1 && !text.slice(index + 1, close).includes('\n')) {
                const token = `\u0000CODE${tokens.length}\u0000`;
                tokens.push(text.slice(index + 1, close));
                output += token;
                index = close + 1;
                continue;
            }
        }

        output += text[index];
        index += 1;
    }

    return { output, tokens };
}


function replaceMarkdownLinks(text) {
    let output = '';
    let index = 0;

    while (index < text.length) {
        const labelStart = text.indexOf('[', index);
        if (labelStart === -1) {
            output += text.slice(index);
            break;
        }
        output += text.slice(index, labelStart);

        const labelEnd = text.indexOf('](', labelStart + 1);
        if (labelEnd === -1) {
            output += text.slice(labelStart);
            break;
        }

        const urlStart = labelEnd + 2;
        if (!text.startsWith('http://', urlStart) && !text.startsWith('https://', urlStart)) {
            output += text.slice(labelStart, urlStart);
            index = urlStart;
            continue;
        }

        let depth = 1;
        let cursor = urlStart;
        while (cursor < text.length && depth > 0) {
            if (text[cursor] === '(') depth += 1;
            if (text[cursor] === ')') depth -= 1;
            cursor += 1;
        }
        if (depth !== 0) {
            output += text.slice(labelStart);
            break;
        }

        const label = text.slice(labelStart + 1, labelEnd);
        const url = text.slice(urlStart, cursor - 1);
        output += `${label}: ${url}`;
        index = cursor;
    }

    return output;
}


function sanitizeForWhatsApp(text) {
    if (!text) return text;

    const protectedCode = protectCode(String(text));
    let output = replaceMarkdownLinks(protectedCode.output)
        .replace(/^#{1,6}\s+(.+)$/gm, '*$1*')
        .replace(/\*\*\*(.+?)\*\*\*/g, '*$1*')
        .replace(/\*\*(.+?)\*\*/g, '*$1*')
        .replace(/__(.+?)__/g, '*$1*');

    protectedCode.tokens.forEach((value, tokenIndex) => {
        output = output.split(`\u0000CODE${tokenIndex}\u0000`).join(value);
    });
    return output;
}


module.exports = { sanitizeForWhatsApp };
