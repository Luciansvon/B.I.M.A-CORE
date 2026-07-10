# Threads Reply Anti-Slop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Upgrade draf balasan komentar Threads Anisa supaya lebih manusiawi, santai, pendek sesuai konteks, dan tidak terdengar seperti AI.

**Architecture:** Pertahankan Meta Threads Graph API dan approval Discord yang sudah ada. Perubahan hanya di prompt construction untuk balasan komentar, dibuat sebagai fungsi murni supaya bisa dites tanpa panggilan LLM atau jaringan.

**Tech Stack:** Python, pytest, LangChain message objects, Meta Threads Graph API existing flow.

---

## Explore Summary

- `core/threads_commands.py` sudah punya `BIMA_SYSTEM_PROMPT` panjang untuk posting utama.
- `reply_to_comment_flow()` saat ini membuat `user_prompt` balasan komentar langsung di dalam fungsi, dengan instruksi pendek: emosional, sarkas, singkatan gaul, "lu/gua", nyambung.
- `evaluate_auto_reply()` sudah aman untuk komentar sederhana dan membalas otomatis dengan teks pendek.
- Approval manusia via `request_permission()` sudah ada dan tidak perlu diganti.
- Test yang ada fokus ke dedup approval, revisi, dan anti bocor disclaimer AI. Belum ada test khusus untuk kualitas prompt balasan komentar.
- Web check 2026-07-10: dokumentasi Meta masih memakai alur resmi `reply_to_id` dan publish endpoint untuk membuat balasan, jadi tidak perlu ganti infrastruktur.

## File Structure

- Modify: `core/threads_commands.py`
  - Tambah helper `_build_threads_reply_prompt(reply_username, reply_text, post_text, viral_context="") -> str`.
  - `reply_to_comment_flow()` memakai helper ini saat membuat `user_prompt`.
- Create: `tests/test_threads_reply_prompt.py`
  - Test prompt helper tanpa network.
  - Test aturan few-shot, no fluff, length matching, dan konteks komentar tetap masuk.
- Modify: `error_solutions.md`
  - Tambah log jika saat implementasi muncul error baru.

## Task 1: Add Deterministic Prompt Tests

**Files:**
- Create: `tests/test_threads_reply_prompt.py`

- [x] **Step 1: Write failing tests**

```python
import core.threads_commands as tc


def test_threads_reply_prompt_contains_context_and_style_rules():
    prompt = tc._build_threads_reply_prompt(
        reply_username="user123",
        reply_text="wkwk relate bgt",
        post_text="laptop gua kipasnya udah kayak nyerah",
        viral_context="\\n=== POLA VIRAL ===\\npendek, punchy\\n",
    )

    assert "@user123" in prompt
    assert "wkwk relate bgt" in prompt
    assert "laptop gua kipasnya udah kayak nyerah" in prompt
    assert "Balasan Buruk" in prompt
    assert "Balasan Baik" in prompt
    assert "Length matching" in prompt
    assert "No fluff" in prompt
    assert "Wah, menarik sekali" in prompt
    assert "Tentu" in prompt
    assert "lu" in prompt and "gua" in prompt


def test_threads_reply_prompt_short_comment_demands_short_reply():
    prompt = tc._build_threads_reply_prompt(
        reply_username="shortuser",
        reply_text="anjir wkwk",
        post_text="kopi dingin lebih jujur dari todo list gua",
    )

    assert "Komentar pendek" in prompt
    assert "maks 8 kata" in prompt
    assert "jangan jawab kayak customer service" in prompt
    assert "jangan bikin ceramah" in prompt
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
source bima_env/bin/activate
pytest tests/test_threads_reply_prompt.py -q
```

Expected:

```text
AttributeError: module 'core.threads_commands' has no attribute '_build_threads_reply_prompt'
```

## Task 2: Add Reply Prompt Builder

**Files:**
- Modify: `core/threads_commands.py`

- [x] **Step 1: Add helper near `evaluate_auto_reply()` or before `reply_to_comment_flow()`**

