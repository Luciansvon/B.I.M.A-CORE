# Anisa Compact VPS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menyediakan profil deployment VPS 2 vCPU/4 GB yang mempertahankan fitur inti Anisa dan menjalankan OCR lokal secara hemat RAM.

**Architecture:** Tambahkan template environment khusus Compact tanpa mengubah default development. Jalur `!ocr` tetap direct pre-route, tetapi memakai EasyOCR lokal saja dan melepas reader setelah idle 10 menit. Threads reaction gate dan fitur lain tidak diubah oleh plan ini.

**Tech Stack:** Python 3.11, EasyOCR CPU, asyncio, pytest, PM2, Ubuntu LTS.

---

## Explore Summary

- `core/ocr.py` saat ini lazy-load EasyOCR, tetapi handler menjalankan Gemini Vision lebih dahulu dan reader lokal tidak pernah dilepas.
- `core/discord_bot.py` sudah melakukan direct pre-route `!ocr`, jadi OCR tidak perlu melewati LangGraph.
- `.env.example` sudah mematikan STT/TTS secara default dan mengaktifkan Threads.
- `ecosystem.config.js` masih membawa konfigurasi model STT lokal; profil Compact harus override lewat file environment terpisah, bukan mengubah perilaku workstation.
- `whatsapp-web.js` tetap memerlukan Chromium internal walaupun BrowserUseTool tidak dipakai.

## File Structure

- Create: `.env.compact.example` — sumber konfigurasi VPS Compact yang aman untuk disalin menjadi `.env`.
- Modify: `core/ocr.py` — OCR EasyOCR-only, serial execution, idle release.
- Create: `tests/test_ocr_compact.py` — menjamin tidak ada vision API pada `!ocr` dan reader dilepas setelah idle.
- Create: `tests/test_compact_env.py` — kontrak feature flag profil Compact.
- Create: `docs/runbooks/anisa-compact-vps.md` — provisioning dan verification checklist.
- Modify: `error_solutions.md` hanya jika implementasi menghasilkan error baru.

## Task 1: Lock the Compact Environment Contract

**Files:**
- Create: `tests/test_compact_env.py`
- Create: `.env.compact.example`

- [ ] **Step 1: Write the failing environment contract test**

```python
from pathlib import Path


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_compact_profile_keeps_core_and_disables_heavy_features():
    env = _read_env(Path(".env.compact.example"))
    assert env["ENABLE_THREADS_AUTO"] == "true"
    assert env["ENABLE_STT"] == "false"
    assert env["ENABLE_TTS"] == "false"
    assert env["ENABLE_OBSERVABILITY"] == "false"
    assert env["ENABLE_BRIEFING"] == "false"
    assert env["ENABLE_HEADROOM"] == "false"
    assert env["ENABLE_CHECKPOINTING"] == "true"
    assert env["ENABLE_SUMMARIZATION"] == "true"
    assert env["OCR_ENGINE"] == "easyocr"
    assert env["OCR_IDLE_TTL_SECONDS"] == "600"
```

- [ ] **Step 2: Run the test and confirm the missing profile failure**

Run:

```bash
source bima_env/bin/activate
pytest tests/test_compact_env.py -q
```

Expected: `FileNotFoundError: .env.compact.example`.

- [ ] **Step 3: Create the compact environment template**

```dotenv
# Copy to .env on the Compact VPS, then fill secrets from the existing private .env.
ENABLE_STT=false
ENABLE_TTS=false
ENABLE_OBSERVABILITY=false
ENABLE_BRIEFING=false
ENABLE_HEADROOM=false
ENABLE_THREADS_AUTO=true
ENABLE_CHECKPOINTING=true
ENABLE_SUMMARIZATION=true
ENABLE_MODEL_ROUTER=true
ENABLE_COST_GUARDRAILS=true
ENABLE_THREAD_ISOLATION=true
ENABLE_STREAMING_DISCORD=true
OCR_ENGINE=easyocr
OCR_IDLE_TTL_SECONDS=600
AGENTMEMORY_ENABLED=false
```

`AGENTMEMORY_ENABLED=false` tetap dipakai sampai vulnerability transitive yang tercatat di `error_solutions.md` memiliki upgrade tervalidasi. SQLite dan file vault tetap menjadi penyimpanan lokal.

- [ ] **Step 4: Run the environment contract test**

Run: `pytest tests/test_compact_env.py -q`

Expected: `1 passed`.

- [ ] **Step 5: Commit the profile contract**

