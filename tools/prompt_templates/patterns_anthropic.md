# Anthropic / Claude — Prompt Patterns Reference

Reference patterns saat `target_model=claude`. Apply di field `rewrite`.

## 1. XML Tags untuk Struktur

Claude trained kuat pada XML. Pisahin section pake tag:

```
<role>Lo adalah senior backend engineer.</role>

<task>
Review function `validate_email` di file `auth.py`. Identifikasi bug + suggest fix.
</task>

<constraints>
- Fokus security (regex injection, ReDoS).
- Max 3 critical issues.
- Skip style/formatting issues.
</constraints>

<output_format>
Untuk tiap issue: severity (high/medium/low), location, problem, fix.
</output_format>
```

## 2. Chain-of-Thought Trigger

Tambah inline trigger sebelum complex reasoning:
- "Pikir step-by-step sebelum jawab."
- "Tuliskan reasoning lo di `<thinking>` tag dulu, baru jawaban final di `<answer>`."
- "Sebelum kasih solusi, list 3 kemungkinan pendekatan + trade-off-nya."

## 3. Few-Shot dengan Tag

```
<example>
  <input>foo@bar</input>
  <output>invalid: missing TLD</output>
</example>
<example>
  <input>foo@bar.com</input>
  <output>valid</output>
</example>
```

## 4. Negative Constraint Eksplisit

Claude follow "JANGAN..." dengan baik. Pake CAPS untuk constraint kritis:
- "JANGAN tambah comment di output."
- "JANGAN modify file di luar `src/`."

## 5. Role Persona di Awal

Letakan role di paling atas, sebelum task. Spesifik > generik:
- ❌ "Lo adalah AI assistant."
- ✅ "Lo adalah staff security engineer dengan 10 tahun pengalaman audit Python web app."

## 6. Output Format Strict

Saat butuh parseable output, deklarasi format eksplisit:
- "Balas HANYA JSON dengan schema berikut, tanpa markdown wrapper:"
- "Output dalam YAML dengan key: severity, file, line, fix."

## 7. Long Context — Document Position

Saat ada long context (dokumen panjang), taro instruksi:
- Dokumen → di awal prompt.
- Pertanyaan/task → di akhir prompt (paling deket dengan turn assistant).

## Anti-Pattern

- Jangan over-format dengan markdown heavy (####, bold tebal banyak) — XML lebih jelas.
- Jangan kasih persona ambigu ("be helpful") — kalibrasi spesifik.
- Jangan campur instruksi dan data tanpa tag — bikin Claude confused mana instruksi mana input.
