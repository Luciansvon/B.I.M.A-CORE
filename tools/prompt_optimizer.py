"""
B.I.M.A Core — Prompt Optimizer Tool

Refactor prompt mentah → prompt efektif pakai pattern Anthropic/OpenAI.
Output: critique 6-axis + rewrite + reasoning, format JSON parseable.

Dipake oleh Seniman agent. Trigger via intent_classifier regex 'optim/rewrite/perbaik prompt'.
"""
import os
import json
from pathlib import Path
from typing import Optional

from crewai.tools import BaseTool


_TEMPLATES_DIR = Path(__file__).parent / "prompt_templates"
_DEFAULT_MODEL = "deepseek/deepseek-v4-pro"
_SCORE_AXES = ("clarity", "specificity", "structure", "constraints", "examples", "output_format")


def _load_template(name: str) -> str:
    path = _TEMPLATES_DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _validate_score(score: dict) -> dict:
    """Pastikan score punya 6 axis + total. Clamp 0-10, recompute total."""
    fixed = {}
    for axis in _SCORE_AXES:
        v = score.get(axis, 0)
        try:
            v = max(0, min(10, int(v)))
        except (TypeError, ValueError):
            v = 0
        fixed[axis] = v
    fixed["total"] = sum(fixed[a] for a in _SCORE_AXES)
    return fixed


def _format_markdown(result: dict) -> str:
    """Convert parsed JSON result jadi markdown buat user."""
    score = result.get("score", {})
    total = score.get("total", 0)

    bars = []
    for axis in _SCORE_AXES:
        v = score.get(axis, 0)
        bar = "█" * v + "░" * (10 - v)
        bars.append(f"  {axis:<14} {bar} {v}/10")

    out = [
        f"## Prompt Score: {total}/60",
        "",
        "```",
        *bars,
        "```",
        "",
        "### Critique",
        result.get("critique", "_(kosong)_"),
        "",
        "### Rewrite",
        "```",
        result.get("rewrite", "_(kosong)_"),
        "```",
        "",
        "### Reasoning",
        result.get("reasoning", "_(kosong)_"),
    ]
    patterns = result.get("applied_patterns", [])
    if patterns:
        out.extend(["", "### Applied Patterns", ", ".join(f"`{p}`" for p in patterns)])
    return "\n".join(out)


class PromptOptimizerTool(BaseTool):
    name: str = "Prompt Optimizer Tool"
    description: str = """Optimize / rewrite prompt biar lebih efektif pakai pattern Anthropic/OpenAI.
    Pakai HANYA jika Bima eksplisit minta optimize/rewrite/perbaikin prompt.
    Input format JSON string:
    {
        "prompt": "prompt mentah yang mau di-optimize",
        "target_model": "claude" | "gpt" | "gemini" (opsional, default gpt),
        "task_type": "code" | "writing" | "analysis" | "general" (opsional, default general)
    }
    Output: markdown dengan score 6-axis + critique + rewrite + reasoning."""

    def _run(self, input_json: str) -> str:
        try:
            data = json.loads(input_json) if isinstance(input_json, str) else dict(input_json)
        except json.JSONDecodeError as e:
            return f"FAILED|Input JSON gak valid: {e}"

        raw_prompt = (data.get("prompt") or "").strip()
        if not raw_prompt:
            return "FAILED|Field 'prompt' kosong"

        target_model = (data.get("target_model") or "gpt").lower()
        if target_model not in ("claude", "gpt", "gemini"):
            target_model = "gpt"
        task_type = (data.get("task_type") or "general").lower()

        system_prompt = _load_template("critique_system.md")
        if not system_prompt:
            return "FAILED|Template critique_system.md gak ketemu di tools/prompt_templates/"

        pattern_file = "patterns_anthropic.md" if target_model == "claude" else "patterns_openai.md"
        pattern_ref = _load_template(pattern_file)
        if pattern_ref:
            system_prompt = f"{system_prompt}\n\n---\n\n## Reference Patterns ({target_model})\n\n{pattern_ref}"

        user_msg = (
            f"target_model: {target_model}\n"
            f"task_type: {task_type}\n\n"
            f"prompt_to_optimize:\n```\n{raw_prompt}\n```"
        )

        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                return "FAILED|OPENROUTER_API_KEY gak diset di .env"

            client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
            )
            response = client.chat.completions.create(
                model=_DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
                max_tokens=2500,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            return f"FAILED|LLM call error: {e}"

        raw_content = response.choices[0].message.content if response.choices else ""
        if not raw_content:
            return "FAILED|LLM balas kosong"

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            cleaned = raw_content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```", 2)[1] if "```" in cleaned[3:] else cleaned[3:]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as e:
                return f"FAILED|LLM output bukan JSON valid: {e}\n\nRaw output:\n{raw_content[:500]}"

        parsed["score"] = _validate_score(parsed.get("score", {}))
        if "applied_patterns" in parsed and not isinstance(parsed["applied_patterns"], list):
            parsed["applied_patterns"] = []

        return f"SUCCESS|prompt_optimized|{_format_markdown(parsed)}"


def create_tool():
    """Hook buat plugin_loader (kalau nanti loader di-wire ke startup)."""
    return PromptOptimizerTool()
