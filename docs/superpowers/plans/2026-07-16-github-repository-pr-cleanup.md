# GitHub Repository and Pull Request Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan inline. Do not dispatch subagents. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Membuat PR #7 dan #8 bebas konflik dan CI hijau, lalu squash-merge keduanya ke `main` secara berurutan tanpa menyentuh perubahan lokal Bima.

**Architecture:** Semua perubahan dikerjakan di dua git worktree terisolasi karena checkout utama sedang memiliki banyak perubahan lokal. PR #7 di-squash-merge lebih dulu; `main` terbaru kemudian digabungkan ke PR #8, konflik antarkedua fitur diselesaikan, test lokal dan CI diulang, lalu PR #8 di-squash-merge. Tidak ada force-push atau direct-push ke `main`.

**Tech Stack:** Git worktree, GitHub CLI/App, Python 3.12, pytest, Node.js test runner, GitHub Actions.

---

## Temuan EXPLORE

- PR #8 `codex/package-a-b-integration`: 3 commit, 36 file menurut PR API, judul generik, body kosong, status `CONFLICTING`, CI gagal.
- PR #7 `Audit-menager-anisa`: 4 commit, 24 file, draft, status `CONFLICTING`, CI gagal.
- Akar CI kedua PR sama: `tests/test_admin.py::test_excel_generator_with_charts` menjalankan OfficeCLI asli yang tidak tersedia di runner; hasil aktual `FAILED|OfficeCLI belum terinstall...`.
- PR #8 salah-track `.codex-remote-attachments/.../1-Photo-1.jpg` dan gitlink `databasement` tanpa `.gitmodules`; gitlink menunjuk clone lokal `David-Crty/databasement`.
- Konflik PR #8: `AGENTS.md`, `CLAUDE.md`, `error_solutions.md`, `teams/t8_mekanik.py`, `whatsapp/index.js`.
- Konflik PR #7: `core/discord_bot.py`, `core/langgraph_engine.py`, `core/langgraph_nodes/manager.py`, `error_solutions.md`, `whatsapp/index.js`.
- Branch remote `claude/debug-git-push-3nSWo`, `feature/last30days`, dan `fix/audit-p0-security` sudah menjadi ancestor `origin/main`.
- Repo masih tanpa description/topics, `delete_branch_on_merge=false`, dan `main` belum memakai branch protection.

## Batas Otorisasi PLAN

Persetujuan PLAN ini mengizinkan:

1. Push normal tanpa `--force` ke `codex/package-a-b-integration` dan `Audit-menager-anisa`.
2. Menghapus dua path salah-track dari PR #8: `.codex-remote-attachments/` dan gitlink `databasement`.
3. Menghapus tiga branch remote yang sudah merged: `claude/debug-git-push-3nSWo`, `feature/last30days`, `fix/audit-p0-security`.
4. Mengubah description, topics, dan `delete_branch_on_merge` repository.
5. Mengubah PR #7 dari draft menjadi ready hanya setelah test lokal dan CI hijau.

Persetujuan PLAN awal tidak mengizinkan merge/close PR. Revisi scope `LANJUT PR` menambahkan izin untuk squash-merge PR #7 lalu PR #8, menyinkronkan dan push normal PR #8 setelah merge #7, serta menghapus dua worktree cleanup setelah seluruh verifikasi selesai.

PLAN tetap tidak mengizinkan force-push, direct-push ke `main`, menghapus local branch dengan `git branch -D`, memasang dependency, mengubah `.env`, mengubah workflow CI, atau mengaktifkan branch protection.

### Task 1: Buat Workspace Terisolasi dan Simpan Baseline

**Files:**
- Tidak ada file tracked yang diubah.
- Worktree lokal: `.worktrees/pr8-cleanup`
- Worktree lokal: `.worktrees/pr7-cleanup`

- [x] **Step 1: Pastikan checkout utama bukan linked worktree dan catat status awal**

```bash
git rev-parse --git-dir
git rev-parse --git-common-dir
git branch --show-current
git status --short --branch
```

Expected: branch utama kerja tetap `codex/package-a-b-integration`; perubahan lokal terlihat dan tidak disentuh.

- [x] **Step 2: Pastikan lokasi worktree di-ignore**

