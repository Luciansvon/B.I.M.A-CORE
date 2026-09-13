# Anisa Efficiency Cleanup — Handoff untuk Claude

> **Status:** Decision gate disetujui Bima 2026-07-11 — Threads: **Opsi A** (tetap di BIMA_CORE). Worktree: **hapus keduanya** (dieksekusi, lihat catatan P0).

**Tujuan:** Mengurangi duplikasi dan beban jalur runtime Anisa tanpa menghapus fitur aktif atau worktree yang masih menyimpan pekerjaan.

**Prinsip:** Sedikit LOC bukan target utama. Prioritaskan pengurangan import/startup cost, jumlah tool yang dilihat LLM, panggilan API berulang, blocking task, dan maintenance ganda.

---

## Kondisi yang sudah diverifikasi

1. Threads BIMA_CORE masih aktif:
   - `core/discord_bot.py:205-206` memulai `core.threads_scheduler`.
   - `core/discord_bot.py:312` dan `core/discord_bot.py:397` memakai `core.threads_commands`.
   - `.env` berisi `ENABLE_THREADS_AUTO=true`.
2. `AI_sosmed` adalah repo Git mandiri, tetapi saat audit:
   - tidak memiliki `AI_sosmed/.env`;
   - tidak ada proses `AI_sosmed`/`Bot_thread` yang berjalan;
   - tidak terdaftar di `ecosystem.config.js` BIMA_CORE.
3. Kesimpulan: source Threads memang terduplikasi dan sudah drift, tetapi **bukan dua runtime aktif**. Menghapus Threads dari BIMA_CORE sekarang akan mematikan fitur aktif.
4. `.worktrees/` berukuran sekitar 6,3 GB, tetapi dua worktree masih terdaftar di Git:
   - `.worktrees/anisa-desktop` — dirty: ada perubahan `core/discord_bot.py` dan file baru `core/mekanik_maintenance_scheduler.py`.
   - `.worktrees/p0-runtime-foundation` — clean dan commit-nya sudah masuk `main`.
5. `services/browser/.venv/` tidak terlacak Git dan memiliki `.gitignore` internal. Masalahnya hanya memperlambat scanner yang tidak memakai exclude.

---

## Koreksi terhadap audit awal

- Jangan sebut Threads sebagai “dual-bot aktif”. Istilah yang tepat: **dua source fork, satu runtime aktif**.
- Jangan menjalankan `rm -rf .worktrees`. Gunakan `git worktree remove` hanya untuk worktree clean yang sudah dipastikan tidak dibutuhkan.
- Jangan menghitung `agent-reach/` dan `tools/last30days-skill/` sebagai source inti Anisa; keduanya kode pihak ketiga/vendored.
- File lebih dari 800 baris adalah maintenance smell, bukan bukti respons Anisa lambat. Refactor hanya jika profiling atau frekuensi perubahan membenarkan.

---

## Decision Gate 1 — Pemilik fitur Threads

Bima harus memilih salah satu:

### Opsi A — Tetap di BIMA_CORE untuk sekarang (paling aman)

- Pertahankan `core/threads_commands.py` dan `core/threads_scheduler.py`.
- Anggap `AI_sosmed` sebagai eksperimen/backup; jangan sinkronkan dua arah.
- Hapus repo lokal `AI_sosmed` hanya jika Bima menyatakan tidak akan dipakai lagi.
- Dampak respons Anisa: hampir tidak berubah; risiko migrasi paling rendah.

### Opsi B — Pindahkan penuh ke AI_sosmed (target arsitektur lebih bersih)

- Siapkan token/config dan proses PM2 `AI_sosmed` terlebih dahulu.
- Jalankan smoke test command, approval DM, publish, scheduler, dan reply komentar.
- Matikan `ENABLE_THREADS_AUTO` di BIMA_CORE.
- Baru lepaskan handler/import Threads dari `core/discord_bot.py` dan hapus dua modul Threads BIMA_CORE.
- Jangan menjalankan dua bot dengan token/command yang sama tanpa desain routing yang jelas.
- Dampak: mengurangi coupling dan contention scheduler di Anisa, tetapi menambah satu proses Python terpisah.