```bash
git add .env.compact.example tests/test_compact_env.py
git commit -m "test: define anisa compact environment profile"
```

## Task 2: Make OCR Local-Only

**Files:**
- Modify: `core/ocr.py`
- Create: `tests/test_ocr_compact.py`

- [ ] **Step 1: Write the failing local-only handler test**

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import core.ocr as ocr


@pytest.mark.asyncio
async def test_handle_ocr_uses_easyocr_without_vlm(monkeypatch):
    attachment = SimpleNamespace(
        filename="scan.png",
        size=128,
        url="https://example.test/scan.png",
    )
    progress = SimpleNamespace(edit=AsyncMock())
    message = SimpleNamespace(
        attachments=[attachment],
        reply=AsyncMock(return_value=progress),
    )
    response = SimpleNamespace(
        content=b"\x89PNGfake",
        raise_for_status=lambda: None,
    )
    client = AsyncMock()
    client.__aenter__.return_value.get.return_value = response
    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: client)
    monkeypatch.setattr(ocr, "extract_text_async", AsyncMock(return_value="MEJA 1200"))
    vlm = AsyncMock(side_effect=AssertionError("VLM must not be called"))
    monkeypatch.setattr(ocr, "extract_text_vlm_async", vlm)

    await ocr.handle_ocr_command(message)

    vlm.assert_not_awaited()
    ocr.extract_text_async.assert_awaited_once_with(b"\x89PNGfake")
    assert "easyocr" in progress.edit.await_args.kwargs["content"].lower()
```

- [ ] **Step 2: Run the handler test and confirm it fails**

Run: `pytest tests/test_ocr_compact.py::test_handle_ocr_uses_easyocr_without_vlm -q`

Expected: FAIL because the current handler calls `extract_text_vlm_async()` first.

- [ ] **Step 3: Replace the VLM-first block in `handle_ocr_command()`**

```python
        text = await extract_text_async(img_bytes)
        engine = "easyocr"
```

Keep input validation, download timeout, Discord truncation, and error reporting unchanged. Do not delete the VLM helper in this task; other callers must be searched before removal.

- [ ] **Step 4: Run the focused handler test**

Run: `pytest tests/test_ocr_compact.py::test_handle_ocr_uses_easyocr_without_vlm -q`

Expected: `1 passed`.

- [ ] **Step 5: Commit local-only OCR routing**

```bash
git add core/ocr.py tests/test_ocr_compact.py
git commit -m "feat: route anisa ocr through local easyocr"
```

## Task 3: Serialize OCR and Release the Reader After Idle

**Files:**
- Modify: `core/ocr.py`
- Modify: `tests/test_ocr_compact.py`

- [ ] **Step 1: Add failing lifecycle tests**

```python
@pytest.mark.asyncio
async def test_ocr_reader_is_reused_within_idle_window(monkeypatch):
    fake_reader = SimpleNamespace(readtext=lambda _: [([], "ABC", 0.99)])
    build = AsyncMock(return_value=fake_reader)
    monkeypatch.setattr(ocr, "_build_reader_async", build)
    monkeypatch.setattr(ocr, "_OCR_IDLE_TTL_SECONDS", 60)
    await ocr.extract_text_async(b"one")
    await ocr.extract_text_async(b"two")
    assert build.await_count == 1


@pytest.mark.asyncio
async def test_ocr_reader_is_released_after_idle(monkeypatch):
    fake_reader = SimpleNamespace(readtext=lambda _: [([], "ABC", 0.99)])
    monkeypatch.setattr(ocr, "_build_reader_async", AsyncMock(return_value=fake_reader))
    monkeypatch.setattr(ocr, "_OCR_IDLE_TTL_SECONDS", 0)
    await ocr.extract_text_async(b"one")
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert ocr._reader is None
```

Add `import asyncio` to the test file and reset `_reader` plus any unload task in an autouse fixture.

- [ ] **Step 2: Run lifecycle tests and confirm missing lifecycle API failures**

Run: `pytest tests/test_ocr_compact.py -q`

Expected: FAIL because `_build_reader_async` and idle release do not exist.

- [ ] **Step 3: Add the reader lifecycle implementation**

```python
import gc
import os

_reader = None
_reader_lock = asyncio.Lock()
_reader_unload_task: asyncio.Task | None = None
_reader_generation = 0
_OCR_IDLE_TTL_SECONDS = int(os.environ.get("OCR_IDLE_TTL_SECONDS", "600"))


