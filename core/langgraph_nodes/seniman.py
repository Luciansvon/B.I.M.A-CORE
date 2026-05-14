import asyncio
import logging
import time
import hashlib
from datetime import datetime
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from core.langgraph_nodes.state import BimaState, notify_progress
from core.langgraph_nodes.llm_config import get_langchain_llm
from core.langgraph_nodes.html_assets import (
    build_html_skeleton,
    detect_template,
    detect_theme,
    TEMPLATE_GUIDES,
)
from core.output_prune import prune_outputs

logger = logging.getLogger('bima_core')

OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

seniman_llm = get_langchain_llm("deepseek/deepseek-v4-flash")


from teams.t7_html_templates import render_template
import json
import re

async def seniman_node(state: BimaState) -> dict:
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")
    temp_data = state.get("temp_data", {})

    await notify_progress(
        state,
        f"🎨 *Tim Seniman lagi mendesain dokumen HTML...*"
    )

    search_data = temp_data.get("last_search_result", "")
    data_section = f"\n\n=== DATA UNTUK DIVISUALISASIKAN ===\n{search_data}\n=== AKHIR DATA ===" if search_data else ""

    # Upstream agent's polished output (manager, intel, atau arsip)
    prev_messages = state.get("messages", []) or []
    upstream_block = ""
    if prev_messages:
        last = prev_messages[-1]
        upstream_text = (getattr(last, "content", "") or str(last))[:2500]
        if upstream_text.strip():
            upstream_block = f"\n\n=== ANALISIS / OUTPUT TIM SEBELUMNYA ===\n{upstream_text}"

    # History fallback kalau user_request singkat (mungkin reply ke pertanyaan klarifikasi)
    history_block = ""
    if len(user_request.strip()) < 60:
        from memory.memory_engine import get_recent_context
        rc = get_recent_context(3)
        if rc and rc.strip() and "Belum ada histori" not in rc:
            history_block = f"\n\n=== HISTORI PERCAKAPAN TERAKHIR ===\n{rc}"

    logger.info(f"[LANGGRAPH SENIMAN] Generating JSON for HTML template...")

    system_prompt = f"""Kamu adalah Seniman/Designer AI dari B.I.M.A Core (Anisa).
Tugasmu: Buat dokumen HTML/Dashboard dengan merancang struktur datanya dalam format JSON.

{realtime_context}{history_block}{upstream_block}{data_section}

CATATAN: Kalau ada blok HISTORI atau ANALISIS TIM SEBELUMNYA, pakai itu untuk pahami subjek/konteks aslinya — terutama kalau permintaan Bima singkat atau sekadar jawaban preferensi.

PILIHAN TEMPLATE:
- "orbital"  : Dark dashboard premium, glassmorphism — untuk laporan data/analytics
- "chronicle": Editorial magazine, serif bold — untuk proposal klien/laporan panjang
- "forge"    : Neobrutalism tech, bold flat — untuk specs teknis/BOM/cutting list
- "paper"    : Print-first minimalist, A4 ready — untuk invoice/surat resmi/kontrak
- "terminal" : CLI aesthetic, monospace neon — untuk system log/technical report

FORMAT OUTPUT (HANYA JSON VALID, TANPA MARKDOWN, TANPA TEKS LAIN):
{{
    "template": "pilih_salah_satu_template_di_atas",
    "title": "Judul Utama Dokumen",
    "subtitle": "Subjudul (opsional)",
    "author": "Anisa (B.I.M.A Core)",
    "sections": [
        {{
            "heading": "Judul Bagian",
            "content": "Paragraf penjelasan yang detail dan substansial...",
            "list": ["Poin 1", "Poin 2"],
            "charts": [
                {{
                    "type": "bar",
                    "title": "Judul Chart",
                    "labels": ["Item 1", "Item 2"],
                    "datasets": [{{"label": "Data", "data": [10, 20]}}]
                }}
            ],
            "table": {{
                "headers": ["Kolom 1", "Kolom 2"],
                "rows": [["Nilai 1", "Nilai 2"]]
            }}
        }}
    ]
}}

ATURAN KETAT:
1. OUTPUT HARUS BERUPA JSON VALID! Jangan ada teks apa pun di luar JSON.
2. JANGAN gunakan ```json ... ```, langsung mulai dengan {{ dan akhiri dengan }}.
3. Pilih template yang paling cocok dengan konteks permintaan user.
4. Buat konten yang detail dan informatif (terutama jika ada data intel).
5. Chart dan tabel bersifat opsional, hanya gunakan jika ada data angka.
"""

    response = await asyncio.to_thread(
        seniman_llm.invoke,
        [SystemMessage(content=system_prompt), HumanMessage(content=user_request)]
    )

    output_text = response.content.strip()
    
    # Strip markdown if LLM still includes it
    if output_text.startswith("```"):
        output_text = re.sub(r"^```[a-z]*\n", "", output_text)
        output_text = re.sub(r"\n```$", "", output_text)
        output_text = output_text.strip()

    try:
        json_data = json.loads(output_text)
        template_used = json_data.get("template", "orbital")
        full_html = render_template(json_data)
    except Exception as e:
        logger.error(f"[LANGGRAPH SENIMAN] JSON Parse Error: {e}")
        # Fallback if LLM fails
        template_used = "orbital"
        full_html = render_template({
            "template": "orbital",
            "title": "Dokumen B.I.M.A Core",
            "sections": [{
                "heading": "Hasil Generate",
                "content": output_text
            }]
        })

    slug = hashlib.md5(user_request.encode()).hexdigest()[:8]
    filename = f"dokumen_{template_used}_{slug}_{int(time.time())}.html"
    filepath = OUTPUT_DIR / filename
    filepath.write_text(full_html, encoding="utf-8")
    prune_outputs(OUTPUT_DIR, "dokumen_*.html", keep=15)

    size_kb = filepath.stat().st_size // 1024
    logger.info(f"[LANGGRAPH SENIMAN] Saved: {filepath} ({size_kb} KB) [tpl={template_used}]")

    result = f"✅ HTML siap! (Template: {template_used.upper()})\nSUCCESS|{filepath}|{filename} ({size_kb} KB)"
    return {
        "messages": [AIMessage(content=result)],
        "is_finished": True
    }

