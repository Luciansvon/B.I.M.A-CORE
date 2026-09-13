# WhatsApp Anisa Identity Preview Design

## Tujuan

Pesan bot di self-chat WhatsApp harus mudah dibedakan dari pesan Bima walau keduanya memakai akun yang sama. Saat AI masih memproses, chat harus langsung menampilkan satu pesan sementara.

## Perilaku

- Jalur AI mengirim `🧠 *ANISA lagi mikir...*` sebelum request HTTP ke backend.
- Jawaban teks pertama memakai header `🤖 *ANISA*`.
- Pesan preview diedit menjadi chunk jawaban pertama agar chat tetap bersih.
- Jika edit tidak didukung WhatsApp Web, jawaban final dikirim sebagai pesan baru.
- Chunk lanjutan, voice note, dan file tetap memakai jalur pengiriman saat ini.
- Command cepat seperti `ping`, login, dan admin tidak membuat preview karena hasilnya langsung tersedia.

## Error Handling

Jika backend gagal setelah preview terkirim, bridge mencoba mengedit preview menjadi pesan error beridentitas Anisa. Jika edit gagal, bridge mengirim error sebagai pesan baru.

## Verifikasi

- Unit test format identitas, edit preview, dan fallback kirim baru.
- Node syntax check.
- Restart hanya `bima-whatsapp`.
- Live self-chat: preview harus muncul sebelum respons dan kemudian berubah menjadi jawaban final atau diikuti fallback final.