```bash
git check-ignore -v .worktrees/pr8-cleanup
git check-ignore -v .worktrees/pr7-cleanup
```

Expected: kedua path cocok dengan rule `.worktrees/`.

- [x] **Step 3: Buat dua worktree dari remote head masing-masing PR**

```bash
git worktree add .worktrees/pr8-cleanup -b codex/pr8-cleanup origin/codex/package-a-b-integration
git worktree add .worktrees/pr7-cleanup -b codex/pr7-cleanup origin/Audit-menager-anisa
```

Expected: dua worktree bersih, checkout utama tidak berubah.

- [x] **Step 4: Reproduksi baseline CI di kedua worktree memakai venv yang sudah ada**

```bash
cd .worktrees/pr8-cleanup
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest tests/test_admin.py::test_excel_generator_with_charts -q

cd ../pr7-cleanup
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest tests/test_admin.py::test_excel_generator_with_charts -q
```

Expected di mesin tanpa OfficeCLI: gagal dengan pesan OfficeCLI tidak ditemukan. Persetujuan PLAN ini sekaligus mengizinkan melanjutkan dari baseline gagal yang akar masalahnya sudah dibuktikan oleh dua log GitHub Actions.

### Task 2: Isolasi OfficeCLI pada Unit Test Kedua PR

**Files:**
- Modify: `.worktrees/pr8-cleanup/tests/test_admin.py`
- Modify: `.worktrees/pr7-cleanup/tests/test_admin.py`

- [x] **Step 1: Tambahkan import dan fake subprocess yang membuat file Excel sementara**

Gunakan bentuk yang sama pada kedua worktree:

```python
import subprocess

import teams.t4_admin.excel_tool as excel_module


def _fake_officecli_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
    command = args[1]
    if command == "create":
        Path(args[2]).touch()
        return subprocess.CompletedProcess(args, 0, "", "")
    if command == "batch":
        payload = {"data": {"summary": {"failed": 0}, "results": []}}
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
    return subprocess.CompletedProcess(args, 0, "", "")
```

- [x] **Step 2: Ubah test agar tidak bergantung pada binary host**

```python
def test_excel_generator_with_charts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(excel_module, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(excel_module, "_officecli_bin", lambda: "/usr/bin/officecli")
    monkeypatch.setattr(excel_module.subprocess, "run", _fake_officecli_run)
    # data test yang sudah ada tetap dipakai tanpa perubahan
```

- [x] **Step 3: Jalankan targeted test di kedua worktree**

```bash
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest tests/test_admin.py::test_excel_generator_with_charts -q
```

Expected: `1 passed` pada masing-masing worktree tanpa menginstal OfficeCLI.

- [x] **Step 4: Commit perbaikan test secara terpisah pada tiap PR**

```bash
git add tests/test_admin.py
git commit -m "test: isolate OfficeCLI Excel generation"
```

Expected: satu commit baru di tiap local cleanup branch.

### Task 3: Bersihkan dan Sinkronkan PR #8

**Files:**
- Modify: `.worktrees/pr8-cleanup/AGENTS.md`
- Modify: `.worktrees/pr8-cleanup/CLAUDE.md`
- Modify: `.worktrees/pr8-cleanup/error_solutions.md`
- Modify: `.worktrees/pr8-cleanup/teams/t8_mekanik.py`
- Modify: `.worktrees/pr8-cleanup/whatsapp/index.js`
- Modify: `.worktrees/pr8-cleanup/.gitignore`
- Delete: `.worktrees/pr8-cleanup/.codex-remote-attachments/019f6472-70dd-7943-84ec-1aa840ef1e1f/6e0a711f-edaa-4ef6-b6d6-b2b37909d113/1-Photo-1.jpg`
- Delete gitlink: `.worktrees/pr8-cleanup/databasement`

- [x] **Step 1: Merge `origin/main` tanpa rebase atau force-push**

```bash
git merge --no-edit origin/main
```

Expected: lima conflict yang sudah teridentifikasi.

- [x] **Step 2: Resolusi konflik dengan mempertahankan kedua sisi yang fungsional**

