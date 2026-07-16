# Audit Menyeluruh BIMA_CORE — Bug & Miss Logic (2026-07-12)

Read-only audit seluruh codebase (core orchestration, teams/, tools/, whatsapp+dashboard+mcp_server, services/+scripts/). Nested/vendored repo (AI_sosmed, agent-reach, tools/bima_search, tools/last30days-skill, node_modules, venv) di luar scope. Empat temuan paling severe sudah diverifikasi manual di line yang tepat.

Legenda severity: **P0** = security/data-loss aktif, **P1** = bug fungsional serius, **P2** = edge-case/leak lambat, **P3** = minor/konsistensi.

---

## Tema besar #1 — Path traversal berulang (LLM/user mengontrol nama/path file)

`pathlib`: `Path(base) / rhs` **membuang base** kalau `rhs` absolut, dan `../` lolos karena cuma dicek `.exists()`, bukan containment. Pola aman sudah ADA di repo (`teams/t7_seniman.py:14` `_safe_filename()`, `teams/t3_arsip.py:624-628` `relative_to(vault_dir)`) tapi belum diadopsi di banyak tempat.

- **P0 `teams/t4_admin/excel_tool.py:118`, `pdf_tool.py:601`, `word_tool.py:493`** — `filename` dari `data.get('filename')` LLM langsung di-join ke `OUTPUT_DIR` tanpa sanitasi. `"filename": "../../../../home/bima_lucian/.bashrc"` menimpa file arbitrer. **Ketiganya file yang lagi diedit uncommitted** — regresi gap vs sisa repo. (Verified persis.)
- **P0 `tools/code_visualizer.py:35`** — `(base_path / target_dir).resolve()` dengan `target_dir` LLM-controlled. `target_dir="/etc"` men-scan + baca file di mana saja, lalu publish nama/isi ke HTML di `outputs/`. (Verified persis.)
- **P0 `tools/image_gen_tool.py:66`** — `reference_image_paths` LLM-controlled dibuka `open(path,"rb")`, base64, dikirim ke OpenRouter tanpa allowlist. `reference_image_paths=[".env"]` → isi `.env` ter-exfiltrate ke API eksternal.
- **P1 `teams/t8_mekanik.py:245` (FileSaverTool)** — `OUTPUT_DIR / filename` tanpa cek; walau ada `check_permission_sync`, prompt approval cuma tampilkan string mentah, bukan path resolusi absolut → Bima bisa approve `"../../.env"` tanpa sadar.
- **P1 `teams/t4_admin/data_analysis_tool.py:37-44`** — `filepath` LLM langsung ke `pd.read_csv/read_excel`; fallback ke OUTPUT_DIR cuma kalau path mentah gak ada → bisa baca & `df.describe()` file CSV/Excel apa pun di disk.
- **P1 `teams/t2_visual.py:538-545`, `teams/t7_html_templates.py:217-226`** — `section["image_path"]` LLM di-base64-embed ke PDF/HTML hanya dengan whitelist ekstensi, tanpa confinement path → vektor exfiltration via dokumen.

## Tema besar #2 — Isolasi state antar-user bocor (multi-user WhatsApp/Discord)

- **P0 `core/langgraph_engine.py:343,360`** + **`whatsapp/index.js:427-434`** + **`core/wa_server.py:31-34,123-129`** — WA bridge dukung banyak owner ter-whitelist (`!wl`, `getEffectiveOwners()`), tapi `sendToAnisa` gak kirim identitas pengirim, `ChatRequest` gak punya field user-id, jadi `thread_id` selalu konstan `"anon_whatsapp"` untuk **semua** pengirim WA. Dua nomor berbeda → orang kedua melanjutkan checkpoint LangGraph orang pertama (di `memory/checkpoints.db`) → riwayat percakapan bocor antar orang. (Verified: line 343 & 360 persis.)
- **P1 `core/discord_bot.py:536`** — `source_channel="discord"` literal, bukan channel id nyata → `thread_id` sama untuk semua channel/DM user itu. Kombinasi dengan `_progress_callbacks` keyed by `thread_id` (`core/langgraph_nodes/state.py:12-23`): dua pesan concurrent dari user sama saling menimpa callback, progress edit nyasar, dan checkpoint AsyncSqliteSaver bisa interleaved.
- **P2 `core/langgraph_nodes/intent_classifier.py:178`** — fast-path canvas/PDF-iterative digate `discord_user_id`; karena WA gak pernah set itu, user WA gak bisa resume sesi canvas aktif (konsekuensi dari P0 di atas).

