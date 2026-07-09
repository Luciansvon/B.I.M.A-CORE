# Plan: Agent Reach Hardening dan CI Pytest

Status approval: disetujui Bima melalui instruksi `gas` pada 9 Juli 2026.

1. Audit perubahan lokal dan pisahkan file di luar scope.
2. Tambah regression test untuk timeout CLI dan sanitasi tweet.
3. Implementasikan timeout, sanitasi link/mention/control character, dan batas output.
4. Tambah dependency development/CI serta workflow GitHub Actions untuk pytest.
5. Verifikasi di virtual environment bersih dan jalankan seluruh test lokal.
6. Catat error dan solusi di `docs/error_solutions.md`.
7. Commit dan push hanya file dalam scope ke branch aktif.
