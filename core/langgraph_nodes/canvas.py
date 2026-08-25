"""Canvas Node — PDF iterative editing (F4b).

Lifecycle:
  1. INIT  : user pertama kali minta "draft PDF tentang X"
             → LLM generate spec awal → save session → render PDF
  2. REVISE: user dah punya session aktif, kirim revisi ("section 2 tambah X")
             → LLM mutate spec → save → re-render PDF
  3. FINALIZE: user bilang "selesai/final/done"
             → render final + close session
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

from langchain_core.messages import AIMessage

from core import canvas_session
from core.langgraph_nodes.state import BimaState, notify_progress
from core.model_router import model_profile, openrouter_extra_body

logger = logging.getLogger("bima_core")
CANVAS_MODEL = model_profile("canvas").model

_FINALIZE_PATTERNS = re.compile(
    r"\b(selesai|udah\s+(final|cukup|beres)|done|final(?:isasi|kan)?|kelar|fix|udah\s+oke)\b",
    re.IGNORECASE,
)


def _is_finalize(text: str) -> bool:
    return bool(_FINALIZE_PATTERNS.search(text or ""))


async def _llm_init_spec(topic: str, user_request: str) -> dict:
    """Panggil LLM buat generate spec PDF awal dari topik user. Return dict."""
    from openai import OpenAI
    import os

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return _fallback_spec(topic or user_request)

    system_prompt = """Lo PDF spec generator. Output WAJIB JSON valid sesuai schema PDFGeneratorTool BIMA_CORE.

Schema:
{
  "filename": "kebab_case_filename",
  "style": "formal" | "casual" | "creative" | "technical" | "educational",
  "cover": true,
  "title": "Judul Utama",
  "subtitle": "Subjudul (opsional)",
  "author": "B.I.M.A Core / Anisa",
  "toc": true,
  "sections": [
    {
      "heading": "Judul Bagian",
      "content": "isi paragraf 2-4 kalimat",
      "drop_cap": false,
      "pullquote": "(opsional, string quote)",
      "list": ["item bullet 1", "item bullet 2"],
      "table": {"headers": ["A","B"], "rows": [["x","y"]]}
    }
  ]
}

ATURAN:
- Generate 3-5 sections yang relevan dengan topik.
- Section pertama: drop_cap=true (magazine-style).
- Section yang punya statement kuat: kasih pullquote.
- Konten realistis dan informatif, BAHASA INDONESIA casual.
- JANGAN ngarang fakta spesifik (statistik, angka, nama orang) — bilang "data perlu di-verify" kalau ragu.
- Output HANYA JSON, tanpa markdown wrapper."""

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    try:
        r = client.chat.completions.create(
            model=CANVAS_MODEL,
            extra_body=openrouter_extra_body("canvas"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Topik: {topic or user_request}\n\nRequest: {user_request}"},
            ],
            temperature=0.4,
            max_tokens=2500,
            response_format={"type": "json_object"},
        )
        raw = r.choices[0].message.content if r.choices else ""
        spec = json.loads(raw)
        return _normalize_spec(spec, topic)
    except Exception as e:
        logger.warning(f"[canvas] LLM init gagal: {e}, pakai fallback")
        return _fallback_spec(topic or user_request)


async def _llm_revise_spec(current_spec: dict, user_request: str) -> tuple[dict, str]:
    """LLM modifikasi spec berdasar instruksi user. Return (new_spec, change_note)."""
    from openai import OpenAI
    import os

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return current_spec, "LLM gak available, spec gak berubah"

    system_prompt = """Lo PDF spec editor. User punya draft PDF (JSON spec) dan minta revisi.

INPUT:
- "current_spec": JSON spec PDF saat ini
- "revision_request": instruksi revisi user (mis. "section 2 perpanjang", "ganti chart bar jadi pie", "tambah section soal X")

OUTPUT (JSON):
{
  "spec": { ...spec lengkap yang udah di-update... },
  "change_note": "ringkasan 1 kalimat apa yang berubah"
}