## Tema besar #3 — XSS & korupsi output chat

- **P0 (XSS) `dashboard/guild-panels.jsx:276`** — `dangerouslySetInnerHTML={{__html: l.text}}` tanpa escape apa pun; `l.text` dibangun dari string mentah command_response/error backend (`guild-app.jsx:171`, `guild-panels.jsx:79`). Respons LangGraph berisi `<img src=x onerror=...>` tereksekusi di DOM siapa pun yang buka dashboard. Bandingkan `ChatPanel.formatMd()` (`guild-panels.jsx:169-176`) yang benar escape — path activity-log tidak. (Verified persis.)
- **P1 `whatsapp/index.js:380-392` (sanitizer, di diff uncommitted)** — konversi bold/italic/underscore jalan SEBELUM strip inline `` `code` ``, jadi isi inline-code gak dilindungi (beda dari fenced ```). `` `__init__` `` → `*init*`, `` `if __name__=='__main__':` `` → `if *name*=='*main*':`. Untuk bot coding-assistant ini sering & high-visibility. Plus: fence tak-tertutup gak dikenali sebagai code (`split(/(```[\s\S]*?```)/g)` butuh pasangan) — inkonsisten dgn `smartChunks()` (`index.js:397-420`). Plus: regex link `\((https?:\/\/[^\s)]+)\)` motong URL ber-`)` (mis. Wikipedia `..._(bar)`).
- **P1 (CLAUDE.md violation) `core/discord_bot.py:591,423`, `core/saham_commands.py:372`, `core/arsip_commands.py:54`** — `str(exception)` mentah diforward ke chat Discord. Cross-cutting: hampir semua tool `t4_admin/t5/t6/t8/t9` pakai `except Exception as e: return f"FAILED|{e}"` yang membocorkan traceback/path lokal ke output chat via CrewAI. CLAUDE.md eksplisit larang ini.

## Bug fungsional & logic gap lain

- **P1 `scripts/setup_threads.py:118-137`** — `long_token = res_data.get('access_token')` disimpan ke `.env` tanpa cek None; kalau Meta balas error payload, script cetak "SETUP BERHASIL!" tapi tulis literal `THREADS_ACCESS_TOKEN=None`, diam-diam matiin semua posting Threads.
- **P1 `tools/slide_generator.py:22,45`** — `bypass_preview: bool` adalah field publik `SlideGeneratorInput`, kebuka ke argumen tool-call LLM → agent bisa set `bypass_preview=True` di call awal dan skip approval Discord Bima. Approval dideklarasikan caller, bukan dipaksa tool.
- **P1 `tools/cloud_backup.py`** — `BACKUP_DIRS` sudah di-ignore `.gitignore` root → `git add` no-op diam tapi script cetak "✅ Commit berhasil"; sementara `origin` = repo dev live (`B.I.M.A-CORE.git`), bukan repo `-backup`, jadi file non-ignored (`main.py`, `teams/`, dst) ke-commit & `push origin main` unattended via cron — bypass review, langgar aturan destructive-needs-approval.
- **P1 `services/browser/worker.py` + `tools/browser_use_tool.py:31`** — `MAX_STEPS×STEP_TIMEOUT` = up to 1200s tapi `BROWSER_WORKER_TIMEOUT=900`; task lambat kena SIGKILL sebelum `browser_use` `finally: close()` jalan → Chromium orphan + lock profil persisten. Gak ada process-group handling.
- **P1 `tools/sherlock_tool.py:34`** — ternary cek truthiness `username` ASLI bukan yang di-strip; `_run("   ")` → `"   "` truthy → strip → `""` → `.split()[0]` → `IndexError` uncaught.
- **P2 `services/browser/worker.py:104-111`** — `ok:True` kalau `final_result()` non-kosong, gak cek `is_successful()`/`is_done()`; task habis MAX_STEPS mid-jalan bisa lapor `SUCCESS|...` padahal belum selesai.
- **P2 `services/browser/worker.py:85-87`** — `MARKETPLACE_PROFILE_DIR` dipakai ulang tanpa lock; dua request marketplace concurrent race di singleton profile lock Chromium.
- **P2 `teams/t4_admin/pdf_tool.py:315-329`** — `_body_start_page` untuk footer Roman/Arab akademik asumsikan cover/abstract/TOC masing-masing 1 halaman; abstract/TOC panjang yang auto-paginate → numeral salah.
- **P2 `teams/t6_lifestyle.py:119-159` (ScheduleManagerTool)** — cuma ada `add/list/clear`, gak ada delete per-item; "hapus jadwal meeting besok" bisa ke-map ke `clear|` (hapus SEMUA jadwal) → data loss dari satu misparse.
- **P2 `tools/file_organizer.py:40-64`** — `shutil.move` semua file `outputs/` tanpa filter umur/try-per-file; race dgn tool yang baru nulis path lalu bot baca untuk kirim → path 404; satu move gagal (file locked) → abort seluruh batch unhandled.
- **P2 `tools/diagram_tool.py:144`** — `diagram_{ts}.html` timestamp detik-integer tanpa hash konten (beda dari image/video_gen yang hash prompt); dua call di detik sama saling timpa. Test `tests/test_diagram_tool.py` cuma cover happy-path + empty-input, gak cover collision/write-fail/regresi `html.escape()`.
- **P2 `teams/t4_admin/chart_utils.py:36-61`** — `plt.subplots()` dibuat sebelum validasi `chart_type`/`datasets`; input jelek raise sebelum `plt.close(fig)` (line 76) → leak figure matplotlib per call gagal.
- **P2 `teams/t2_visual.py:255` (ExcelReader)** — `wb.close()` cuma di success path; exception saat iterasi sheet → workbook openpyxl gak ketutup.
- **P3 `core/langgraph_nodes/manager.py:112`** — prompt "pilih SATU dari 20 pilihan" padahal menu 22 opsi (diff uncommitted nambah combo).
- **P3 `core/langgraph_engine.py:269-304`** — cache graph/DB keyed `id(asyncio.get_running_loop())`; `id()` bisa reuse setelah loop GC → potensi collision dgn entry stale (koneksi closed).
- **P3 `core/gen_rate_limit.py`** — `sqlite3` sinkron dipanggil dari async path (`discord_bot.py:509-513`, `CostTracker.on_llm_end`) tanpa `asyncio.to_thread` → block event loop sesaat per call.
- **P3 `scripts/setup_threads.py`, `scripts/test_post_image.py`** — `Path('.env')` relatif ke cwd; jalan dari luar root baca/tulis `.env` lain diam-diam.
- **P3 `services/agentmemory/package.json`** — `"start":"agentmemory"` tanpa `--tools core` (ecosystem.config.js pakai `--tools core`); script out of sync, praktis unused.

---

## Confirmed non-bug (biar gak diutak lagi)

- Diff uncommitted `word_tool.py`/`pdf_tool.py`/`excel_tool.py` = bugfix legit (swap Roman/Arab, footer dedup, indent-cell, kv-table width, OfficeCLI column-offset), bukan regresi. **Tapi** path-traversal di atas tetap perlu ditambal.
- Fenced ```code``` di sanitizer WA memang benar dilindungi (split-and-skip untuk pasangan matched).
- `mcp_server/*` (server.py, tools_registry.py, manifest.yaml): validasi input, clamp range, exception-wrap ada; gak ada schema drift.
- `config_mcp.json` valid JSON; semua `attach_to` cocok `core/agent_registry.py`.
- `default_llm` sekarang eager (bukan lazy) di `llm_config.py:87`; AsyncSqliteSaver lifecycle ada per-loop cache + `shutdown_engine()`; OpenRouter CostTracker terpasang & fungsional. (3 concern "ANISA v3" lama sudah beres.)
- `services/voice` sengaja tanpa `.py` (dijalankan `-m` via venv terisolasi); `.clauderules`/`Rules for agent.md` = stub deprecated nunjuk CLAUDE.md, konsisten by design.

## Rekomendasi urutan tambal

1. **P0 path traversal** — tambahkan satu helper `_safe_output_path(name)` (adopsi pola `t7_seniman._safe_filename`) dan pakai di semua titik OUTPUT_DIR join (t4_admin ×3, code_visualizer, t8_mekanik, data_analysis, t2_visual, t7_html_templates, image_gen reference paths).
2. **P0 thread_id leak WA** — teruskan sender id dari `whatsapp/index.js` → `ChatRequest` → `run_langgraph_engine(discord_user_id=...)`.
3. **P0 XSS dashboard** — ganti `dangerouslySetInnerHTML` di `guild-panels.jsx:276` dengan text node, atau escape lewat `formatMd()`.
4. **P1 sanitizer WA inline-code**, **slide_generator bypass_preview**, **cloud_backup auto-push**, **setup_threads None token**, **browser worker timeout/orphan**.
