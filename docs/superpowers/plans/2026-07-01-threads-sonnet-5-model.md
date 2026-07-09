# Threads Sonnet 5 Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ganti LLM Bot_thread/Threads dari Claude Sonnet 4.6 ke Claude Sonnet 5.

**Architecture:** Threads memakai `THREADS_LLM_MODEL` dari env sebagai sumber runtime utama, dengan fallback hardcoded di modul command. Perubahan efektif harus update env runtime dan fallback kode agar bot tetap pakai Sonnet 5 jika env tidak diset.

**Tech Stack:** Python, LangChain `ChatOpenAI`, OpenRouter, Discord Bot_thread, PM2.

---

## Context

- Current runtime env: `.env:75` berisi `THREADS_LLM_MODEL=anthropic/claude-sonnet-4.6`.
- Current fallback:
  - `core/threads_commands.py`
  - `AI_sosmed/core/threads_commands.py`
- OpenRouter Sonnet 5 slug terbaru: `anthropic/claude-sonnet-5`.
- Anthropic native API slug: `claude-sonnet-5`.

## Files

- Modify: `.env`
- Modify: `core/threads_commands.py`
- Modify: `AI_sosmed/core/threads_commands.py`
- Modify: `AI_sosmed/.env.example`
- Modify: `docs/error_solutions.md`

## Tasks

### Task 1: Update Runtime Env

- [x] Change `.env:75` from:

```env
THREADS_LLM_MODEL=anthropic/claude-sonnet-4.6
```

to:

```env
THREADS_LLM_MODEL=anthropic/claude-sonnet-5
```

### Task 2: Update Code Fallbacks

- [x] Change fallback in `core/threads_commands.py` from `anthropic/claude-sonnet-4.6` to `anthropic/claude-sonnet-5`.
- [x] Change fallback in `AI_sosmed/core/threads_commands.py` from `anthropic/claude-sonnet-4.6` to `anthropic/claude-sonnet-5`.
- [x] Update stale comment that says Claude 3.5 Sonnet so it does not mislead future debugging.

### Task 3: Update Env Example

- [x] Change `AI_sosmed/.env.example`:

```env
THREADS_LLM_MODEL=anthropic/claude-sonnet-5
```

### Task 4: Log Error/Solution

- [x] Add a short entry to `docs/error_solutions.md` explaining old Sonnet 4.6 config and fix to Sonnet 5.

### Task 5: Verify

- [x] Run syntax checks:

```bash
wsl bash -c "cd /home/bima_lucian/BIMA_CORE && source bima_env/bin/activate && python3 -c \"import ast; ast.parse(open('core/threads_commands.py', encoding='utf-8').read()); ast.parse(open('AI_sosmed/core/threads_commands.py', encoding='utf-8').read()); print('AST OK')\""
```

- [x] Confirm env line only:

```powershell
Select-String -LiteralPath '.env' -Pattern '^THREADS_LLM_MODEL\s*='
```

- [x] Optional after approval: restart PM2 process that runs Bot_thread.
