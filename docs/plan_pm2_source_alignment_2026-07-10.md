# Plan PM2 Source Alignment - 2026-07-10

## Root Cause
- `pm2 describe anisa-v3` menunjukkan runtime aktif dari `.worktrees/anisa-desktop`.
- Root repo berada di branch `feature/last30days`, sedangkan runtime berada di `feature/anisa-desktop`.
- Diff antar branch besar dan menyentuh desktop API, permission gate, threads, dan ecosystem config.

## Decision
- Jangan paksa `anisa-v3` pindah ke root sekarang.
- Pakai source production aktif `.worktrees/anisa-desktop` sebagai sumber PM2 sampai branch production disatukan secara sadar.
- Persist PM2 dump agar resurrect tidak balik ke state lama yang tidak jelas.

## Steps
1. Validasi config PM2 di `.worktrees/anisa-desktop/ecosystem.config.js`.
2. Jalankan syntax check config.
3. Apply/reload `anisa-v3` dari config worktree production.
4. Jalankan `pm2 save`.
5. Verifikasi `pm2 describe anisa-v3` menunjukkan script/cwd worktree production dan scheduler Mekanik aktif.
6. Catat keputusan di `error_solutions.md`.

## Not Doing
- Tidak checkout branch.
- Tidak merge branch.
- Tidak delete worktree.
- Tidak switch runtime ke root branch `feature/last30days` karena delta terlalu besar.