async def _build_reader_async():
    return await asyncio.to_thread(_build_reader)


async def _release_reader_after_idle(generation: int) -> None:
    global _reader
    await asyncio.sleep(_OCR_IDLE_TTL_SECONDS)
    async with _reader_lock:
        if generation != _reader_generation:
            return
        _reader = None
        await asyncio.to_thread(gc.collect)
        logger.info("[ocr] EasyOCR reader released after idle timeout")


def _schedule_reader_release() -> None:
    global _reader_unload_task
    if _reader_unload_task and not _reader_unload_task.done():
        _reader_unload_task.cancel()
    _reader_unload_task = asyncio.create_task(
        _release_reader_after_idle(_reader_generation)
    )


async def extract_text_async(image_bytes: bytes) -> str:
    global _reader, _reader_generation
    async with _reader_lock:
        if _reader is None:
            logger.info("[ocr] init EasyOCR Reader (id+en)")
            _reader = await _build_reader_async()
        results = await asyncio.to_thread(_reader.readtext, image_bytes)
        text = "\n".join(value for _, value, _ in results if value.strip())
        _reader_generation += 1
    _schedule_reader_release()
    return text
```

Keep the synchronous `extract_text()` public function for compatibility, but make the Discord path use the serialized async implementation above. Search all callers before changing its semantics.

- [ ] **Step 4: Run OCR tests**

Run: `pytest tests/test_ocr_compact.py -q`

Expected: all tests pass with no network or real model load.

- [ ] **Step 5: Run existing voice and Discord-adjacent regression tests**

Run:

```bash
pytest tests/test_voice_feature_flags.py tests/test_threads_dedup.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit OCR lifecycle**

```bash
git add core/ocr.py tests/test_ocr_compact.py
git commit -m "feat: release easyocr reader after compact idle window"
```

## Task 4: Write the Deferred VPS Runbook

**Files:**
- Create: `docs/runbooks/anisa-compact-vps.md`

- [ ] **Step 1: Document provisioning commands and explicit approval gates**

The runbook must contain these exact phases:

```markdown
# Anisa Compact VPS Runbook

## Budget and Target
- 2 vCPU, 4 GB RAM, 60 GB SSD.
- Monthly billing target: Rp139.000 before any checkout tax.

## Approval Gates
- Do not purchase a VPS without Bima's explicit approval.
- Do not copy `.env`, tokens, or WhatsApp session data without Bima's explicit approval.
- Do not change DNS or production tunnel configuration without Bima's explicit approval.

## Provision
1. Install Ubuntu LTS updates, Python 3.11, Node.js 20, PM2, ffmpeg, and build tools.
2. Create a 4 GB swap file with swappiness 10.
3. Clone BIMA_CORE and create `bima_env`.
4. Copy `.env.compact.example` to `.env`, then insert secrets manually.
5. Install dependencies from the locked project environment.
6. Start `anisa-v3`, `bima-whatsapp`, and the required tunnel only.

## Verify
1. Run `source bima_env/bin/activate && pytest tests/test_compact_env.py tests/test_ocr_compact.py -q`.
2. Run `python scripts/healthcheck.py`.
3. Send Discord text, WhatsApp text, `!ocr`, and one Threads dry workflow.
4. Confirm `ENABLE_STT=false` and `ENABLE_TTS=false` in PM2 environment.
5. Confirm idle RAM remains below 75% before enabling auto-post.

## Rollback
Stop the VPS PM2 processes and restore the workstation deployment. Do not delete the VPS or its data until Bima approves deletion.
```

- [ ] **Step 2: Review the runbook for secrets and destructive commands**

Run: `rg -n "TOKEN=|API_KEY=|rm -rf|reset --hard|--force" docs/runbooks/anisa-compact-vps.md`

Expected: no secret values and no destructive commands.

- [ ] **Step 3: Commit the runbook**

```bash
git add docs/runbooks/anisa-compact-vps.md
git commit -m "docs: add deferred anisa compact vps runbook"
```

## Final Verification

- [ ] Run `pytest tests/test_compact_env.py tests/test_ocr_compact.py tests/test_voice_feature_flags.py tests/test_threads_dedup.py -q`.
- [ ] Run `python scripts/healthcheck.py` on the target VPS only after purchase approval.
- [ ] Verify the Threads reaction flow remains unchanged: approve posts, reject cancels, timeout performs safety check, safe drafts auto-post.
- [ ] Record every implementation or deployment error and its verified solution in `error_solutions.md`.