- `AGENTS.md` dan `CLAUDE.md`: pertahankan aturan satu PLAN, EXPLORE→PLAN→CODE→VERIFY, minimal diff, approval operasi destruktif, dan ringkasan maksimal lima baris; hilangkan duplikasi kalimat.
- `error_solutions.md`: gabungkan log dari `main` dan PR #8 secara append-only; jangan hapus nomor log atau solusi lama.
- `teams/t8_mekanik.py`: pertahankan hardening security dari `main` dan registrasi/pemakaian `StrixSecurityScannerTool` dari PR #8.
- `whatsapp/index.js`: pertahankan hardening input/message dari `main` dan delegasi filter ke `message_filter.js` dari PR #8.

- [x] **Step 3: Hapus artefak salah-track dan cegah terulang**

```bash
git rm .codex-remote-attachments/019f6472-70dd-7943-84ec-1aa840ef1e1f/6e0a711f-edaa-4ef6-b6d6-b2b37909d113/1-Photo-1.jpg
git rm databasement
```

Tambahkan ke `.gitignore`:

```gitignore
# Codex chat attachments and local tool clones
.codex-remote-attachments/
databasement/
```

- [x] **Step 4: Catat error eksplorasi yang belum tercakup**

Tambahkan log baru ke `error_solutions.md` untuk:

1. `git for-each-ref --format=%(...)` gagal saat nested PowerShell→WSL; solusi: jalankan format kompleks langsung di shell WSL atau pecah menjadi command sederhana.
2. GitHub branch-protection API mengembalikan 404 saat branch memang tidak diproteksi; solusi: perlakukan 404 sebagai state `not protected`, bukan kegagalan autentikasi.

Regex alternation PowerShell→WSL tidak ditulis ulang karena sudah tercakup oleh Log 82.

- [x] **Step 5: Selesaikan merge commit**

```bash
git add AGENTS.md CLAUDE.md error_solutions.md teams/t8_mekanik.py whatsapp/index.js .gitignore
git commit
```

Expected: merge commit berisi resolusi dan penghapusan artefak, tanpa file lain.

- [x] **Step 6: Verifikasi PR #8**

```bash
node --check whatsapp/index.js
node --test whatsapp/test/message_filter.test.js
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest tests/test_admin.py tests/test_discord_startup_embed.py tests/test_duckdb_tool.py tests/test_healthcheck.py tests/test_obsidian_formats.py tests/test_strix_scanner.py -q
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest -q
git diff --check origin/codex/package-a-b-integration..HEAD
git ls-files -s databasement .codex-remote-attachments
git status --short
```

Expected: syntax/test lulus, full pytest nol failure, `git diff --check` kosong, dua path artefak tidak terdaftar, status bersih.

- [x] **Step 7: Push fast-forward ke branch PR #8**

```bash
git push origin HEAD:codex/package-a-b-integration
```

Expected: push sukses tanpa `--force`.

- [x] **Step 8: Rapikan metadata PR #8 lewat GitHub App**

Title:

```text
feat: integrate Obsidian, DuckDB, Strix, and messaging hardening
```

Body harus memuat ringkasan empat kelompok perubahan, daftar verifikasi aktual, catatan penghapusan attachment/gitlink, dan tidak mengklaim CI hijau sebelum check selesai.

### Task 4: Sinkronkan dan Siapkan PR #7

**Files:**
- Modify: `.worktrees/pr7-cleanup/core/discord_bot.py`
- Modify: `.worktrees/pr7-cleanup/core/langgraph_engine.py`
- Modify: `.worktrees/pr7-cleanup/core/langgraph_nodes/manager.py`
- Modify: `.worktrees/pr7-cleanup/error_solutions.md`
- Modify: `.worktrees/pr7-cleanup/whatsapp/index.js`

- [x] **Step 1: Merge `origin/main` tanpa rebase atau force-push**

```bash
git merge --no-edit origin/main
```

Expected: lima conflict yang sudah teridentifikasi.

- [x] **Step 2: Resolusi konflik secara semantik**

