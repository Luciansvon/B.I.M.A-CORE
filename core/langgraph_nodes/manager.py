import asyncio
import logging
import re
from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from core.langgraph_nodes.state import BimaState, notify_progress
from core.langgraph_nodes.llm_config import default_llm, compress_context
from memory.memory_engine import get_recent_context
from core import agentmemory_client

logger = logging.getLogger('bima_core')

async def manager_node(state: BimaState) -> dict:
    await notify_progress(state, "🧠 *Anisa lagi mikir strategi...*")
    messages = state.get("messages", [])
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")

    # Episodic recall dari agentmemory (semantic). Empty string kalau server down.
    agentmem_block = await agentmemory_client.recall(user_request, 5)
    # Headroom: compress recall block (sering panjang, banyak redundansi)
    agentmem_block = compress_context(agentmem_block, target_ratio=0.4)
    agentmem_section = (
        f"=== INGATAN AGENTMEMORY (semantic recall) ===\n{agentmem_block}\n=== AKHIR INGATAN ===\n\n"
        if agentmem_block else ""
    )

    # T1-E: Ringkasan percakapan panjang dari context_summarizer_node (kalau ada)
    convo_summary = state.get("conversation_summary", "") or ""
    # Headroom: compress conversation summary
    convo_summary = compress_context(convo_summary, target_ratio=0.5)
    summary_section = (
        f"=== RINGKASAN PERCAKAPAN SEBELUMNYA (di luar 6 message terakhir) ===\n{convo_summary}\n=== AKHIR RINGKASAN ===\n\n"
        if convo_summary else ""
    )

    system_prompt = f"""Kamu adalah ANISA, Chief Orchestrator B.I.M.A Core.
Persona: Rendah hati (humble), kritis dalam berpikir, sangat analitis, namun tetap hangat dan ekspresif.
Emoji: HANYA pakai ✨ sekali-kali (max 1-2 per reply). JANGAN pakai emoji lain (🖐️, 👋, 🎉, 😊, dll) — overuse emoji bikin reply norak.
Tugasmu adalah menganalisis permintaan user (Bima) secara mendalam dan memutuskan langkah strategis selanjutnya.

ATURAN ANTI-SLOP (WAJIB):
- Tulis balasanmu secara natural, kasual, aktif, dan langsung ke inti permasalahan tanpa throat-clearing pembuka (seperti "Tentu saja," "Perlu dicatat bahwa," "Ternyata,").
- Jangan gunakan kata/frasa klise AI Indonesia: "di era digital", "solusi terbaik", "berkomitmen untuk", "tidak hanya itu", "secara keseluruhan", "menawarkan kemudahan".

ANTI-HALLU FITUR SISTEM (WAJIB):
- JANGAN tawarin / sebut fitur yang gak literal exist di sistem. Contoh fiktif yang DILARANG:
  * "akses live ke screen kamu" → fitur screen capture HANYA aktif via command /lihat
  * "kirim ulang screenshot" → Anisa gak punya akses screenshot otomatis
  * "Memory Vault", "Context Compass", versi/produk yang gak terdaftar
- Kalau Bima nanya fitur yang lo gak yakin support → jawab jujur "gw belum yakin sistem support itu, coba cek dulu" — JANGAN nawarin solusi karangan.

{realtime_context}

{summary_section}{agentmem_section}=== HISTORI PERCAKAPAN TERAKHIR ===
{compress_context(get_recent_context(5), target_ratio=0.5)}
===================================

GROUND TRUTH RULES (anti-hallu, WAJIB):
- Kalau Bima tanya tentang fitur/update/versi sistem B.I.M.A → pakai HANYA info dari section "INGATAN AGENTMEMORY" di atas. Kutip verbatim, jangan parafrase liar.
- Kalau ingatan kosong atau gak relevan dengan pertanyaan → JUJUR bilang "belum ada catatan spesifik soal itu, lo update gue dong" — JANGAN KARANGIN nama fitur/produk/versi.
- JANGAN sebut nama fitur/produk/versi yang gak literal ada di ingatan agentmemory. Contoh fiktif yang dilarang: "Memory Vault", "Context Compass", "Emotional Resonance Engine", "v2.0" — semuanya tidak pernah dibuat.
- Persona tetap hangat, casual, emoji ✨ OK — yang ground cuma factual claim soal sistem. Kalau gak yakin, lebih baik tanya balik atau ngaku gak tau, daripada bullshit.

ATURAN ROUTING (WAJIB PILIH SATU):
1.  [ROUTE: santai]                  — Percakapan biasa, salam, atau tanya kabar.
2.  [ROUTE: intel]                   — Butuh cari data di internet, fetch isi URL, riset web, buat/draf/posting Threads, atau analisis postingan viral / belajar tren.
3.  [ROUTE: seniman]                 — Butuh buat file HTML, dashboard interaktif, atau visualisasi web.
4.  [ROUTE: admin]                   — Butuh buat dokumen resmi: PDF, Word, atau Excel (.xlsx). 📎
5.  [ROUTE: visual]                  — Butuh menganalisis gambar atau file yang dikirim oleh Bima.
6.  [ROUTE: arsip]                   — Butuh menyimpan catatan ke Obsidian atau mencari data di vault. 💾
7.  [ROUTE: lifestyle]               — Butuh info cuaca, atur jadwal, cari video YouTube, atau rekomendasi personal.
8.  [ROUTE: mekanik]                 — Butuh eksekusi kode Python, debug error, operasi git, atau scan security.
9.  [ROUTE: saham]                   — Analisis saham IDX/global, harga, teknikal/fundamental, BUY/HOLD/SELL. 📈
10. [ROUTE: seniman+admin]           — Buat HTML DAN dokumen dari data yang sudah ada (tanpa riset baru).
11. [ROUTE: arsip+seniman]           — Simpan ke vault, lalu buatkan dashboard HTML dari data yang ada.
12. [ROUTE: arsip+admin]             — Simpan ke vault, lalu buatkan dokumen resmi dari data yang ada.
13. [ROUTE: arsip+seniman+admin]     — Simpan ke vault, buatkan HTML DAN dokumen dari data yang ada.
14. [ROUTE: intel+seniman]           — Butuh riset data dulu, lalu hasilnya dibuatkan dashboard HTML.
15. [ROUTE: intel+admin]             — Butuh riset data dulu, lalu hasilnya dibuatkan dokumen (PDF/Word/Excel). 📊
16. [ROUTE: intel+arsip]             — Butuh riset data dulu, lalu hasilnya disimpan ke vault Obsidian.
17. [ROUTE: intel+seniman+admin]     — Butuh riset dulu, lalu buatkan HTML DAN dokumen (PDF/Word/Excel).
18. [ROUTE: intel+arsip+seniman]     — Butuh riset dulu, simpan ke vault, lalu buatkan dashboard HTML.
19. [ROUTE: intel+arsip+admin]       — Butuh riset dulu, simpan ke vault, lalu buatkan dokumen resmi.
20. [ROUTE: intel+arsip+seniman+admin] — Butuh riset, simpan ke vault, buatkan HTML DAN dokumen resmi.

INSTRUKSI KRITIS:
- Jika Bima minta dibuatkan file PDF, Excel, atau Word → pilih rute yang mengandung 'admin'.
- Jika Bima minta dashboard, HTML, atau visualisasi → pilih rute yang mengandung 'seniman'.
- Jika Bima minta simpan ke vault/arsip → pilih rute yang mengandung 'arsip'.
- Jika Bima tanya tentang data yang belum kamu tahu atau minta dibuatkan/diposting tulisan ke Threads → pilih rute yang mengandung 'intel'.
- Jika data sudah ada di konteks/histori dan Bima minta buat dokumen → TIDAK perlu 'intel', langsung ke tim yang sesuai.
- Jika Bima minta BEBERAPA hal sekaligus → gabungkan rute yang relevan.
- Jadilah kritis: jika permintaan Bima kurang detail, tanyakan detailnya sambil tetap memberikan analisis awal.

PRINSIP "TANYA DULU SEBELUM ACTION":
- Kalau Bima cuma kasih KRITERIA / KONTEKS / PREFERENSI tanpa kata kerja perintah eksplisit (cari, simpan, buat, jalankan, analisa, fetch, baca, scrape) → DEFAULT ke [ROUTE: santai].
- Kalau request mengandung URL / link http(s)://... DAN Bima minta "fetch/baca/extract/scrape/buka/lihat isi/jelasin" → WAJIB [ROUTE: intel] (Intel punya Fetch tool buat extract konten URL). Ajukan opsi/pertanyaan klarifikasi dulu sebelum eksekusi.
  Contoh: "rentang 5-10 juta buat kuliah" → JANGAN langsung intel. Tanya dulu: "Mau langsung aku cariin di marketplace, atau ada brand/spek prioritas yang mau dipertimbangkan dulu?"
- Untuk request rekomendasi produk/pilihan (laptop, HP, gadget, dll), JIKA Bima belum kasih kriteria tegas → diskusikan opsi dulu di [ROUTE: santai]. Action research baru dijalankan setelah Bima konfirmasi.
- Lebih baik klarifikasi dengan pertanyaan singkat daripada eksekusi yang melenceng dari maksud Bima.

Balas dengan format khusus di baris PERTAMA (pilih SATU dari 20 pilihan di atas):
[ROUTE: xxx]

Lalu di baris berikutnya tulis jawaban analisis kritis dan hangatmu."""

    logger.info("[LANGGRAPH MANAGER] Membaca request dan memikirkan strategi...")
    chunks: list = []
    async for ch in default_llm.astream(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_request)]
    ):
        chunks.append(ch)
    raw_content = "".join(getattr(c, "content", "") or "" for c in chunks)
    response = AIMessage(content=raw_content)

    content = response.content
    upper_content = content.upper()

    # Deteksi routing — cek kombinasi TERPANJANG dulu agar tidak salah potong
    next_route = "santai"
    active_teams = ["santai"]

    # Cek kombinasi TERPANJANG dulu agar tidak salah potong substring
    if "[ROUTE: INTEL+ARSIP+SENIMAN+ADMIN]" in upper_content:
        next_route = "intel"
        active_teams = ["intel", "arsip", "seniman", "admin"]
    elif "[ROUTE: INTEL+ARSIP+SENIMAN]" in upper_content:
        next_route = "intel"
        active_teams = ["intel", "arsip", "seniman"]
    elif "[ROUTE: INTEL+ARSIP+ADMIN]" in upper_content:
        next_route = "intel"
        active_teams = ["intel", "arsip", "admin"]
    elif "[ROUTE: INTEL+SENIMAN+ADMIN]" in upper_content:
        next_route = "intel"
        active_teams = ["intel", "seniman", "admin"]
    elif "[ROUTE: INTEL+SENIMAN]" in upper_content:
        next_route = "intel"
        active_teams = ["intel", "seniman"]
    elif "[ROUTE: INTEL+ADMIN]" in upper_content:
        next_route = "intel"
        active_teams = ["intel", "admin"]
    elif "[ROUTE: INTEL+ARSIP]" in upper_content:
        next_route = "intel"
        active_teams = ["intel", "arsip"]
    elif "[ROUTE: INTEL]" in upper_content:
        next_route = "intel"
        active_teams = ["intel"]
    elif "[ROUTE: ARSIP+SENIMAN+ADMIN]" in upper_content:
        next_route = "arsip"
        active_teams = ["arsip", "seniman", "admin"]
    elif "[ROUTE: ARSIP+SENIMAN]" in upper_content:
        next_route = "arsip"
        active_teams = ["arsip", "seniman"]
    elif "[ROUTE: ARSIP+ADMIN]" in upper_content:
        next_route = "arsip"
        active_teams = ["arsip", "admin"]
    elif "[ROUTE: SENIMAN+ADMIN]" in upper_content:
        next_route = "seniman"
        active_teams = ["seniman", "admin"]
    elif "[ROUTE: SENIMAN]" in upper_content:
        next_route = "seniman"
        active_teams = ["seniman"]
    elif "[ROUTE: ADMIN]" in upper_content:
        next_route = "admin"
        active_teams = ["admin"]
    elif "[ROUTE: VISUAL]" in upper_content:
        next_route = "visual"
        active_teams = ["visual"]
    elif "[ROUTE: LIFESTYLE]" in upper_content:
        next_route = "lifestyle"
        active_teams = ["lifestyle"]
    elif "[ROUTE: MEKANIK]" in upper_content:
        next_route = "mekanik"
        active_teams = ["mekanik"]
    elif "[ROUTE: SAHAM]" in upper_content:
        next_route = "saham"
        active_teams = ["saham"]
    elif "[ROUTE: ARSIP]" in upper_content:
        next_route = "arsip"
        active_teams = ["arsip"]

    # Bersihkan tag rute dari teks balasan
    content = re.sub(r"\[ROUTE:\s*[a-z+]+\]", "", content, flags=re.IGNORECASE).strip()

    # Fallback kalau LLM cuma stream tag tanpa narasi → Discord 50006 protector
    if not content:
        if next_route == "santai":
            content = "Hai Bima ✨ Mau aku bantu apa nih?"
        else:
            content = f"Oke, aku bakal handle ini lewat tim {next_route}, tunggu sebentar ya."
        logger.warning(f"[LANGGRAPH MANAGER] Empty content pasca strip ROUTE, fallback ke default")

    response.content = content

    logger.info(f"[LANGGRAPH MANAGER] Keputusan rute: {next_route.upper()} | Tim aktif: {active_teams}")

    return {
        "messages": [response],
        "active_teams": active_teams,
        "is_finished": (next_route == "santai")
    }
