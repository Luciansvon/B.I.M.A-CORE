import logging
import asyncio
import re
from pathlib import Path
from langchain_core.messages import AIMessage
from core.langgraph_nodes.state import BimaState, get_current_upstream_text, notify_progress
from teams.t4_admin import admin_agent, detect_style, detect_format, STYLES
from crewai import Task, Crew

logger = logging.getLogger('bima_core')

async def admin_node(state: BimaState) -> dict:
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")
    temp_data = state.get("temp_data", {})

    # Auto-detect style + format dari permintaan
    detected_style = detect_style(user_request)
    detected_format = detect_format(user_request)
    style_info = STYLES[detected_style]

    await notify_progress(
        state,
        f"📄 *Tim Admin lagi bikin {detected_format.upper()} ({style_info['label']})...*"
    )

    search_data = temp_data.get("last_search_result", "")
    data_context = f"\n\n=== DATA UNTUK DIJADIKAN DOKUMEN ===\n{search_data}\n=== AKHIR DATA ===" if search_data else ""

    # Upstream agent's polished output from this graph run.
    upstream_text = get_current_upstream_text(state, "admin")
    upstream_block = ""
    if upstream_text:
        upstream_block = f"\n\n=== ANALISIS / OUTPUT TIM SEBELUMNYA ===\n{upstream_text}"

    # History fallback kalau user_request singkat
    history_block = ""
    if len(user_request.strip()) < 60:
        from memory.memory_engine import get_recent_context
        rc = get_recent_context(3)
        if rc and rc.strip() and "Belum ada histori" not in rc:
            history_block = f"\n\n=== HISTORI PERCAKAPAN TERAKHIR ===\n{rc}"

    logger.info(f"[LANGGRAPH ADMIN] Style={detected_style} | Format={detected_format} | Menyiapkan...")

    task = Task(
        description=f"""{realtime_context}{history_block}{upstream_block}{data_context}

        Permintaan Bima: '{user_request}'

        CATATAN: Kalau ada blok HISTORI atau ANALISIS TIM SEBELUMNYA, pakai itu untuk pahami subjek/konteks aslinya — terutama kalau permintaan Bima singkat atau sekadar jawaban preferensi.

        TEBAKAN AWAL DARI KEYWORD MATCHING (fallback -- BUKAN keputusan final):
        - Format file: {detected_format.upper()}
        - Gaya tulisan: {detected_style.upper()} ({style_info['tone']})
        Keyword matching di atas cuma baca kata literal di permintaan, gak baca konteks.
        PRIORITASKAN penalaran kamu sendiri atas HISTORI/ANALISIS TIM SEBELUMNYA/DATA di atas
        kalau itu kasih petunjuk lebih akurat soal format & gaya yang pas -- baru pakai tebakan
        di atas kalau kamu beneran gak punya cukup konteks buat mutusin sendiri.

        TUGASMU:
        1. Pakai tool yang sesuai:
           - PDF   → PDFGeneratorTool (cocok untuk laporan, proposal, resume, surat, certificate)
           - Word  → WordGeneratorTool (cocok untuk dokumen yang masih bisa diedit Bima)
           - Excel → ExcelGeneratorTool (cocok untuk tabel data, rekap, perbandingan angka)
        2. WAJIB sertakan "style" (formal | semi_formal | informal | akademik) di JSON input tool -- supaya warna, tone, dan layout sesuai
        3. Konten WAJIB substantial:
           - PDF/Word: minimal 3-5 sections, setiap section punya heading + content (paragraph)
           - PDF: kalau >3 sections, set "cover": true dan "toc": true
           - Excel: minimal 5 baris data dalam tiap sheet
        4. Tone tulisan menyesuaikan style:
           - Formal      → baku, resmi, struktur kaku (surat dinas, kontrak, laporan resmi)
           - Semi-Formal → sopan tapi luwes, ramah (tutorial, dokumentasi teknis, panduan)
           - Informal    → santai, ekspresif, boleh non-baku (blog, cerita, chat santai)
           - Akademik    → sangat formal, objektif, impersonal (skripsi, tesis, jurnal ilmiah)

        ATURAN TABEL (WAJIB jika ada tabel di section):
        - Jangan masukkan teks panjang dalam satu cell — pecah jadi beberapa kolom atau singkat jadi frasa.
        - Maksimal 5-6 kolom per tabel (lebih dari itu tabel jadi sempit & berantakan).
        - Tiap kata WAJIB dipisah spasi — JANGAN tulis "Rp50000" tapi "Rp 50.000". JANGAN "Tahun2026" tapi "Tahun 2026".
        - Header tabel pakai Title Case singkat (mis. "Nama Material", "Harga (Rp)", "Supplier").
        - Cell value text idealnya <= 25 karakter. Kalau perlu lebih panjang, taruh di paragraf section, bukan tabel.

        ATURAN DAFTAR PUSTAKA (WAJIB jika konten bersifat informatif/riset/edukatif/jurnal):
        - Tambahkan section terakhir berjudul "Daftar Pustaka" atau "Referensi" SEBELUM kesimpulan.
        - PDF/Word: pakai field "references" di JSON (list of {{"text": "...", "url": "https://..."}}).
        - Excel: bikin sheet terpisah bernama "Referensi" dengan kolom [Nomor, Sumber, URL].
        - URL WAJIB valid & verifiable: Wikipedia, situs resmi (.gov, .edu, .org), jurnal open-access (DOI.org, arxiv.org),
          dokumentasi resmi vendor. JANGAN mengarang URL atau judul paper.
        - Kalau tidak yakin link spesifiknya akurat → pakai homepage situs sumbernya saja
          (mis. https://en.wikipedia.org daripada link artikel spesifik yang dikarang).

        5. Pastikan file tersimpan dengan benar.

        WAJIB FINAL OUTPUT: SUCCESS|path_file|keterangan ATAU FAILED|alasan""",
        expected_output="Path file dalam format SUCCESS|path|keterangan.",
        agent=admin_agent
    )

    crew = Crew(
        agents=[admin_agent],
        tasks=[task],
        verbose=True
    )

    hasil_raw = await asyncio.to_thread(crew.kickoff)
    hasil_str = str(hasil_raw)

    logger.info(f"[LANGGRAPH ADMIN] Output raw: {hasil_str[:200]}...")

    success_match = re.search(r'SUCCESS\|([^\|\n\r]+)\|([^\n\r]+)', hasil_str)
    failed_match = re.search(r'FAILED\|([^\n\r]+)', hasil_str)

    if success_match:
        file_path = success_match.group(1).strip()
        keterangan = success_match.group(2).strip()
        filename = Path(file_path).name
        ext = Path(file_path).suffix.upper().lstrip('.')

        response_content = f"""✅ Dokumen **{ext}** berhasil dibuat, Bima!

📄 **{filename}**
{keterangan}

File sudah siap dikirim. 📎
SUCCESS|{file_path}|{keterangan}"""
        logger.info(f"[LANGGRAPH ADMIN] Berhasil: {file_path}")

    elif failed_match:
        error = failed_match.group(1).strip()
        response_content = f"❌ Maaf Bima, gagal membuat dokumen:\n```\n{error}\n```"
        logger.error(f"[LANGGRAPH ADMIN] Gagal: {error}")

    else:
        response_content = hasil_str
        logger.warning("[LANGGRAPH ADMIN] Format hasil tidak dikenal dari CrewAI")

    return {
        "messages": [AIMessage(content=response_content)],
        "is_finished": True
    }