ATURAN:
- Output WAJIB spec LENGKAP (semua field), bukan diff.
- Cuma ubah bagian yang user minta. Section lain JANGAN diutak-atik.
- Pertahankan schema yang sama (filename, style, cover, sections, dll).
- Kalau user gak jelas / gak bisa interpret → balikin spec apa adanya + change_note "tidak ada perubahan, request gak jelas".
- Output HANYA JSON, tanpa markdown wrapper."""

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    user_msg = json.dumps(
        {"current_spec": current_spec, "revision_request": user_request},
        ensure_ascii=False,
    )

    try:
        r = client.chat.completions.create(
            model=CANVAS_MODEL,
            extra_body=openrouter_extra_body("canvas"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=3500,
            response_format={"type": "json_object"},
        )
        raw = r.choices[0].message.content if r.choices else ""
        parsed = json.loads(raw)
        new_spec = _normalize_spec(parsed.get("spec", current_spec), current_spec.get("title", ""))
        note = parsed.get("change_note", "spec di-update")
        return new_spec, note
    except Exception as e:
        logger.warning(f"[canvas] LLM revise gagal: {e}")
        return current_spec, f"revise gagal: {e}"


def _fallback_spec(topic: str) -> dict:
    """Spec default kalau LLM gak available. Minimal tapi valid."""
    return {
        "filename": "canvas_draft",
        "style": "casual",
        "cover": True,
        "title": topic[:80] if topic else "Draft Canvas",
        "subtitle": "Iterative editing dengan Anisa",
        "author": "B.I.M.A Core / Anisa",
        "toc": False,
        "sections": [
            {
                "heading": "Pendahuluan",
                "content": (
                    f"Ini draft awal tentang '{topic or 'topik'}'. "
                    "Section ini di-generate otomatis sebagai fallback. "
                    "Lo bisa minta Anisa revisi (mis. 'section 1 perpanjang', "
                    "'ganti judul jadi X', 'tambah section soal Y')."
                ),
                "drop_cap": True,
            },
        ],
    }


def _normalize_spec(spec: dict, fallback_title: str = "") -> dict:
    """Pastikan spec punya field minimum + safe defaults."""
    if not isinstance(spec, dict):
        return _fallback_spec(fallback_title)
    spec.setdefault("filename", "canvas_draft")
    spec.setdefault("style", "casual")
    spec.setdefault("cover", True)
    spec.setdefault("title", fallback_title or "Draft Canvas")
    spec.setdefault("author", "B.I.M.A Core / Anisa")
    spec.setdefault("toc", False)
    if "sections" not in spec or not isinstance(spec["sections"], list):
        spec["sections"] = []
    if not spec["sections"]:
        spec["sections"] = [{
            "heading": "Pendahuluan",
            "content": "Konten kosong — minta Anisa revisi buat ngisi.",
        }]
    return spec


async def _render_pdf(spec: dict, version: int) -> str:
    """Render PDF via PDFGeneratorTool existing. Return result string atau error."""
    from teams.t4_admin import PDFGeneratorTool

    # Tambah suffix version di filename biar tiap revisi punya file beda
    rendered_spec = dict(spec)
    base_name = rendered_spec.get("filename", "canvas_draft")
    rendered_spec["filename"] = f"{base_name}_v{version}"

    tool = PDFGeneratorTool()
    try:
        return await asyncio.to_thread(tool._run, json.dumps(rendered_spec))
    except Exception as e:
        return f"FAILED|render error: {e}"


def _extract_pdf_path(result: str) -> str | None:
    """Parse 'SUCCESS|<path>|<msg>' atau return None kalau FAILED."""
    if not result or not result.startswith("SUCCESS|"):
        return None
    parts = result.split("|", 2)
    return parts[1] if len(parts) >= 2 else None


def _summary_msg(spec: dict, version: int, change_note: str, pdf_path: str, is_final: bool) -> str:
    sections = spec.get("sections", [])
    section_list = "\n".join(f"  {i+1}. {s.get('heading', '(no heading)')}" for i, s in enumerate(sections[:8]))
    if len(sections) > 8:
        section_list += f"\n  ... ({len(sections) - 8} section lagi)"

    if is_final:
        header = f"✅ **PDF FINAL siap.** ({version} revisi)"
        footer = "Session canvas ditutup. Mau bikin draft baru? Bilang 'draft PDF tentang ...' aja."
    else:
        header = f"📝 **Draft v{version}** — {change_note}"
        footer = (
            "Mau revisi lagi? Contoh: 'section 2 perpanjang', 'ganti chart bar di section 3 jadi pie', "
            "'tambah section soal X'. Kalau udah cukup: bilang 'selesai' / 'final'."
        )

    return f"""{header}

