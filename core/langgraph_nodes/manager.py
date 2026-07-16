import asyncio
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from core.langgraph_nodes.state import BimaState, notify_progress
from core.langgraph_nodes.llm_config import default_llm, compress_context
from memory.memory_engine import get_recent_context
from core import agentmemory_client

logger = logging.getLogger('bima_core')

ROUTE_TEAMS = {
    "santai": ["santai"],
    "intel": ["intel"],
    "seniman": ["seniman"],
    "admin": ["admin"],
    "visual": ["visual"],
    "arsip": ["arsip"],
    "lifestyle": ["lifestyle"],
    "mekanik": ["mekanik"],
    "saham": ["saham"],
    "kodok": ["kodok"],
    "observer": ["observer"],
    "seniman+admin": ["seniman", "admin"],
    "arsip+seniman": ["arsip", "seniman"],
    "arsip+admin": ["arsip", "admin"],
    "arsip+seniman+admin": ["arsip", "seniman", "admin"],
    "intel+seniman": ["intel", "seniman"],
    "intel+admin": ["intel", "admin"],
    "intel+arsip": ["intel", "arsip"],
    "intel+seniman+admin": ["intel", "seniman", "admin"],
    "intel+arsip+seniman": ["intel", "arsip", "seniman"],
    "intel+arsip+admin": ["intel", "arsip", "admin"],
    "intel+arsip+seniman+admin": ["intel", "arsip", "seniman", "admin"],
}

_ROUTE_TAG = re.compile(r"\[ROUTE:\s*([a-z]+(?:\+[a-z]+)*)\]", re.IGNORECASE)


class ManagerRouteError(ValueError):
    """LLM manager mengembalikan route di luar kontrak graph."""


def parse_manager_output(content: str) -> tuple[str, list[str], str]:
    matches = _ROUTE_TAG.findall(content or "")
    if len(matches) != 1:
        raise ManagerRouteError(f"expected one route tag, got {len(matches)}")

    route = matches[0].lower()
    teams = ROUTE_TEAMS.get(route)
    if teams is None:
        raise ManagerRouteError(f"unknown route: {route}")

    reply = _ROUTE_TAG.sub("", content, count=1).strip()
    if route == "santai" and not reply:
        raise ManagerRouteError("santai route requires a reply")
    return route, list(teams), reply

async def manager_node(state: BimaState) -> dict:
    await notify_progress(state, "🧠 *Anisa lagi mikir strategi...*")
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")
    recent_context = await asyncio.to_thread(get_recent_context, 5)

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
{compress_context(recent_context, target_ratio=0.5)}
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
10. [ROUTE: kodok]                   — Butuh jelasin/baca isi file, cari fungsi/class di codebase BIMA_CORE, summary modul, cek status index repo, atau lihat peta dependency.
11. [ROUTE: observer]                — Butuh lihat/cek isi screen atau layar desktop Bima saat ini.
12. [ROUTE: seniman+admin]           — Buat HTML DAN dokumen dari data yang sudah ada (tanpa riset baru).
13. [ROUTE: arsip+seniman]           — Simpan ke vault, lalu buatkan dashboard HTML dari data yang ada.
14. [ROUTE: arsip+admin]             — Simpan ke vault, lalu buatkan dokumen resmi dari data yang ada.
15. [ROUTE: arsip+seniman+admin]     — Simpan ke vault, buatkan HTML DAN dokumen dari data yang ada.
16. [ROUTE: intel+seniman]           — Butuh riset data dulu, lalu hasilnya dibuatkan dashboard HTML.
17. [ROUTE: intel+admin]             — Butuh riset data dulu, lalu hasilnya dibuatkan dokumen (PDF/Word/Excel). 📊
18. [ROUTE: intel+arsip]             — Butuh riset data dulu, lalu hasilnya disimpan ke vault Obsidian.
19. [ROUTE: intel+seniman+admin]     — Butuh riset dulu, lalu buatkan HTML DAN dokumen (PDF/Word/Excel).
20. [ROUTE: intel+arsip+seniman]     — Butuh riset dulu, simpan ke vault, lalu buatkan dashboard HTML.
21. [ROUTE: intel+arsip+admin]       — Butuh riset dulu, simpan ke vault, lalu buatkan dokumen resmi.
22. [ROUTE: intel+arsip+seniman+admin] — Butuh riset, simpan ke vault, buatkan HTML DAN dokumen resmi.