```python
def _build_threads_reply_prompt(
    reply_username: str,
    reply_text: str,
    post_text: str,
    viral_context: str = "",
) -> str:
    """Build prompt khusus balasan komentar Threads supaya gaya reply tidak kaku."""
    return f"""Komentar dari @{reply_username} pada postingan kita:
Postingan Kita: "{post_text}"
Komentar Dia: "{reply_text}"
{viral_context}

Tugas:
Tulis draf balasan Threads yang nyambung, natural, dan terasa kayak manusia bales komentar temen.

Voice:
- Pake "gua" dan "lu". Jangan pake "gue" atau "loe".
- Bahasa chat Indo santai: wkwk, asli, anjir, bgt, emg, dah, sih, yaudah, ngab. Pakai seperlunya.
- Boleh sarkas ringan, tapi jangan maksa emosional kalau komentarnya biasa aja.
- Jangan toxic, jangan nyerang personal, jangan bahas SARA/politik/skincare.

Length matching:
- Komentar pendek atau cuma tawa: jawab pendek juga, ideal 2 sampai 8 kata.
- Komentar sedang: jawab 1 kalimat pendek.
- Komentar serius/bertanya: jawab tetap singkat, 1 sampai 2 kalimat, jangan bikin ceramah.
- Jangan lebih panjang dari komentar dia kecuali memang perlu jawab pertanyaan.

No fluff:
- Jangan mulai dengan basa-basi robot.
- Dilarang pakai pembuka: "Wah, menarik sekali", "Tentu", "Tentu saja", "Terima kasih sudah berbagi", "Perlu dicatat".
- Jangan jawab kayak customer service.
- Jangan jelasin kalau lu AI, bot, asisten, atau sistem.
- Jangan pake hashtag.
- Jangan pake format list.

Few-shot:
Balasan Buruk: "Wah, menarik sekali! Terima kasih sudah berbagi pendapatmu."
Balasan Baik: "wkwk asli relate bgt"

Balasan Buruk: "Tentu, hal tersebut memang cukup lucu dan relevan."
Balasan Baik: "emg agak nyiksa sih"

Balasan Buruk: "Secara keseluruhan, ini menunjukkan pengalaman yang banyak dialami orang."
Balasan Baik: "gua kira gua doang anjir"

Output:
- HANYA teks balasan final.
- Tanpa tanda kutip pembungkus.
- Maks 180 karakter, ideal di bawah 80 karakter.
"""
```

- [x] **Step 2: Run prompt tests**

Run:

```bash
source bima_env/bin/activate
pytest tests/test_threads_reply_prompt.py -q
```

Expected:

```text
2 passed
```

## Task 3: Wire Helper Into Reply Flow

**Files:**
- Modify: `core/threads_commands.py`
- Test: `tests/test_threads_dedup.py`

- [x] **Step 1: Replace inline prompt in `reply_to_comment_flow()`**

Find:

```python
    user_prompt = f"""Komentar dari @{reply_username} pada postingan kita:
Postingan Kita: "{post_text}"
Komentar Dia: "{reply_text}"
{viral_context}
Tulis draf balasan Threads yang sangat emosional, sarkas, menggunakan singkatan gaul, memakai kata "lu" dan "gua" (tanpa kata "loe" atau "gue"). Balas secara nyambung dan cerdas."""
```

Replace with:

```python
    user_prompt = _build_threads_reply_prompt(
        reply_username=reply_username,
        reply_text=reply_text,
        post_text=post_text,
        viral_context=viral_context,
    )
```

- [x] **Step 2: Run existing reply flow tests**

Run:

```bash
source bima_env/bin/activate
pytest tests/test_threads_dedup.py tests/test_threads_reply_prompt.py -q
```

Expected:

```text
7 passed
```

## Task 4: Regression Checks

**Files:**
- Test: `tests/test_threads_revision.py`
- Test: `tests/test_threads_no_ai_leak.py`

- [x] **Step 1: Run Threads regression tests**

Run:

```bash
source bima_env/bin/activate
pytest tests/test_threads_revision.py tests/test_threads_no_ai_leak.py tests/test_threads_dedup.py tests/test_threads_reply_prompt.py -q
```

Expected:

```text
all tests pass
```

- [x] **Step 2: Run AST syntax check**

Run:

```bash
source bima_env/bin/activate
python3 -c "import ast; ast.parse(open('core/threads_commands.py').read()); print('AST OK')"
```

Expected:

```text
AST OK
```

## Task 5: Manual Smoke Review

**Files:**
- No file edits.

- [x] **Step 1: Manually inspect sample prompt behavior through helper**

Run:

```bash
source bima_env/bin/activate
python3 - <<'PY'
from core.threads_commands import _build_threads_reply_prompt
print(_build_threads_reply_prompt(
    reply_username="tester",
    reply_text="anjir wkwk",
    post_text="file final_final_v9 lebih jujur dari hidup gua",
)[:1200])
PY
```

Expected:

```text
Prompt includes context, few-shot examples, no-fluff bans, and short-comment length rule.
```

## Self-Review

- Spec coverage: few-shot prompting, no fluff, sentiment and length matching, approval flow preservation, and official API preservation are covered.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: helper signature matches call site plan.
- Scope: one focused behavior change, no dependency change, no API migration.

## Approval Gate

Stop here until Bima approves implementation.
