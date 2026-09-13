# PLAN Pet Codex Pijar - 2026-07-16

> **Status:** Menunggu persetujuan Bima.

## Hasil Explore

- Folder custom pet Codex tersedia di `C:\Users\shint\.codex\pets`, tetapi masih kosong.
- Kontrak pet v2 memakai atlas WebP `1536x2288`, grid 8x11, sel `192x208`, dan `spriteVersionNumber: 2`.
- Pet wajib punya 9 animasi standar serta 16 arah pandang yang divalidasi secara deterministik dan visual.
- Slime hijau membutuhkan chroma key magenta agar warna tubuh tidak ikut terhapus.
- Efek api harus menyatu atau bersentuhan dengan tubuh; partikel api terpisah, glow, bayangan, dan motion trail tidak boleh dipakai.

## Desain Terpilih

- **Nama:** Pijar.
- **Gaya:** chibi `3d-toy` glossy, bentuk slime jelly hijau giok, mata gelap besar, mulut mungil, dan mahkota api jingga-kuning yang menempel di kepala/punggung.
- **Siluet:** badan pendek membulat tanpa kaki terpisah; dua lengan kecil muncul saat gestur agar tetap jelas di ukuran pet.
- **Idle:** napas/bob halus sambil mata dan bagian atas tubuh menengok kanan lalu kiri; dasar tubuh tetap stabil.
- **Saat bekerja (`running`):** micro-hop berulang seperti pogo, ekspresi fokus, api memanjang-memendek mengikuti pantulan; bukan berlari dengan kaki.
- **Jumping:** squash, ancang-ancang, meluncur, puncak bulat, turun, lalu mendarat gepeng tanpa debu atau bayangan.
- **State lain:** lambaian dengan lengan slime; gagal dengan badan kempis dan api merunduk; menunggu dengan pose berharap; review dengan condong fokus.
- **Arah pandang:** mata memimpin, bagian atas slime meregang sedikit, dasar tetap tertambat, dan mahkota api mengikuti dengan jeda kecil. Sprite tidak diputar utuh.

## Pertimbangan Gaya

1. **3D-toy glossy — dipilih:** karakter jelly dan api paling hidup serta mudah dibaca.
2. **Flat sticker:** ekstraksi lebih mudah, tetapi volume slime dan pantulannya lebih datar.
3. **Pixel art:** paling ringan, tetapi ekspresi chibi dan 16 arah pandang lebih terbatas.

## Langkah Kerja

1. **Getting Pijar ready:** siapkan run folder, spesifikasi visual, chroma magenta, prompt, dan manifest job tanpa menyentuh source BIMA_CORE.
2. **Imagining Pijar's main look:** hasilkan base art Pijar, cek identitas/siluet/api menempel, lalu jadikan canonical reference.
3. **Picturing Pijar's poses:** hasilkan dan validasi row idle, gerak kanan/kiri, waving, jumping, failed, waiting, working, review, empat cardinal, serta dua row 16 arah pandang; perbaiki hanya row yang gagal.
4. **Hatching Pijar:** rakit atlas v2, jalankan inspeksi frame, preview GIF, continuity, despill, validasi atlas, tiga blind direction QA, final visual QA, lalu pasang `pet.json` dan `spritesheet.webp` ke folder custom pet Codex.

## Verifikasi dan Batasan

- Atlas final wajib `1536x2288`, transparan, sel terpakai tidak kosong, dan sel tidak terpakai benar-benar transparan.
- `qa/review.json` tanpa error; despill dan `validate_atlas.py --require-v2` wajib lulus.
- Cardinal up/right/down/left tidak boleh ambigu; 16 arah harus membentuk loop searah jarum jam yang konsisten.
- Semua kegagalan nyata, root cause, solusi, dan hasil verifikasi akan ditambahkan ke `error_solutions.md` tanpa mengubah catatan lama.
- Tidak memasang dependency, mengubah `.env`, menjalankan service, commit, atau operasi destruktif.