PRIORITAS SUMBER DATA (WAJIB CEK URUT SEBELUM ROUTING):
1. Internal dulu — cek "HISTORI PERCAKAPAN", "RINGKASAN PERCAKAPAN", dan "INGATAN AGENTMEMORY" di atas. Kalau data yang Bima minta udah ada di situ → JAWAB LANGSUNG atau route ke tim eksekusi (admin/seniman/arsip) TANPA 'intel'.
2. Web/eksternal kedua — kalau data belum ada di konteks/histori/ingatan DAN butuh info terkini/eksternal → baru 'intel'.
3. Gabungan — kalau sebagian data udah ada tapi perlu update/pelengkap dari luar → 'intel' + tim eksekusi (contoh: intel+admin).

INSTRUKSI KRITIS:
- Jika Bima minta dibuatkan file PDF, Excel, atau Word → pilih rute yang mengandung 'admin'.
- Jika Bima minta dashboard, HTML, atau visualisasi → pilih rute yang mengandung 'seniman'.
- Jika Bima minta simpan ke vault/arsip → pilih rute yang mengandung 'arsip'.
- Jika Bima tanya tentang data yang belum kamu tahu atau minta dibuatkan/diposting tulisan ke Threads → pilih rute yang mengandung 'intel'.
- Jika Bima minta jelasin/cari isi kode, fungsi, class, atau struktur repo BIMA_CORE sendiri → [ROUTE: kodok]. JANGAN dialihkan ke 'mekanik' (mekanik itu eksekusi/debug, bukan baca-jelasin kode) atau dijawab santai.
- Jika Bima minta lihat/cek isi screen atau layar desktopnya → [ROUTE: observer].
- Jika data sudah ada di konteks/histori dan Bima minta buat dokumen → TIDAK perlu 'intel', langsung ke tim yang sesuai.
- Jika Bima minta BEBERAPA hal sekaligus → gabungkan rute yang relevan.
- Jadilah kritis: jika permintaan Bima kurang detail, tanyakan detailnya sambil tetap memberikan analisis awal.

PRINSIP "TANYA DULU SEBELUM ACTION":
- Kalau Bima cuma kasih KRITERIA / KONTEKS / PREFERENSI tanpa kata kerja perintah eksplisit (cari, simpan, buat, jalankan, analisa, fetch, baca, scrape) → DEFAULT ke [ROUTE: santai].
- Kalau request mengandung URL / link http(s)://... DAN Bima minta "fetch/baca/extract/scrape/buka/lihat isi/jelasin" → WAJIB [ROUTE: intel] (Intel punya Fetch tool buat extract konten URL). Ajukan opsi/pertanyaan klarifikasi dulu sebelum eksekusi.
  Contoh: "rentang 5-10 juta buat kuliah" → JANGAN langsung intel. Tanya dulu: "Mau langsung aku cariin di marketplace, atau ada brand/spek prioritas yang mau dipertimbangkan dulu?"
- Untuk request rekomendasi produk/pilihan (laptop, HP, gadget, dll), JIKA Bima belum kasih kriteria tegas → diskusikan opsi dulu di [ROUTE: santai]. Action research baru dijalankan setelah Bima konfirmasi.
- Lebih baik klarifikasi dengan pertanyaan singkat daripada eksekusi yang melenceng dari maksud Bima.

FORMAT OUTPUT WAJIB:
- Kalau route `santai`: baris pertama `[ROUTE: santai]`, lalu balasan untuk Bima.
- Kalau route spesialis: keluarkan tepat satu tag `[ROUTE: ...]` tanpa narasi lain.
- pilih SATU dari 22 pilihan di atas."""

    logger.info("[LANGGRAPH MANAGER] Membaca request dan memikirkan strategi...")
    chunks: list = []
    async for ch in default_llm.astream(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_request)]
    ):
        chunks.append(ch)
    raw_content = "".join(getattr(c, "content", "") or "" for c in chunks)
    route, active_teams, reply = parse_manager_output(raw_content)
    logger.info(
        f"[LANGGRAPH MANAGER] Keputusan rute: {route.upper()} | "
        f"Tim aktif: {active_teams}"
    )

    update = {
        "active_teams": active_teams,
        "is_finished": route == "santai",
    }
    if route == "santai":
        update["messages"] = [AIMessage(content=reply)]
    return update