- `core/discord_bot.py`: pertahankan security/error hardening dari `main` serta status-node/progress behavior PR #7.
- `core/langgraph_engine.py`: pertahankan state/runtime hardening dari `main` serta event streaming yang diperlukan progress preview.
- `core/langgraph_nodes/manager.py`: pertahankan anti-slop dan public-output hardening dari `main`; route internal tidak boleh bocor ke user.
- `whatsapp/index.js`: pertahankan validasi/filter dari `main`; satu pesan progress harus diedit menjadi hasil final/error tanpa mengirim duplikat.
- `error_solutions.md`: gabungkan append-only dan masukkan dua log eksplorasi yang sama seperti PR #8 agar branch mana pun yang merge lebih dulu membawa dokumentasi error.

- [x] **Step 3: Selesaikan merge commit**

```bash
git add core/discord_bot.py core/langgraph_engine.py core/langgraph_nodes/manager.py error_solutions.md whatsapp/index.js
git commit
```

- [x] **Step 4: Verifikasi PR #7**

```bash
node --check whatsapp/index.js
node --test whatsapp/progress_message.test.js
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest tests/test_admin.py::test_excel_generator_with_charts tests/test_agent_registry.py tests/test_manager_routing.py tests/test_mcp_hardening.py -q
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest -q
git diff --check origin/Audit-menager-anisa..HEAD
git status --short
```

Expected: seluruh test lulus dan status bersih.

- [x] **Step 5: Push fast-forward ke branch PR #7**

```bash
git push origin HEAD:Audit-menager-anisa
```

- [x] **Step 6: Rapikan metadata PR #7 lewat GitHub App**

Title:

```text
fix: harden manager routing and add WhatsApp progress preview
```

Body diperbarui dengan hasil verifikasi aktual dan status conflict resolution. PR tetap draft sampai CI GitHub hijau.

### Task 5: Rapikan Metadata dan Branch Repository GitHub

**Files:**
- Tidak ada file lokal yang diubah.
- Repository settings: `Luciansvon/B.I.M.A-CORE`

- [x] **Step 1: Set metadata repository**

Description:

```text
Anisa: multi-agent AI assistant for Discord, WhatsApp, and REST, orchestrated with LangGraph and CrewAI.
```

Topics:

```text
python fastapi langgraph crewai discord-bot whatsapp-bot multi-agent openrouter wsl
```

- [x] **Step 2: Aktifkan penghapusan branch otomatis setelah PR merge**

Set `delete_branch_on_merge=true`. Branch protection tetap tidak diubah karena itu akan mengubah workflow solo-dev dan tidak dibutuhkan untuk cleanup ini.

- [x] **Step 3: Verifikasi ulang bahwa branch target benar-benar merged**

```bash
git fetch origin
git branch -r --merged origin/main
```

Expected: ketiga branch target masih tercantum.

- [x] **Step 4: Hapus hanya tiga branch remote yang sudah merged**

```bash
git push origin --delete claude/debug-git-push-3nSWo
git push origin --delete feature/last30days
git push origin --delete fix/audit-p0-security
```

Jangan hapus `codex/package-a-b-integration`, `Audit-menager-anisa`, atau branch lain yang belum merged.

### Task 6: VERIFY GitHub dan Jaga Working Tree Bima

**Files:**
- Tidak ada file baru.

- [x] **Step 1: Tunggu check terbaru PR #8 dan PR #7**

```bash
gh pr checks 8 --watch --interval 10
gh pr checks 7 --watch --interval 10
```

Expected: check `pytest` sukses pada head SHA terbaru.

- [x] **Step 2: Jika CI hijau, tandai PR #7 ready for review**

Gunakan GitHub App untuk mengubah PR #7 dari draft ke ready. PR #8 sudah ready dan tidak diubah state-nya.

- [x] **Step 3: Audit akhir GitHub**

```bash
gh pr view 8 --json title,body,isDraft,mergeable,mergeStateStatus,statusCheckRollup,url
gh pr view 7 --json title,body,isDraft,mergeable,mergeStateStatus,statusCheckRollup,url
gh api repos/Luciansvon/B.I.M.A-CORE
gh api repos/Luciansvon/B.I.M.A-CORE/branches --paginate
```

Expected: dua PR tidak konflik, CI hijau, metadata terisi, auto-delete aktif, tiga branch merged sudah hilang.

- [x] **Step 4: Pastikan checkout utama tetap utuh**

