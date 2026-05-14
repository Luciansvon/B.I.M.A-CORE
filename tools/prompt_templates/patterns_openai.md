# OpenAI / GPT — Prompt Patterns Reference

Reference patterns saat `target_model=gpt`. Apply di field `rewrite`. Juga dipake untuk `gemini` dengan minor adjustment (gemini suka contoh konkret, GPT suka structure).

## 1. Markdown Section Headers

GPT trained pada doc markdown. Pisahin section dengan `##`:

```
## Role
Lo adalah senior backend engineer.

## Task
Review function `validate_email` di file `auth.py`. Identifikasi bug + suggest fix.

## Constraints
- Fokus security (regex injection, ReDoS).
- Max 3 critical issues.
- Skip style/formatting issues.

## Output Format
Untuk tiap issue: severity (high/medium/low), location, problem, fix.
```

## 2. Numbered Steps untuk Procedural

GPT inggris kerja paling baik dengan numbered list buat task sequential:
```
1. Parse file `auth.py`.
2. Identifikasi fungsi yang handle user input.
3. Untuk tiap fungsi, check 3 hal: SQL injection, XSS, ReDoS.
4. Output sebagai tabel markdown.
```

## 3. Role + Task Clarity

Pisahin "siapa" dan "ngapain":
- **Role**: identity & expertise (selama session)
- **Task**: action yang concrete (sekarang)

Hindarin merge "Lo adalah X yang ngerjain Y" — split.

## 4. Output Format dengan Schema Eksplisit

```
## Output
Balas dalam JSON dengan schema berikut. Jangan wrap dalam markdown.

{
  "severity": "high" | "medium" | "low",
  "location": "filename:line",
  "problem": "string max 200 chars",
  "fix": "string max 500 chars"
}
```

## 5. Few-Shot Examples

```
## Examples
Input: `foo@bar`
Output: `{"valid": false, "reason": "missing TLD"}`

Input: `foo@bar.com`
Output: `{"valid": true, "reason": null}`
```

## 6. Reasoning Trigger

Buat reasoning task, eksplisit:
- "Jelasin reasoning lo dulu (max 3 kalimat), baru kasih final answer."
- "Pakai chain-of-thought: list facts → infer → conclude."

GPT-4+ default thinking implicit, tapi explicit trigger sering improve accuracy.

## 7. System vs User Distinction

Pisahin yang stable (role, constraint, output format) ke system message, dan yang turn-specific (task input, context data) ke user message.

## 8. Temperature & Determinism Hints

Saat butuh deterministik, tambah di prompt:
- "Jawab faktual, jangan creative."
- "Kalau ragu, bilang 'tidak tahu' — jangan ngarang."

## Anti-Pattern

- Jangan campur task & input tanpa pembatas — pake `---` atau triple backticks.
- Jangan request format yang ambiguous ("kasih insights") — selalu spesifik.
- Jangan lupa output format — GPT default ke prosa, kadang gak parseable.
- Jangan terlalu panjang system prompt > 2000 token — diminishing return.
