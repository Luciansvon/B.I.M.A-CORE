# Plan WA Bridge Dependency Fix - 2026-07-10

## Root Cause
- `bima-whatsapp` PM2 status: `waiting restart`.
- Log terbaru menunjukkan `Error: Cannot find module 'whatsapp-web.js'`.
- `whatsapp/package.json` mendeklarasikan `whatsapp-web.js`, tetapi `whatsapp/node_modules/` tidak ada.
- Syntax `whatsapp/index.js` valid, jadi crash bukan karena syntax.

## Fix Plan
1. Install dependency dari lockfile:
   - `cd /home/bima_lucian/BIMA_CORE/whatsapp`
   - `npm ci`
2. Restart WA bridge:
   - `pm2 restart bima-whatsapp --update-env`
3. Verifikasi:
   - `pm2 describe bima-whatsapp` status `online`.
   - `pm2 logs bima-whatsapp --nostream --lines 80` tidak ada `MODULE_NOT_FOUND`.
   - Jika session WA invalid, cek QR baru di `outputs/wa_qr.png`.
4. Persist PM2:
   - `pm2 save`

## Risk
- `npm ci` akan membuat `whatsapp/node_modules/` dan bisa menjalankan install script Puppeteer.
- Jika Puppeteer mendownload Chromium, proses bisa makan waktu dan bandwidth.
- Ini tidak mengubah source code tracked, tetapi tetap termasuk install dependency sehingga butuh approval Bima.
