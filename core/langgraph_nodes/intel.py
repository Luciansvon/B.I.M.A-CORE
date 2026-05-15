import asyncio
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from core.langgraph_nodes.state import BimaState, notify_progress
from core.langgraph_nodes.llm_config import default_llm
from teams.t5_intel import SmartSearchTool
from tools.browser_use_tool import BrowserUseTool
from memory.memory_engine import get_recent_context

logger = logging.getLogger('bima_core')

search_tool = SmartSearchTool()
browser_tool = BrowserUseTool()

# Trigger short-circuit ke BrowserUseTool: pesan punya URL https?:// PLUS verb interaktif.
# Pattern: cek URL eksplisit AND minimal salah satu verb di list.
_URL_PATTERN = re.compile(r'https?://[^\s\'"<>]+', re.IGNORECASE)
_INTERACTIVE_VERBS = re.compile(
    r'\b(brows\w*|buka|navigasi\w*|masuk\s+ke|login(?:\s+ke)?|klik\w*|isi\s+form|scrape|scrap\w+|extract\s+isi|scroll\w*|interact\w*|fetch|live\s+brows\w*|cek)\b',
    re.IGNORECASE,
)

# Force-trigger pattern — frasa yang EKSPLISIT minta browser-use. Kalau match,
# langsung fire BrowserUseTool walau gak ada URL / site di catalog.
# Agent natural-language yang figure out target dari task.
_FORCE_BROWSER = re.compile(
    r'\b(live\s+brows\w*|browser\s+use\b|browser\s+automat\w*|pake?\s+browser|pakai\s+browser|use\s+browser)\b',
    re.IGNORECASE,
)

# Site catalog untuk auto-fill URL — kalau user mention site name + verb interaktif
# (tanpa kasih URL lengkap), kita resolve ke URL search/home dari catalog ini.
# Tuple: (pattern_regex, url_dengan_query_template, url_tanpa_query_fallback).
# Multi-word patterns DULU (tiktok shop, github trending) supaya prioritas match lebih spesifik.
_SITE_CATALOG = [
    (re.compile(r'\btiktok\s*shop\b', re.IGNORECASE),
     'https://www.tiktok.com/shop/search?query={q}', 'https://www.tiktok.com/shop'),
    (re.compile(r'\bgithub\s+trending\b', re.IGNORECASE),
     None, 'https://github.com/trending'),
    (re.compile(r'\bhugging\s*face\b', re.IGNORECASE),
     'https://huggingface.co/models?search={q}', 'https://huggingface.co/models'),
    (re.compile(r'\b(hackernews|hacker\s*news|ycombinator)\b', re.IGNORECASE),
     None, 'https://news.ycombinator.com'),
    # Marketplace: ALWAYS pakai homepage (no direct /search URL).
    # Direct URL search trigger anti-bot karena bypass XHR/cookie SPA frontend.
    # Agent harus navigate via UI: klik search bar → ketik → enter.
    (re.compile(r'\btokopedia\b', re.IGNORECASE),
     None, 'https://www.tokopedia.com'),
    (re.compile(r'\bshopee\b', re.IGNORECASE),
     None, 'https://shopee.co.id'),
    (re.compile(r'\blazada\b', re.IGNORECASE),
     None, 'https://www.lazada.co.id'),
    (re.compile(r'\bbukalapak\b', re.IGNORECASE),
     None, 'https://www.bukalapak.com'),
    (re.compile(r'\bgithub\b', re.IGNORECASE),
     'https://github.com/search?q={q}', 'https://github.com'),
    (re.compile(r'\breddit\b', re.IGNORECASE),
     'https://www.reddit.com/search/?q={q}', 'https://www.reddit.com'),
    (re.compile(r'\byoutube\b', re.IGNORECASE),
     'https://www.youtube.com/results?search_query={q}', 'https://www.youtube.com'),
    (re.compile(r'\bcoingecko\b', re.IGNORECASE),
     None, 'https://www.coingecko.com'),
    (re.compile(r'\b(twitter|x\.com)\b', re.IGNORECASE),
     'https://x.com/search?q={q}', 'https://x.com'),
]

# Stopwords yang di-strip pas extract query dari text (id + en mix)
_QUERY_STOPWORDS = {
    'ke', 'di', 'dan', 'untuk', 'cari', 'carikan', 'produk', 'keyword', 'about', 'tentang',
    'top', 'terbaru', 'trending', 'best', 'and', 'with', 'for', 'in', 'on', 'at', 'the',
    'a', 'an', 'gw', 'gua', 'aku', 'lo', 'lu', 'kamu', 'plis', 'tolong', 'donk', 'dong',
    'ya', 'sih', 'yang', 'itu', 'ini', 'aja', 'doang', 'live', 'real', 'time', 'realtime',
    'browse', 'browsing', 'scrape', 'scraping', 'fetch', 'buka', 'cek', 'check', 'lihat',
}


