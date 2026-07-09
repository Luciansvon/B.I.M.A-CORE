"""DeslopTool — Menyaring draf tulisan agar terbebas dari pola bahasa AI yang kaku (AI Slop)."""
from __future__ import annotations

import logging
from crewai.tools import BaseTool

logger = logging.getLogger("bima_core")


class DeslopTool(BaseTool):
    name: str = "Deslop Tool"
    description: str = (
        "Revisi draf tulisan (prose/pesan/postingan) agar terdengar lebih natural, "
        "aktif, langsung ke poin, dan terbebas dari gaya bahasa khas AI (AI tells/filler). "
        "Input: draft_text (str). "
        "Output: Teks hasil revisi yang bersih."
    )

    def _run(self, draft_text: str) -> str:
        draft_text = (draft_text or "").strip()
        if not draft_text:
            return ""

        try:
            from core.langgraph_nodes.llm_config import default_llm
            from langchain_core.messages import SystemMessage, HumanMessage
        except ImportError as e:
            logger.error(f"[DESLOP_TOOL] Gagal mengimpor modul LLM/LangChain: {e}")
            return draft_text

        system_prompt = """Kamu adalah Editor Tulisan Profesional. Tugasmu adalah menghilangkan pola penulisan robotik/AI (AI tells / slop) dari teks masukan agar terdengar alami, ditulis oleh manusia asli, dan padat.

ATURAN DAN PANDUAN PENYARINGAN (ANTI-SLOP):

1. HAPUS PEMBUKA BASA-BASI (Throat-Clearing Openers):
   - Contoh: "Here's the thing:", "Let me be clear", "The truth is,", "It turns out", "Perlu diingat bahwa...", "Tentu saja,", "Seperti yang kita ketahui...", "Berikut adalah..."
   - Potong kalimat pengantar tersebut dan langsung tulis inti poinnya.

2. HAPUS KATA PENEGAS KLISHE (Emphasis Crutches):
   - Contoh: "Full stop.", "Let that sink in.", "Make no mistake", "This matters because...", "Penting sekali untuk...", "Gak main-main,"

3. GANTI JARGON BISNIS / AI SPEAK:
   - Ganti "Navigate challenges" -> "Handle / address / hadapi"
   - Ganti "Unpack" -> "Explain / jelaskan"
   - Ganti "Lean into" -> "Accept / pelajari / peluk"
   - Ganti "Deep dive" -> "Analysis / ulasan mendalam"
   - Ganti "Game-changer" -> "Significant / penting"
   - Ganti "Double down" -> "Commit / tingkatkan"
   - Ganti "Circle back" -> "Return to / bahas lagi"

4. BANNED WORDS INDONESIA (AI Tells Lokal):
   - Sangat dilarang keras menulis frasa:
     * "Di era digital yang berkembang pesat ini..." (atau variasi era digital)
     * "Berkomitmen untuk memberikan solusi terbaik..."
     * "Menawarkan berbagai kemudahan..."
     * "Secara keseluruhan..." / "Pada intinya..." (sebagai pembuka kesimpulan klise)
     * "Tidak hanya itu..."
     * "Menjelajahi potensi / menjelajahi tantangan"

5. GUNAKAN KALIMAT AKTIF (Active Voice):
   - Pastikan subjeknya manusia atau pelaku aktif yang melakukan sesuatu, bukan objek pasif.

6. HINDARI KONTRAS BINER DRAMATIS:
   - Hindari struktur: "Bukan karena X, melainkan Y" atau "X bukan masalahnya, Y yang masalah".
   - Tulis Y secara langsung. Hilangkan runway penyangkalan di awal.

7. VARIATION & RHYTHM:
   - Campurkan kalimat pendek dan panjang. Jangan biarkan ritme tulisan terlalu seragam atau monoton.
   - Jangan gunakan tanda hubung em dash (—) berulang-ulang atau staccato yang dibuat-buat ("Satu kata. Dahsyat.").

Cukup kembalikan hasil revisi teks final. JANGAN memberikan kata pengantar, penjelasan perubahan, atau tanda kutip pembungkus."""

        try:
            resp = default_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Teks Draf:\n{draft_text}")
            ])
            cleaned = resp.content.strip()
            # Jika respon diapit kutipan oleh LLM, bersihkan
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1].strip()
            elif cleaned.startswith("'") and cleaned.endswith("'"):
                cleaned = cleaned[1:-1].strip()
            return cleaned
        except Exception as e:
            logger.error(f"[DESLOP_TOOL] Gagal memanggil LLM: {e}")
            return draft_text