```bash
cd /home/bima_lucian/BIMA_CORE
git branch --show-current
git status --short --branch
```

Expected: branch dan seluruh perubahan lokal awal tetap ada; tidak ada file user yang di-stage/commit.

- [x] **Step 5: Laporkan hasil faktual maksimal lima baris**

Cantumkan link PR #7 dan #8, hasil CI, branch yang dihapus, metadata yang diubah, serta pekerjaan yang sengaja tidak dilakukan (merge/close PR dan branch protection).

## Revisi Scope: Lanjut Merge PR

Revisi ini dibuat setelah Bima meminta `LANJUT PR`. Status saat revisi: PR #7 dan #8 `OPEN`, `MERGEABLE`, `CLEAN`, bukan draft, dan masing-masing memiliki dua check CI sukses.

### Task 7: Squash-Merge PR #7

**Files:**
- Tidak ada file lokal yang diubah.
- GitHub PR: `Luciansvon/B.I.M.A-CORE#7`

- [x] **Step 1: Verifikasi head dan check PR #7 tepat sebelum merge**

```bash
/home/bima_lucian/.local/bin/gh pr view 7 --repo Luciansvon/B.I.M.A-CORE \
  --json headRefOid,isDraft,mergeable,mergeStateStatus,statusCheckRollup
```

Expected: head `bad511120f35bebdb450356de03e48f90d0871fa`, `isDraft=false`, `MERGEABLE`, `CLEAN`, seluruh check `SUCCESS`.

- [x] **Step 2: Squash-merge PR #7**

```bash
/home/bima_lucian/.local/bin/gh pr merge 7 --repo Luciansvon/B.I.M.A-CORE --squash
```

Expected: PR #7 berstatus merged. Setting `delete_branch_on_merge=true` menghapus remote branch `Audit-menager-anisa`.

- [x] **Step 3: Fetch `main` baru dan verifikasi merge**

```bash
git fetch origin
/home/bima_lucian/.local/bin/gh pr view 7 --repo Luciansvon/B.I.M.A-CORE \
  --json state,mergedAt,mergeCommit
```

Expected: `state=MERGED`, `mergedAt` terisi, `origin/main` maju ke squash commit PR #7.

### Task 8: Sinkronkan Ulang PR #8 terhadap Hasil PR #7

**Conflict aktual dari simulasi `git merge-tree`:**
- Modify: `.worktrees/pr8-cleanup/whatsapp/index.js`
- Modify: `.worktrees/pr8-cleanup/error_solutions.md`

- [x] **Step 1: Merge `origin/main` terbaru ke worktree PR #8**

```bash
cd /home/bima_lucian/BIMA_CORE/.worktrees/pr8-cleanup
git merge --no-edit origin/main
```

Expected: conflict hanya pada `whatsapp/index.js` dan `error_solutions.md`; `core/discord_bot.py` auto-merge.

- [x] **Step 2: Pertahankan seluruh behavior gabungan**

- `whatsapp/index.js`: gunakan `shouldHandleMessage`, `sanitizeForWhatsApp`, dan `updateProgressMessage`; hasil final disanitasi lalu mengedit pesan progress yang sama.
- `error_solutions.md`: gabungkan append-only, nomor log unik, dan catat semua error/solusi selama revisi merge.
- Setelah merge, verifikasi `core/discord_bot.py` tetap memuat image-only attachment policy dan `add_session`, serta `tests/test_admin.py` tetap memuat fake OfficeCLI.

- [x] **Step 3: Commit resolusi merge tanpa perubahan di luar konflik**

```bash
git add whatsapp/index.js error_solutions.md
git commit --no-edit
```

Jika suatu file tidak conflict/tidak berubah, jangan dipaksa masuk staging.

- [x] **Step 4: Jalankan verifikasi gabungan**

```bash
node --check whatsapp/index.js
node --test whatsapp/test/message_filter.test.js
node --test whatsapp/progress_message.test.js
node --test whatsapp/tests/sanitize.test.js
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest \
  tests/test_admin.py tests/test_discord_image_only.py \
  tests/test_manager_routing.py tests/test_p3_consistency.py -q
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest -q
git diff --check origin/main..HEAD
```

