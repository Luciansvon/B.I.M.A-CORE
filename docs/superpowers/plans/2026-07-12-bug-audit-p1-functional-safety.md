# BIMA_CORE P1 Functional and Safety Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menutup seluruh temuan P1 audit: sisa path traversal, sanitizer WhatsApp, error disclosure, setup Threads, slide approval, cloud backup, browser orphan/timeout, dan Sherlock whitespace.

**Architecture:** Reuse helper path P0, ekstrak sanitizer menjadi fungsi pure yang bisa dites, pakai helper pesan publik agar exception tetap di log, dan hilangkan jalur mutasi Git unattended. Slide generator memisahkan public approval flow dari compiler privat; browser worker dijalankan sebagai process group.

**Tech Stack:** Python 3.12, pytest, Node.js built-in test runner, FastAPI, pathlib, subprocess/process groups, Marp CLI.

**Known baseline:** Sebelum P1 ada 6 failure `tests/test_slide_generator.py` karena kode memilih Chrome Windows dari WSL. Binary Puppeteer lokal sudah dibuktikan menghasilkan PDF 16 KB.

**Dirty-worktree policy:** Jangan stage/commit file overlap; pertahankan semua hunk existing Bima.

---

## Task 1: Finish Path Confinement

**Files:**
- Modify `core/path_security.py`
- Modify `teams/t8_mekanik.py`
- Modify `teams/t4_admin/data_analysis_tool.py`
- Modify `teams/t2_visual.py`
- Modify `teams/t7_html_templates.py`
- Create `tests/test_p1_path_confinement.py`

- [x] **Step 1: Write RED tests**

Tests must prove:

```python
def test_file_saver_rejects_parent_traversal_before_approval(...): ...
def test_file_saver_approval_shows_resolved_output_path(...): ...
def test_data_analysis_rejects_existing_csv_outside_outputs(...): ...
def test_image_analyzer_rejects_local_image_outside_outputs(...): ...
def test_image_to_code_rejects_local_image_outside_outputs(...): ...
def test_html_template_does_not_embed_image_outside_outputs(...): ...
```

Use only temporary files; never read `.env` or real credentials. Patch permission/API boundaries and assert they are not called for rejected paths.

- [x] **Step 2: Run RED**

Run: `pytest tests/test_p1_path_confinement.py -q`  
Expected: traversal cases are accepted or reach approval/API under current code.

- [x] **Step 3: Add safe named-output helper**

Add to `core/path_security.py`:

```python
def safe_named_output_path(
    root: Path,
    requested_name: object,
    *,
    default_name: str,
) -> Path:
    root = root.resolve()
    raw = str(requested_name or "").strip().replace("\\", "/")
    leaf = raw.rsplit("/", 1)[-1]
    name = _UNSAFE_FILENAME_CHARS.sub("_", leaf).strip(" ._-")
    if not name:
        name = default_name
    candidate = (root / name[:120]).resolve()
    if candidate.parent != root:
        raise ValueError("Path tidak diizinkan")
    return candidate
```

- [x] **Step 4: Apply helper at each trust boundary**

- `FileSaverTool`: resolve before approval, show absolute resolved path, write only that path.
- `DataAnalysisTool`: `resolve_allowed_path(..., allowed_roots=(OUTPUT_DIR,), base_dir=OUTPUT_DIR.parent, allowed_suffixes={'.csv','.xlsx','.xls'})`; absolute outside paths must fail, not fallback.
- `ImageAnalyzerTool` and `ImageToCodeTool`: existing local files must resolve inside `OUTPUT_DIR` with image suffix allowlist before reading/base64.
- `render_template`: resolve `section.image_path` inside project `outputs/`; rejected path is skipped and logged without reading.

Return only `FAILED|Path tidak diizinkan` to the tool caller.

- [x] **Step 5: Run GREEN**

Run: `pytest tests/test_p1_path_confinement.py tests/test_admin.py -q`  
Expected: all pass.

## Task 2: WhatsApp Sanitizer Parser

**Files:**
- Create `whatsapp/sanitize.js`
- Create `whatsapp/tests/sanitize.test.js`
- Modify `whatsapp/index.js`