def _extract_query(text: str, site_match: 're.Match') -> str:
    """Strip site name DULU (pakai original indices), terus verb, terus stopwords. Sisa = keyword."""
    # Order penting: site removal pakai indices dari original text, jadi harus first
    cleaned = text[:site_match.start()] + ' ' + text[site_match.end():]
    cleaned = _INTERACTIVE_VERBS.sub(' ', cleaned)
    tokens = [t for t in re.split(r'\W+', cleaned) if t and t.lower() not in _QUERY_STOPWORDS]
    return ' '.join(tokens[:6]).strip()


def _autofill_url(text: str) -> str | None:
    """Kalau text mention site populer (tanpa URL lengkap), return URL hasil resolve.
    None = no recognized site."""
    if not text:
        return None
    for pattern, with_q, without_q in _SITE_CATALOG:
        m = pattern.search(text)
        if not m:
            continue
        if not with_q:
            return without_q
        query = _extract_query(text, m)
        if not query:
            return without_q
        from urllib.parse import quote_plus
        return with_q.format(q=quote_plus(query))
    return None


async def intel_node(state: BimaState) -> dict:
    await notify_progress(state, "🔍 *Tim Intel lagi cari info di internet...*")
    user_request = state.get("user_request", "")
    realtime_context = state.get("realtime_context", "")

    # === Short-circuit ke BrowserUseTool ===
    # Trigger jalur 1: URL eksplisit + verb interaktif (existing).
    # Trigger jalur 2: verb interaktif + site populer (auto-fill URL dari catalog).
    # Trigger jalur 3: force pattern ("live browsing" / "pake browser use") — fire walau gak ada URL/site.
    url_match = _URL_PATTERN.search(user_request)
    verb_match = _INTERACTIVE_VERBS.search(user_request)
    force_match = _FORCE_BROWSER.search(user_request)

    autofilled_url = None
    if (verb_match or force_match) and not url_match:
        autofilled_url = _autofill_url(user_request)

    should_short_circuit = (verb_match and (url_match or autofilled_url)) or force_match

    if should_short_circuit:
        # Tentukan task buat browser-use
        if url_match:
            task_for_browser = user_request
            logger.info(f"[LANGGRAPH INTEL] Short-circuit BrowserUseTool — URL={url_match.group(0)[:60]} verb={verb_match.group(0) if verb_match else '(force)'}")
        elif autofilled_url:
            # Marketplace SPA anti-bot ketat: instruct agent navigate via UI, bukan URL search direct.
            is_marketplace = any(s in autofilled_url for s in ('shopee.co.id', 'tokopedia.com', 'lazada.co.id', 'bukalapak.com'))
            marketplace_hint = ""
            if is_marketplace:
                # Re-extract keyword dari user_request (re-run site detection)
                keyword = ""
                for pattern, _, _ in _SITE_CATALOG:
                    m = pattern.search(user_request)
                    if m:
                        keyword = _extract_query(user_request, m)
                        break
                kw_line = f"\nKeyword cari: {keyword}" if keyword else ""
                marketplace_hint = (
                    f"\n\nNOTE PENTING (marketplace anti-bot ketat):"
                    f"\n1. Setelah halaman home load, JANGAN langsung navigate ke URL /search atau /product."
                    f"\n2. Cari search bar di top header → klik → ketik keyword → tekan Enter."
                    f"\n3. Tunggu halaman hasil render, baru extract data.{kw_line}"
                )
            task_for_browser = f"{user_request}\n\n(URL target: {autofilled_url}){marketplace_hint}"
            logger.info(f"[LANGGRAPH INTEL] Short-circuit BrowserUseTool — autofilled URL={autofilled_url[:80]} marketplace={is_marketplace} verb={verb_match.group(0) if verb_match else '(force)'}")
        else:
            # Force-only: gak ada URL/site, kasih hint sintaks ke Agent
            task_for_browser = (
                f"{user_request}\n\n"
                f"(Lo punya akses real browser — navigate ke site yang relevan, login kalau perlu, "
                f"interact dan extract data. Untuk topik di X/Twitter, mulai dari https://x.com/search?q=<keyword>. "
                f"Untuk topik umum, mulai dari Google search dulu.)"
            )
            logger.info(f"[LANGGRAPH INTEL] Short-circuit BrowserUseTool — FORCE trigger ({force_match.group(0)}), no URL/site")

        await notify_progress(state, "🌐 *Anisa nge-buka browser (Chromium) buat fetch isi...*")
        try:
            browser_result = await asyncio.to_thread(browser_tool._run, task_for_browser)
            logger.info(f"[LANGGRAPH INTEL] Browser selesai. Data: {len(str(browser_result))} karakter")
        except Exception as e:
            logger.error(f"[LANGGRAPH INTEL] BrowserUseTool gagal: {e}", exc_info=True)
            browser_result = f"FAILED|{e}"

        # Format jawaban — kalau SUCCESS, parse + rangkum; kalau FAILED, fallback ke Serper.
        if str(browser_result).startswith("SUCCESS|"):
            parts = str(browser_result).split("|", 2)
            body = parts[2] if len(parts) >= 3 else str(browser_result)
            sys_prompt = (
                f"{realtime_context}\n\nKamu adalah Anisa, asisten B.I.M.A Core. Rangkum hasil browser-use ini "
                f"buat Bima dengan jelas, casual Bahasa Indonesia. Sebutin URL sumber + waktu fetch.\n\n"
                f"Data:\n{body}"
            )
            final_response = await asyncio.to_thread(
                default_llm.invoke,
                [SystemMessage(content=sys_prompt), HumanMessage(content=user_request)]
            )
            temp_data = dict(state.get("temp_data", {}))
            temp_data["last_browser_result"] = body
            active_teams = state.get("active_teams", [])
            has_downstream = any(t in active_teams for t in ["seniman", "admin", "arsip"])
            return {
                "messages": [final_response],
                "is_finished": not has_downstream,
                "temp_data": temp_data,
            }
        else:
            # Browser gagal — log + fallback ke search path biasa
            logger.warning(f"[LANGGRAPH INTEL] Browser fail, fallback ke search: {browser_result[:120]}")
            await notify_progress(state, "⚠️ *Browser gagal, fallback ke search engine...*")

    prompt_search = f"""{realtime_context}

=== HISTORI PERCAKAPAN TERAKHIR ===
{get_recent_context(3)}
===================================

Permintaan terbaru Bima: '{user_request}'

Tugasmu: rumuskan 1 kata kunci pencarian Google yang paling tepat.
- WAJIB pakai konteks histori di atas. Kalau permintaan terbaru cuma jawaban singkat / preferensi (misal "kamera", "yang baru", "5-10jt"), itu LANJUTAN dari pertanyaan sebelumnya — pahami subjek aslinya dari histori.
- Sertakan tahun/bulan terkini kalau permintaan sensitif waktu (harga, tren, berita).
- Contoh: kalau histori bahas "rekomendasi HP gaming kamera bagus" dan jawaban Bima "kamera, baru" → keyword: "HP kamera bagus 2026" — BUKAN "kamera baru".

HANYA TULIS KATA KUNCINYA SAJA."""

    keyword_response = await asyncio.to_thread(
        default_llm.invoke, [HumanMessage(content=prompt_search)]
    )
    keyword = keyword_response.content.strip()

    logger.info(f"[LANGGRAPH INTEL] Mencari: '{keyword}'")
    try:
        search_result = await asyncio.to_thread(search_tool._run, keyword)
        logger.info(f"[LANGGRAPH INTEL] Selesai. Data: {len(str(search_result))} karakter")
    except Exception as e:
        logger.error(f"[LANGGRAPH INTEL] Gagal: {e}")
        search_result = f"Pencarian gagal: {e}"

    system_prompt = f"""Kamu adalah Agen Intel B.I.M.A Core.

{realtime_context}

Berikan rangkuman dan analisis dari data mentah hasil pencarian ini kepada Bima.
Tegaskan kapan data ini di-fetch (sesuai waktu di atas). Kalau ada angka/harga, sebutkan tanggalnya.

Data Mentah:
{search_result}

Jawab dengan gaya asisten (Anisa) yang profesional namun hangat."""

    final_response = await asyncio.to_thread(
        default_llm.invoke,
        [SystemMessage(content=system_prompt), HumanMessage(content=user_request)]
    )

    temp_data = dict(state.get("temp_data", {}))
    temp_data["last_search_result"] = search_result

    active_teams = state.get("active_teams", [])
    has_downstream = any(t in active_teams for t in ["seniman", "admin", "arsip"])

    return {
        "messages": [final_response],
        "is_finished": not has_downstream,
        "temp_data": temp_data
    }
