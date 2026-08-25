# AGENTS.md — BIMA_CORE

Sumber aturan utama untuk seluruh coding agent di repository ini. File khusus tool seperti `CLAUDE.md` hanya boleh mengarah ke file ini, bukan menyimpan aturan kedua.

## Project Summary

- BIMA_CORE adalah runtime multi-agent Python untuk Discord, WhatsApp, dashboard web, dan REST.
- Orkestrasi memakai LangGraph; agent spesialis memakai CrewAI.
- Runtime utama: Python 3.12 di WSL Ubuntu, virtual environment `bima_env/`, production melalui PM2.
- Entry point: `main.py`.
- Konfigurasi utama: `config.py`, `config_mcp.json`, `pyproject.toml`, `requirements*.txt`, `ecosystem.config.js`, dan `.env.example`.
- Test berada di `tests/`; CI berada di `.github/workflows/ci.yml`.

## Bima dan Gaya Respons

- Balas dalam Bahasa Indonesia casual, langsung ke inti, tanpa salam atau teori panjang.
- Jelaskan istilah coding dengan bahasa praktis; pakai diagram kecil bila hubungan sistem sulit dipahami.
- Ringkasan akhir maksimal lima baris dan selalu beri solusi atau pertanyaan lanjutan yang berguna.

## Workflow Wajib

```text
EXPLORE → PLAN → CODE → VERIFY
```

1. **EXPLORE** — baca file, caller, konfigurasi, test, dan diff terkait sebelum membuat klaim. Jangan membaca `.env` atau credential.
2. **PLAN** — buat tepat satu PLAN Markdown yang sekaligus menjadi task list, lalu minta satu persetujuan. Re-plan hanya jika Bima mengubah scope atau memintanya.
3. **CODE** — setelah persetujuan, lanjutkan tanpa approval tambahan untuk langkah rutin. Gunakan minimal diff dan jangan melakukan cleanup di luar scope.
4. **VERIFY** — jalankan pemeriksaan yang sebanding dengan risiko dan laporkan hasil sebenarnya. Task belum selesai jika verifikasi penting belum dijalankan.

Approval baru hanya diperlukan untuk perubahan scope, penghapusan data/file yang belum disetujui, dependency, `.env`/settings/CI, migration, credential, atau logika bisnis ambigu.

## Safety dan Git

- Pertahankan perubahan user yang sudah ada; selalu cek `git status` dan diff file target.
- Dilarang memakai `--force`, `--no-verify`, `git reset --hard`, clean paksa, atau menghapus test gagal.
- Jangan menyimpan token, key, password, isi `.env`, data pribadi, atau trace internal ke chat/dokumentasi.
- Jangan menyembunyikan error dengan `try/except: pass`.
- Jangan install/uninstall dependency, restart service, commit, push, atau mengubah CI tanpa scope/izin yang sesuai.

## Coding dan Testing

- Ikuti pola modul yang sedang disentuh; gunakan type annotation pada fungsi baru atau signature yang diubah.
- Perbaiki akar masalah pada shared path setelah memeriksa seluruh caller.
- Untuk fitur atau bugfix, tambah regression test terkecil yang membuktikan perilaku.
- External API call yang butuh retry memakai `core/api_retry.py:call_with_retry()`.
- Jangan menambah abstraksi, dependency, atau konfigurasi untuk kebutuhan spekulatif.

## Perintah Aktual

```bash
source bima_env/bin/activate
bima_env/bin/python main.py
bima_env/bin/python -m pytest -q --no-header
bima_env/bin/python -m pytest tests/test_qc.py -q
bima_env/bin/python scripts/healthcheck.py
node --check whatsapp/index.js

pm2 list
pm2 logs anisa-v3 --nostream --lines 50
pm2 restart anisa-v3 --update-env
pm2 restart bima-whatsapp
pm2 start ecosystem.config.js
```

Restart matrix: perubahan `core/`, `teams/`, `tools/`, atau dependency Python memerlukan `anisa-v3`; perubahan `whatsapp/` memerlukan `bima-whatsapp`.

## Repository Map

```text
main.py                    Bootstrap runtime
core/                      Channel handlers, LangGraph, scheduler, voice, dashboard
core/langgraph_nodes/      State dan node orchestration
teams/                     Definisi CrewAI agent
tools/                     Tool bersama dan plugin
tests/                     Pytest suite
whatsapp/                  Node.js WhatsApp bridge
dashboard/                 Frontend dashboard
services/                  Sidecar AgentMemory, browser, dan voice
scripts/                   Healthcheck dan utility operasional
docs/                      Arsitektur, error knowledge base, worklog, audit, dan plan
outputs/                   Artefak runtime; bukan source
```

## Dokumentasi

Baca sesuai kebutuhan:

1. `AGENTS.md`
2. `docs/WORKLOG.md`
3. `docs/ARCHITECTURE.md` untuk flow, boundary, state, atau deployment
4. `docs/ERROR_SOLUTIONS.md` sebelum menangani error non-trivial
5. `README.md` untuk setup dan penggunaan

Perbarui `ARCHITECTURE.md` saat flow, state, schema, service, atau boundary berubah. Perbarui `ERROR_SOLUTIONS.md` hanya setelah root cause dan solusi/mitigasi terverifikasi. Perbarui `WORKLOG.md` untuk checkpoint pekerjaan penting atau task yang ditinggalkan belum selesai; jangan simpan percakapan atau output terminal mentah.

Submodule `databasement/` dan komponen vendored `tools/last30days-skill/` memiliki dokumentasi sendiri; jangan digabung ke aturan root tanpa scope eksplisit.