- [x] **Step 1: Write RED Node tests**

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { sanitizeForWhatsApp } = require('../sanitize');

test('keeps inline code content unchanged', () => {
  assert.equal(sanitizeForWhatsApp('`__init__`'), '__init__');
  assert.equal(
    sanitizeForWhatsApp("`if __name__=='__main__':`"),
    "if __name__=='__main__':",
  );
});

test('protects an unclosed fenced block to end of message', () => {
  assert.equal(sanitizeForWhatsApp('```py\n__init__'), '```py\n__init__');
});

test('preserves balanced parentheses in markdown URLs', () => {
  assert.equal(
    sanitizeForWhatsApp('[x](https://en.wikipedia.org/wiki/Foo_(bar))'),
    'x: https://en.wikipedia.org/wiki/Foo_(bar)',
  );
});

test('still converts narrative emphasis', () => {
  assert.equal(sanitizeForWhatsApp('**tebal** dan __juga__'), '*tebal* dan *juga*');
});
```

- [x] **Step 2: Run RED**

Run: `node --test whatsapp/tests/sanitize.test.js`  
Expected: module missing.

- [x] **Step 3: Implement a small state-machine sanitizer**

`whatsapp/sanitize.js` must:

1. Tokenize paired/unpaired fenced code and paired inline code before any emphasis replacement.
2. Store inline token content without backticks; store fenced token including fences.
3. Parse `[label](url)` by scanning balanced parentheses, not regex truncation.
4. Apply header/bold conversions only to narrative tokens.
5. Restore code tokens byte-for-byte except the intentional inline backtick removal.

Export with `module.exports = { sanitizeForWhatsApp };`.

- [x] **Step 4: Wire into bridge**

At top of `whatsapp/index.js`:

```javascript
const { sanitizeForWhatsApp } = require('./sanitize');
```

Delete the inline implementation; keep current call before `smartChunks()`.

- [x] **Step 5: Run GREEN**

Run:

```bash
node --test whatsapp/tests/sanitize.test.js
node --check whatsapp/index.js
```

Expected: 4 tests pass and syntax check exits 0.

## Task 3: Public Error Redaction

**Files:**
- Create `core/public_errors.py`
- Create `tests/test_p1_error_redaction.py`
- Modify `core/discord_bot.py`, `core/saham_commands.py`, `core/arsip_commands.py`
- Modify `teams/t4_admin/*.py`, `teams/t5_intel.py`, `teams/t6_lifestyle.py`, `teams/t8_mekanik.py`, `teams/t9_saham.py`

- [x] **Step 1: Write RED behavior/static tests**

```python
from core.public_errors import public_failure, public_message


def test_public_error_helpers_never_include_exception_detail() -> None:
    assert public_failure("Gagal membuat PDF") == (
        "FAILED|Gagal membuat PDF. Detail teknis dicatat di log."
    )
    assert public_message("Gagal memproses permintaan") == (
        "❌ Gagal memproses permintaan. Detail teknis dicatat di log."
    )
```

Add an AST scan over the exact files above. Inside an `except ... as <name>` block, fail when:

- a `return` f-string interpolates `<name>`;
- a Discord `reply()` f-string interpolates `<name>`;
- returned content calls `traceback.format_exc()`.

- [x] **Step 2: Run RED**

Run: `pytest tests/test_p1_error_redaction.py -q`  
Expected: helper import fails and static scan reports current leaks.

- [x] **Step 3: Implement helpers**

```python
def public_failure(context: str) -> str:
    return f"FAILED|{context}. Detail teknis dicatat di log."


def public_message(context: str) -> str:
    return f"❌ {context}. Detail teknis dicatat di log."
```

- [x] **Step 4: Replace audited leak sites**

For every caught exception in the listed files:

1. Keep/add `logger.exception(...)` locally.
2. Replace user/tool return with `public_failure("<fixed context>")`.
3. Replace direct Discord reply with `public_message("<fixed context>")`.
4. In `CodeExecutorTool`, remove traceback/history exception text from the returned chat payload; keep it in logger only.
5. JSON validation errors may say `JSON tidak valid` but must not include parser detail.

Fixed contexts are the existing Indonesian prefixes without `{exception}`: e.g. `Gagal membuat PDF`, `Gagal scrape Reddit`, `Gagal cek cuaca`, `Gagal ambil quote`, `Gagal menyimpan file`.

- [x] **Step 5: Run GREEN**

Run: `pytest tests/test_p1_error_redaction.py tests/test_security_fixes.py -q`  
Expected: all pass.

## Task 4: Threads Setup Validation and Rooted Env Path

**Files:**
- Modify `scripts/setup_threads.py`
- Modify `scripts/test_post_image.py`
- Create `tests/test_setup_threads.py`

- [x] **Step 1: Write RED tests**

Test that:

- both modules define `ENV_PATH == PROJECT_ROOT / '.env'`;
- `require_access_token({})` raises `ValueError`;
- `require_access_token({'access_token': None})` raises;
- a non-empty string is returned stripped;
- `save_env(..., env_path=tmp_path/'.env')` never writes literal `None`.

- [x] **Step 2: Run RED**

Run: `pytest tests/test_setup_threads.py -q`.

- [x] **Step 3: Implement validation**

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def require_access_token(payload: dict) -> str:
    token = payload.get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Response Threads tidak berisi access_token")
    return token.strip()
```

Use this after both token exchanges, before success output or `save_env`. Give `load_env`/`save_env` explicit typed path parameters defaulting to `ENV_PATH`. Apply the same rooted path to `test_post_image.py`.

- [x] **Step 4: Run GREEN**

Run: `pytest tests/test_setup_threads.py -q`  
Expected: all pass.

## Task 5: Enforce Slide Approval and Fix WSL Chrome Selection

**Files:**
- Modify `tools/slide_generator.py`
- Rewrite `tests/test_slide_generator.py`

- [x] **Step 1: Write RED tests without external Marp calls**

Tests must assert:

- `bypass_preview` is absent from `SlideGeneratorInput.model_fields`;
- public `_run(..., output_format='pdf')` always invokes permission gate;
- denial never compiles final PDF;
- approval compiles preview then final output;
- `_find_chrome()` selects executable under `~/.cache/puppeteer` before the Windows fallback;
- compiler passes that binary as `CHROME_PATH`;
- PDF-page extraction uses a temporary PDF created directly with PyMuPDF.

Mock `_compile()` or `subprocess.run`; tests must not run `npx`, hit network, or need a browser.

- [x] **Step 2: Run RED**

Run: `pytest tests/test_slide_generator.py -q`  
Expected: schema and approval tests fail; existing integration tests still show Chrome error.

- [x] **Step 3: Split public flow from private compiler**

- Remove `bypass_preview` from Pydantic schema, tool description, and public `_run` signature.
- Move current file-writing/Marp compilation into `_compile(markdown_content, output_format, theme_style)`.
- Public `_run` calls `_compile(..., 'png', ...)`, approval gate, preview cleanup, then `_compile(..., requested_format, ...)`.
- Direct public PNG remains supported without recursive preview.

- [x] **Step 4: Resolve a real WSL browser**

Add `_find_chrome() -> Path | None` with this order:

1. executable from `CHROME_PATH` when it is a Linux file;
2. executable `chrome` below `~/.cache/ms-playwright`;
3. executable `chrome` below `~/.cache/puppeteer`;
4. `shutil.which('google-chrome'|'chromium'|'chromium-browser')`;
5. mounted Windows Chrome only if it exists.

If none exists, return a generic failure before `npx`. Local evidence path under Puppeteer generated `/tmp/bima-marp-smoke.pdf` successfully.

- [x] **Step 5: Run GREEN and production smoke**

```bash
pytest tests/test_slide_generator.py -q
python3 -c "from tools.slide_generator import _find_chrome; print(_find_chrome())"
```

Expected: tests pass and path points to the Puppeteer Linux Chrome binary.

## Task 6: Disable Unattended Git Backup Mutation

**Files:**
- Replace `tools/cloud_backup.py`
- Create `tests/test_cloud_backup_safety.py`

- [x] **Step 1: Write RED test**

Import `backup()` with `run_git` patched to raise. Assert `backup()` returns `False` without calling Git and output explains a separate backup repository is required.

- [x] **Step 2: Run RED**

Run: `pytest tests/test_cloud_backup_safety.py -q`  
Expected: current function invokes Git.

- [x] **Step 3: Replace dangerous script with a safety stub**

Keep module/function compatibility but remove `git add`, commit, push, `.gitignore` writes, and cron instructions. `backup()` prints that automatic Git backup from the live development repo is disabled and returns `False`; `__main__` exits 1.

This is intentionally minimal: a real backup tool requires a separate repo/destination and a separately approved design.

- [x] **Step 4: Run GREEN**

Run: `pytest tests/test_cloud_backup_safety.py -q`.

## Task 7: Browser Worker Timeout and Process-Group Cleanup

**Files:**
- Modify `tools/browser_use_tool.py`
- Modify `tests/test_browser_worker_isolation.py`

- [x] **Step 1: Write RED tests**

Test that default timeout is `1260`, `Popen` receives `start_new_session=True`, timeout calls `os.killpg(worker.pid, SIGTERM)`, and a still-running group escalates to `SIGKILL`.

- [x] **Step 2: Run RED**

Run: `pytest tests/test_browser_worker_isolation.py -q`.

- [x] **Step 3: Replace `subprocess.run` with controlled `Popen`**

Use `stdin/stdout/stderr=PIPE`, `text=True`, `start_new_session=True`, then `communicate(payload, timeout=_worker_timeout())`. On timeout terminate the group, wait five seconds, then kill the group if required. Return only a generic timeout to chat; detailed stderr remains in logger.

- [x] **Step 4: Run GREEN**

Run: `pytest tests/test_browser_worker_isolation.py -q`.

## Task 8: Sherlock Whitespace Guard

**Files:**
- Modify `tools/sherlock_tool.py`
- Create `tests/test_sherlock_tool.py`

- [x] **Step 1: Write RED test**

```python
def test_sherlock_rejects_whitespace_without_index_error() -> None:
    assert SherlockTool()._run("   ") == (
        "FAILED|Username kosong / cuma karakter terlarang"
    )
```

- [x] **Step 2: Run RED**

Run: `pytest tests/test_sherlock_tool.py -q`  
Expected: `IndexError`.

- [x] **Step 3: Normalize before splitting**

```python
raw_username = (username or "").strip()
username = raw_username.split()[0] if raw_username else ""
```

Keep the existing character allowlist and length cap.

- [x] **Step 4: Run GREEN**

Run: `pytest tests/test_sherlock_tool.py -q`.

## Task 9: P1 Verification and Error Log

- [x] **Step 1: Run targeted P1 suite**

```bash
pytest \
  tests/test_p1_path_confinement.py \
  tests/test_p1_error_redaction.py \
  tests/test_setup_threads.py \
  tests/test_slide_generator.py \
  tests/test_cloud_backup_safety.py \
  tests/test_browser_worker_isolation.py \
  tests/test_sherlock_tool.py -q
node --test whatsapp/tests/sanitize.test.js
node --check whatsapp/index.js
```

- [x] **Step 2: Run syntax/static checks**

Run `python3 -m py_compile` on every modified Python file, then `git diff --check`.

- [x] **Step 3: Run full suite**

Run: `bima_env/bin/pytest -q`  
Expected: 0 failures, including the six former slide failures.

- [x] **Step 4: Runtime smoke**

Restart `anisa-v3` and `bima-whatsapp`, run `python scripts/healthcheck.py`, hit WA `/health`, and inspect fresh logs for import/startup errors.

- [x] **Step 5: Append `error_solutions.md`**

Record actual P1 root causes and fixes, including wrong WSL Chrome fallback, disabled live-repo auto-push, process-group cleanup, sanitizer tokenization, path confinement, and any command/test errors encountered. Do not include tokens or sensitive payloads.