**Title**: {spec.get('title', '(no title)')}
**Style**: {spec.get('style', 'casual')}
**Sections**:
{section_list}

**PDF**: `{pdf_path}`

{footer}"""


async def canvas_node(state: BimaState) -> dict:
    """Handler PDF Canvas — init / revise / finalize berdasar konteks session."""
    user_request = state.get("user_request", "")
    user_id = state.get("discord_user_id", "")

    if not user_id:
        # Tanpa identity channel kita gak bisa track session.
        return {
            "messages": [AIMessage(
                content=(
                    "⚠️ Canvas mode butuh identitas user dari channel chat. "
                    "Coba kirim ulang dari sesi yang sama."
                )
            )],
            "is_finished": True,
        }

    lock = canvas_session.get_lock(user_id)
    async with lock:
        existing = canvas_session.load(user_id)
        is_finalize = _is_finalize(user_request) and existing is not None

        if is_finalize:
            # Finalize — render final + close session
            await notify_progress(state, "🎨 *Canvas: finalisasi PDF...*")
            spec = existing["spec"]
            version = existing["version"]
            result = await _render_pdf(spec, version)
            pdf_path = _extract_pdf_path(result)
            canvas_session.close(user_id)
            if not pdf_path:
                return {
                    "messages": [AIMessage(content=f"❌ Gagal render PDF final: {result}")],
                    "is_finished": True,
                }
            return {
                "messages": [AIMessage(content=_summary_msg(spec, version, "final version", pdf_path, is_final=True))],
                "is_finished": True,
            }

        if existing is None:
            # INIT — session baru
            await notify_progress(state, "🎨 *Canvas: lagi bikin draft awal PDF...*")
            # Extract topic dari request kalau ada
            topic_match = re.search(r"(?:tentang|soal|mengenai|topik)\s+(.+?)(?:\s+dengan|\s*$)", user_request, re.IGNORECASE)
            topic = topic_match.group(1).strip() if topic_match else ""
            spec = await _llm_init_spec(topic, user_request)
            session = canvas_session.init(user_id, spec, topic=topic)
            result = await _render_pdf(spec, session["version"])
            pdf_path = _extract_pdf_path(result)
            if not pdf_path:
                # Render fail — drop session biar user bisa retry
                canvas_session.close(user_id)
                return {
                    "messages": [AIMessage(content=f"❌ Gagal render draft awal: {result}")],
                    "is_finished": True,
                }
            return {
                "messages": [AIMessage(content=_summary_msg(spec, session["version"], "initial draft", pdf_path, is_final=False))],
                "is_finished": True,
            }

        # REVISE — session ada, user kirim revisi
        await notify_progress(state, f"🎨 *Canvas: revisi draft v{existing['version']}...*")
        new_spec, change_note = await _llm_revise_spec(existing["spec"], user_request)
        updated = canvas_session.update(user_id, new_spec, change_note=change_note)
        if updated is None:
            return {
                "messages": [AIMessage(content=f"❌ Gagal update canvas session: storage error")],
                "is_finished": True,
            }
        result = await _render_pdf(new_spec, updated["version"])
        pdf_path = _extract_pdf_path(result)
        if not pdf_path:
            return {
                "messages": [AIMessage(content=f"❌ Gagal render revisi: {result}")],
                "is_finished": True,
            }
        return {
            "messages": [AIMessage(content=_summary_msg(new_spec, updated["version"], change_note, pdf_path, is_final=False))],
            "is_finished": True,
        }
