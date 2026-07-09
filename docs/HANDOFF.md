# HANDOFF — Perubahan Codex (branch `feature/last30days`)

Tanggal audit: 9 Juli 2026. Dokumen ini merangkum perubahan yang dibuat sesi Codex sebelumnya, status verifikasinya, bug yang sudah dibetulkan, dan item yang masih perlu keputusan Bima. Rujukan detail per-error ada di [error_solutions.md](error_solutions.md) (Log 8–12) dan rencananya di [implementation_plan.md](implementation_plan.md).

---

## 1. Ringkasan perubahan

### Threads — perombakan konten (paling besar)
- [core/threads_commands.py](../core/threads_commands.py) — model default naik ke `anthropic/claude-sonnet-5`, `max_tokens=1000` untuk menghindari error kredit OpenRouter 402, prompt Gen-Z ditulis ulang (dari pola "fakta unik → analogi besar → punchline" ke gaya curhat personal), draf final dibungkus tag `<draft>...</draft>` agar bersih diekstrak regex.
- [core/threads_scheduler.py:425](../core/threads_scheduler.py#L425) — fallback topik casual sekarang difilter dulu lewat recent-topics supaya tidak mengulang.
- [core/scientific_facts.json](../core/scientific_facts.json) — tambah 5 fakta untuk variasi konten.
- [docs/threads_genz_prompt_rules.md](threads_genz_prompt_rules.md) — bahan audit/aturan prompt Gen-Z (untraked, referensi).

### Command & tool baru
- [core/arsip_commands.py](../core/arsip_commands.py) — router `!arsip` (`help` / `hubungkan` / `index`), di-wire ke [core/discord_bot.py:381](../core/discord_bot.py#L381). Command `!thread` (tanpa `s`) juga sekarang dikenali.
- [teams/t3_arsip.py:411](../teams/t3_arsip.py#L411) — `VaultLinkerTool`: sisip `[[wikilink]]` semantik antar catatan Obsidian + backup file sebelum overwrite ke `outputs/backup/`.
- [tools/deslop_tool.py](../tools/deslop_tool.py) — `DeslopTool`, filter anti "AI slop" berbasis LLM. Aturan anti-slop juga disisipkan di 3 titik lain: backstory admin agent, `manager_node`, dan `apply_smart_revision` (lihat [AGENTS.md](../AGENTS.md) bagian Anti-AI Slop).

### Admin doc tool — [teams/t4_admin.py](../teams/t4_admin.py)
- Excel bisa render chart (`_render_chart` + `openpyxl.drawing.image`) di level sheet maupun dokumen.
- Footer PDF tidak lagi muncul di cover page.
- `DataAnalysisTool` punya fallback cari file di `OUTPUT_DIR` kalau path relatif meleset.

### Furniture QC — [core/furniture_qc.py:532](../core/furniture_qc.py#L532)
- Render bbox/label diganti dari `PIL.ImageDraw` manual ke `supervision` (Roboflow) `BoxAnnotator` + `LabelAnnotator`. Warna dipetakan per severity (critical/warning/info). Dependensi baru: `supervision>=0.19.0` di [requirements.txt](../requirements.txt).

### Intel team — [teams/t5_intel.py](../teams/t5_intel.py)
- `XScraper` diganti `XReachTool`, tambah `JinaReaderTool` (keduanya dari [tools/agent_reach_tool.py](../tools/agent_reach_tool.py), memakai package `agent_reach` yang sudah di-pip-install ke `bima_env`).

### Governance / docs
- [.clauderules](../.clauderules) baru — workflow plan → approval → code.
- [CLAUDE.md](../CLAUDE.md) baru — panduan dev BIMA_CORE.
- `error_solutions.md` & `implementation_plan.md` dipindah ke `docs/`.
- [.kilo/skills/agent-md-refactor/](../.kilo/skills/agent-md-refactor/) — skill pihak ketiga (toolkit `softaworks/agent-toolkit`), ikut ke-stage. **Perlu konfirmasi apakah memang mau di-vendor di repo ini** (lihat §4).

### Test baru
- [tests/test_admin.py](../tests/test_admin.py) — 3 test (fallback path, Excel chart, PDF footer). **Sudah dijalankan: 3/3 PASS.**
- [tests/test_reviser.py](../tests/test_reviser.py) — smoke test manual `apply_smart_revision` (lihat catatan di §4).

---

## 2. Status verifikasi

Semua dijalankan langsung di WSL (`bima_env`), bukan cuma baca diff:

| Cek | Hasil |
| --- | --- |
| Import semua modul tersentuh (t3_arsip, t5_intel, arsip_commands, deslop_tool, manager, threads_commands, llm_config) | ✅ bersih |
| `_render_markup_per_page` (furniture_qc) dengan gambar dummy + 2 issue (critical & warning) | ✅ hasilkan PNG valid |
| `pytest tests/test_admin.py` | ✅ 3 passed |
| `pytest tests/ --collect-only` (seluruh suite) | ✅ 124 tests, tanpa error collect/import |
| `supervision` di `bima_env` | ✅ v0.28.0, signature `BoxAnnotator`/`LabelAnnotator`/`ColorPalette` kompatibel dengan kode baru |

Kesimpulan: **tidak ada bug logika di kode**. Masalah yang ditemukan murni soal git state / infra.

---

## 3. Bug yang sudah dibetulkan (sesi ini)

1. **Gitlink `agent-reach` rusak** — `agent-reach` ter-`git add` sebagai submodule (mode `160000`, commit `...dc0ca-dirty`) padahal **tidak ada `.gitmodules`**. Kalau ke-commit, clone baru dapat folder kosong dan git tidak tahu URL-nya. `agent-reach/` itu clone lokal build tool (github.com/Panniantong/agent-reach, sudah di-pip-install ke `bima_env` — lihat [error_solutions.md](error_solutions.md) Log 11), bukan source BIMA_CORE.
   - **Fix**: tambah `agent-reach/` ke [.gitignore](../.gitignore) + `git rm --cached -f agent-reach`. Folder working tree utuh, sekarang untracked & ignored.

2. **Exec bit ke-strip di 11 shell script** (`100755` → `100644` di index) — file asli di WSL sebenarnya tetap `755`; hanya index yang salah (kemungkinan artefak stage dari git Windows). Kalau ke-commit, script yang dipanggil langsung (bukan via `bash x.sh`) bakal gagal "Permission denied".
   - **Fix**: `git update-index --chmod=+x` pada `mcp_server/run.sh`, `scripts/{fetch_fonts,install_gh,install_mcp_manifest}.sh`, `start_tunnel.sh`, dan 5 script di `tools/last30days-skill/`. Index balik ke `100755`.

---

## 4. Item terbuka — butuh keputusan Bima

1. **Perubahan Threads belum di-`git add`** — [core/threads_commands.py](../core/threads_commands.py), [core/threads_scheduler.py](../core/threads_scheduler.py), [core/scientific_facts.json](../core/scientific_facts.json), dan tambahan di [docs/error_solutions.md](error_solutions.md) masih di working tree. **Kalau commit sekarang tanpa stage ulang, perubahan Threads yang paling substansial akan ketinggalan.**

2. **[tests/test_reviser.py](../tests/test_reviser.py) bukan test pytest** — isinya `async def main()` yang dijalankan via `asyncio.run()`, tidak ada fungsi `test_*`, jadi pytest collect 0 item dari file ini. Selain itu ia memanggil LLM asli (non-mock), jadi memang smoke-test manual — bukan untuk CI. Namanya di folder `tests/` bikin seolah sudah ter-cover padahal tidak. Opsi: rename jadi `scripts/smoke_reviser.py`, atau biarkan tapi catat di sini.

3. **[.kilo/skills/agent-md-refactor/](../.kilo/skills/agent-md-refactor/)** — skill pihak ketiga (referensi "Kilo Code", bukan Claude/Codex) ikut ke-stage. Konfirmasi: memang mau di-vendor di repo, atau kebawa tidak sengaja?

4. **`CLAUDE.md` ke-stage padahal `.gitignore` punya `claude.md`** — filesystem WSL case-sensitive, jadi `CLAUDE.md` ≠ `claude.md` dan lolos ignore. Kalau `CLAUDE.md` memang mau dilacak, aman. Kalau tidak, sesuaikan pola gitignore.

5. **Folder untracked lain**: `AI_sosmed/` (80 file, punya `.git` sendiri — nested repo, sesuai memori: repo terpisah `Ai-sosmed`), `ui_sidebar/` (9 file), `docs/superpowers/` (1 file). Belum di-add — pastikan `AI_sosmed/` tidak sengaja ke-commit sebagai nested repo.

---

## 5. Cara lanjut / verifikasi ulang

```bash
# Semua dari WSL:
cd /home/bima_lucian/BIMA_CORE && source bima_env/bin/activate

# Test suite yang relevan
bima_env/bin/pytest tests/test_admin.py tests/test_qc.py -v

# Syntax + import cek cepat
bima_env/bin/python -c "import teams.t5_intel, teams.t3_arsip, core.furniture_qc; print('OK')"

# Sebelum commit: stage ulang perubahan Threads yang masih di working tree
git add core/threads_commands.py core/threads_scheduler.py core/scientific_facts.json docs/error_solutions.md
```

Sebelum `git commit`: jalankan `pytest` (aturan [CLAUDE.md](../CLAUDE.md) §3) dan pastikan §4 sudah diputuskan.