**Rekomendasi:** Opsi A sampai AI_sosmed punya `.env`, PM2 entry, dan smoke test. Setelah itu migrasi satu arah ke Opsi B; jangan mempertahankan dua source fork permanen.

---

## Urutan kerja setelah decision gate disetujui

### P0 — Lindungi pekerjaan aktif — ✅ SELESAI 2026-07-11

- [x] `git status --short` dijalankan di main dan setiap worktree.
- [x] Temuan baru: `anisa-desktop` memang dirty secara git, tetapi isinya **identik dengan main** — `core/mekanik_maintenance_scheduler.py` sudah tracked di main dan sama persis; `core/discord_bot.py` worktree identik byte-per-byte dengan main HEAD. Tidak ada pekerjaan unik yang hilang.
- [x] Bima menyetujui hapus **kedua** worktree. Dieksekusi via `git worktree remove` (p0) dan `git worktree remove --force` (anisa-desktop, force aman karena konten sudah di main) + `git worktree prune`.
- [x] `git worktree list` terverifikasi: tinggal main + `anisa-rag-upgrade` (superpowers, di luar repo). Folder `.worktrees/` kosong sudah dihapus, ±6,3 GB kembali.
- [ ] Sisa: folder artefak kosong `wsl.localhost/` di root repo (0 file, 8 dir kosong) — penghapusan menunggu konfirmasi Bima.

### P1 — Putuskan satu source Threads — ✅ DIPUTUSKAN: Opsi A

- [x] Bima memilih Opsi A (2026-07-11): Threads tetap di BIMA_CORE, `AI_sosmed` dianggap eksperimen/backup, tidak disinkronkan dua arah. Tidak ada perubahan kode yang diperlukan sekarang. Migrasi ke Opsi B dipertimbangkan lagi hanya setelah AI_sosmed punya `.env`, PM2 entry, dan smoke test.
- [ ] Eksekusi hanya Opsi A atau Opsi B; jangan membuat shared package ketiga.
- [ ] Jika memilih Opsi B, tes AI_sosmed sebelum mengubah BIMA_CORE.
- [ ] Setelah migrasi, grep seluruh caller:

```bash
rg -n "threads_commands|threads_scheduler|!threads|!thread" core main.py ecosystem.config.js tests
```

- [ ] Jalankan test Threads yang sudah tersedia:

```bash
bima_env/bin/pytest tests/test_threads_dedup.py tests/test_threads_reply_prompt.py tests/test_threads_topic_dedup.py tests/test_threads_revision.py tests/test_threads_no_ai_leak.py -q
```

### P2 — Ukur sebelum memecah file besar

- [ ] Profil startup, handler chat biasa, dan handler Threads secara terpisah.
- [ ] Pecah `core/furniture_qc.py` hanya berdasarkan tanggung jawab yang memang berubah terpisah: schema/input, vision inference, scoring, dan rendering.
- [ ] Jangan pecah `teams/t2_visual.py` hanya karena 804 baris; ukur manfaat dan frekuensi edit dulu.
- [ ] Jangan refactor clone internal `tools/last30days-skill`; update dari upstream atau biarkan vendored.

### P3 — Tambahkan audit rutin tanpa membebani runtime

- [ ] Jalankan tool hanya di CI/dev, bukan di proses Anisa:

```bash
npx jscpd core teams tools --ignore "**/last30days-skill/**,**/.venv/**,**/.worktrees/**"
uvx radon cc core teams tools -s -a
uvx vulture core teams tools --exclude "*/last30days-skill/*,*/.venv/*"
```

- [ ] Jangan menambah tool tersebut ke `requirements.txt` runtime.

---

## Definition of Done

- Hanya satu source Threads yang menjadi authoritative.
- Tidak ada fitur Threads yang hilang sebelum penggantinya lolos smoke test.
- Worktree dirty tetap aman.
- Scanner mengecualikan `.worktrees`, `.venv`, dan kode vendored.
- Klaim “lebih cepat” harus disertai perbandingan latency sebelum/sesudah; pengurangan LOC saja tidak cukup.
- Semua error dan solusinya dicatat ke `error_solutions.md`.