Expected: seluruh Node test lulus, targeted pytest lulus, full pytest nol failure, diff check bersih.

- [x] **Step 5: Push normal dan tunggu CI PR #8**

```bash
git push origin HEAD:codex/package-a-b-integration
/home/bima_lucian/.local/bin/gh pr checks 8 --repo Luciansvon/B.I.M.A-CORE \
  --watch --interval 10
```

Expected: push fast-forward tanpa `--force`; seluruh check head terbaru sukses.

- [x] **Step 6: Verifikasi PR #8 kembali mergeable**

```bash
/home/bima_lucian/.local/bin/gh pr view 8 --repo Luciansvon/B.I.M.A-CORE \
  --json isDraft,mergeable,mergeStateStatus,statusCheckRollup
```

Expected: `isDraft=false`, `MERGEABLE`, `CLEAN`, seluruh check `SUCCESS`.

### Task 9: Squash-Merge PR #8 dan Verifikasi `main`

**Files:**
- Tidak ada file baru.
- GitHub PR: `Luciansvon/B.I.M.A-CORE#8`

- [x] **Step 1: Squash-merge PR #8**

```bash
/home/bima_lucian/.local/bin/gh pr merge 8 --repo Luciansvon/B.I.M.A-CORE --squash
```

Expected: PR #8 merged dan remote branch `codex/package-a-b-integration` terhapus otomatis.

- [x] **Step 2: Fetch dan tunggu CI pada `main` hasil akhir**

```bash
git fetch origin
MAIN_SHA=$(git rev-parse origin/main)
RUN_ID=$(/home/bima_lucian/.local/bin/gh run list \
  --repo Luciansvon/B.I.M.A-CORE --workflow CI --branch main \
  --commit "$MAIN_SHA" --limit 1 --json databaseId --jq '.[0].databaseId')
/home/bima_lucian/.local/bin/gh run watch "$RUN_ID" \
  --repo Luciansvon/B.I.M.A-CORE --exit-status
```

Expected: workflow CI `main` selesai sukses.

- [x] **Step 3: Audit GitHub akhir**

```bash
/home/bima_lucian/.local/bin/gh pr list --repo Luciansvon/B.I.M.A-CORE --state open
/home/bima_lucian/.local/bin/gh api repos/Luciansvon/B.I.M.A-CORE/branches \
  --paginate --jq '.[].name'
```

Expected: tidak ada open PR; remote branch hanya `main`.

### Task 10: Bersihkan Worktree Cleanup tanpa Menyentuh Checkout Utama

**Files:**
- Remove worktree directory: `/home/bima_lucian/BIMA_CORE/.worktrees/pr7-cleanup`
- Remove worktree directory: `/home/bima_lucian/BIMA_CORE/.worktrees/pr8-cleanup`
- Preserve: `/home/bima_lucian/BIMA_CORE` dan semua perubahan lokalnya.

- [x] **Step 1: Verifikasi path dan status dua worktree**

```bash
git -C /home/bima_lucian/BIMA_CORE/.worktrees/pr7-cleanup status --short
git -C /home/bima_lucian/BIMA_CORE/.worktrees/pr8-cleanup status --short
git -C /home/bima_lucian/BIMA_CORE worktree list
```

Expected: dua worktree cleanup bersih dan path berada di bawah `/home/bima_lucian/BIMA_CORE/.worktrees/`.

- [x] **Step 2: Hapus hanya dua worktree milik task**

```bash
cd /home/bima_lucian/BIMA_CORE
git worktree remove /home/bima_lucian/BIMA_CORE/.worktrees/pr7-cleanup
git worktree remove /home/bima_lucian/BIMA_CORE/.worktrees/pr8-cleanup
git worktree prune
```

Local branch `codex/pr7-cleanup` dan `codex/pr8-cleanup` dipertahankan karena squash merge membuatnya bukan ancestor langsung `main`; PLAN tidak mengizinkan `git branch -D`.

- [x] **Step 3: Pastikan perubahan lokal Bima tetap utuh**

```bash
git branch --show-current
git status --short --branch
```

Expected: checkout utama tetap pada local branch `codex/package-a-b-integration`; seluruh perubahan lokal awal dan file PLAN masih ada, tidak di-stage atau di-commit.
