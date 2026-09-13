# BIMA_CORE P3 Consistency Remediation Plan

**Goal:** Menutup seluruh temuan P3 audit tanpa perubahan dependency/config rahasia.

## Task 1: Manager Route Count Consistency

**Files:** `core/langgraph_nodes/manager.py`, `tests/test_p3_consistency.py`

- [x] Tulis static regression test bahwa menu bernomor 1–22 dan instruksi menyebut 22 pilihan.
- [x] Ubah teks `20 pilihan` menjadi `22 pilihan`; tidak mengubah routing behavior.

## Task 2: Event-Loop Cache Identity

**Files:** `core/langgraph_engine.py`, `tests/test_p3_consistency.py`

- [x] Tulis test dua loop object yang dipaksa memiliki nilai `id()` sama tetap menghasilkan compiled app berbeda.
- [x] Key cache dengan object event loop melalui `weakref.WeakKeyDictionary`, bukan integer `id(loop)`.
- [x] Pertahankan satu app/checkpointer per loop dan cleanup seluruh connection di `shutdown_engine()`.

## Task 3: Non-blocking Cost SQLite in Async Paths

**Files:** `core/discord_bot.py`, `core/langgraph_nodes/llm_config.py`, `tests/test_p3_consistency.py`

- [x] Tulis test/source assertion cost guard Discord memakai `await asyncio.to_thread(...)`.
- [x] Ubah `CostTracker` menjadi `AsyncCallbackHandler`; `on_llm_end` async dan menulis cost lewat `asyncio.to_thread`.
- [x] Tulis behavior test callback memakai fake response dan patched writer tanpa SQLite nyata.

## Task 4: AgentMemory Script Consistency

**Files:** `services/agentmemory/package.json`, `tests/test_p3_consistency.py`

- [x] Tulis test `scripts.start` memuat `agentmemory --tools core`, sama dengan PM2.
- [x] Ubah script package saja; service tetap opt-in/disabled sampai vulnerability upstream aman.

## Task 5: Threads Root Env Regression

- [x] Jalankan ulang `tests/test_setup_threads.py`; tidak ada code change tambahan jika tetap hijau.

## Task 6: P3 Verification and Audit Log

- [x] Jalankan targeted P3 + regression terkait.
- [x] Jalankan compileall, Node/package JSON parse, dan `git diff --check`.
- [x] Jalankan full `pytest -q`.
- [x] Restart backend, cek `/health` dan fresh startup log.
- [x] Catat P3 di `error_solutions.md`.
