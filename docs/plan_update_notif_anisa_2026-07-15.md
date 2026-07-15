# PLAN Update Notifikasi Startup Anisa — 2026-07-15

> **Status:** CODE selesai; VERIFY akhir dijalankan 2026-07-15.

## Hasil EXPLORE

- Notifikasi startup dibuat oleh `_build_startup_embed()` di `core/discord_bot.py`.
- Command aktif yang perlu diperkenalkan: chat via mention/DM, `/private`, `!status`, `!ocr`, `!qc`, `!cutlist`, `!arsip`, `!saham`, `!threads`, serta command musik.
- Embed saat ini memakai 8 field tim vertikal dan belum memberi petunjuk command.
- Desain harus tetap di bawah batas Discord: maksimal 25 field, 1.024 karakter per field, dan 6.000 karakter total.
- File aturan dengan variasi kapital hanya satu: `CLAUDE.md`. Error berulang berasal dari tiga referensi lowercase di `AGENTS.md` dan satu entry lowercase di `.gitignore`.
- `Rules for agent.md` adalah dokumen kedua yang diklaim sama, tetapi hash dan isinya sudah berbeda dari `CLAUDE.md`.
- Guard awal gagal sesuai harapan karena sumber aturan belum tunggal.

## Fix Sumber Aturan

1. Jadikan `CLAUDE.md` satu-satunya dokumen aturan rinci dengan menggabungkan 8 operating rules dan standar pengembangan yang masih relevan.
2. Hapus `Rules for agent.md` yang redundan dan sudah menyimpang.
3. Ubah seluruh referensi di `AGENTS.md` ke nama persis `CLAUDE.md`, serta hapus entry lowercase yang menyesatkan dari `.gitignore`.
4. Pertahankan Log 34 sebagai catatan canonical dan hapus Log 81 yang menduplikasi masalah sama.

## Opsi Desain

1. **Tambah daftar command di bawah tampilan lama** — diff paling kecil, tetapi notifikasi makin tinggi dan kurang nyaman dipindai.
2. **Command Center (rekomendasi)** — hero status baru, kapabilitas tim diringkas, command dikelompokkan, dan contoh mulai dibuat menonjol.
3. **Beberapa embed/pagination** — lebih interaktif, tetapi berlebihan untuk notifikasi startup dan menambah kode yang tidak dibutuhkan.

## Desain Terpilih

```text
🟢 ANISA ONLINE • B.I.M.A CORE
Sistem aktif • Mention @Anisa atau DM untuk mulai

🧠 THINK & REMEMBER      🎨 CREATE & ANALYZE
T1 Manager ...           T2 Visual ...
T3 Arsip ...             T4 Admin ...
T5 Intel ...             T7 Seniman ...

⚡ COMMAND CEPAT         🎵 MUSIK & MARKET
!status — kesehatan VPS  !play <judul> — putar musik
!ocr + gambar — OCR      !saham help — menu saham
!qc + drawing — QC       !threads <topik> — buat draf

🔒 /private start|stop — buka/tutup thread privat
```

## Langkah CODE dan VERIFY

1. Terapkan fix sumber aturan di atas, lalu jalankan ulang guard sampai hanya `CLAUDE.md` yang canonical.
2. Ubah hanya `_build_startup_embed()` agar struktur lebih ringkas, eye-catching, dan semua command utama memiliki keterangan.
3. Tambah unit test kecil untuk memastikan command penting tampil dan Embed tetap di bawah limit Discord.
4. Jalankan AST/import smoke check dan targeted pytest melalui `bima_env`.
5. Restart `anisa-v3` hanya bila prosesnya memang sedang online, lalu cek log startup dan notifikasi terkirim.

## Batasan

- Tidak menambah dependency, command baru, gambar eksternal, tombol, atau handler baru.
- Tidak mengubah alur `on_ready()`, routing command, `.env`, maupun service lain.
- Tidak menyentuh perubahan aktif di `whatsapp/` dan file kerja Bima lainnya.
- Penghapusan hanya untuk `Rules for agent.md`; tidak menghapus `CLAUDE.md` atau `AGENTS.md`.
