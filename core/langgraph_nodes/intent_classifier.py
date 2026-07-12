"""Intent classifier node — fast-path routing tanpa LLM call.

Pattern conservative: hanya intent yang JELAS single-team. Multi-team / ambigu
fallback ke manager_node (LLM-based routing existing).
"""
import re
import logging
from core.langgraph_nodes.state import BimaState

logger = logging.getLogger('bima_core')

# Pattern case-sensitive ticker — harus uppercase 2-5 char
_TICKER_HARGA = re.compile(r'\bharga\s+(saham\s+)?[A-Z]{2,5}(\.JK)?\b')
_TICKER_DOLLAR = re.compile(r'\$[A-Z]{2,5}(\.JK)?\b')
_SAHAM_KEYWORDS = re.compile(
    r'\b(rsi|macd|bollinger|sma|fundamental|teknikal|buy/hold/sell|per\s+pbv)\b.{0,30}\b[A-Z]{2,5}\b',
    re.IGNORECASE,
)

_VAULT_SAVE = re.compile(
    r"\b(simpan|catat|arsipkan)\b.{0,50}\b(vault|obsidian|catatan)\b"
    r"|\b(vault|obsidian|catatan)\b.{0,50}\b(simpan|catat|arsipkan)\b"
    r"|^\s*catat\s+(ini|itu)(?:\s+(dong|ya))?[.!?]?\s*$",
    re.IGNORECASE,
)
_VAULT_SEARCH = re.compile(
    r"\b(cari|apa\s+isi|buka)\b.{0,50}\b(vault|obsidian|catatan)\b"
    r"|\b(vault|obsidian|catatan)\b.{0,50}\b(cari|apa\s+isi|buka)\b",
    re.IGNORECASE,
)
_VAULT_NEGATED = re.compile(
    r"\b(jangan|tidak\s+usah|gak\s+usah|nggak\s+usah)\b"
    r".{0,20}\b(simpan|catat|arsipkan|cari|apa\s+isi|buka)\b",
    re.IGNORECASE,
)

_CUACA = re.compile(r'\bcuaca\s+(di\s+)?\S+', re.IGNORECASE)
_YOUTUBE = re.compile(r'\b(cari\s+)?video\s+(youtube|yt)\b', re.IGNORECASE)

_RUN_CODE = re.compile(
    r'\b(jalankan|run|eksekusi|execute)\s+(kode|code|python|skrip|script)\b',
    re.IGNORECASE,
)

_PROMPT_OPTIMIZE = re.compile(
    r'\b(optim\w+|rewrite|perbaik\w+|refactor|tunin\w+)\b.{0,30}\bprompt\b'
    r'|\bprompt\b.{0,30}\b(buruk|jelek|bingung|gak\s+jelas|kurang\s+spesifik|gak\s+work|gak\s+jalan)\b'
    r'|\bprompt\s+(master|engineer\w*|optimiz\w+)\b',
    re.IGNORECASE,
)

# Video generation: trigger eksplisit "bikin/buat/generate video" atau slash command.
# Dicek SEBELUM _IMAGE_GEN — lebih spesifik biar "bikin video" gak ke-route ke image.
_VIDEO_GEN = re.compile(
    # Cabang A: verba + noun ("bikin video", "render klip", "animasiin clip")
    # NB: "vidio" itu typo umum Bahasa Indonesia informal — masuk whitelist
    r'\b(bikin|buat|generate|render|animas\w+)\b.{0,40}\b(video|vidio|klip|clip|animasi)\b'
    # Cabang B: verba khusus implisit ("videoin X", "animasiin X", "animasikan X")
    r'|\b(videoin|vidioin|animasiin|animasikan)\b'
    # Cabang C: slash command
    r'|^\s*/anisa\s+(video|vidio|klip|animasi)\b',
    re.IGNORECASE,
)

# Image generation: trigger eksplisit "bikin/buat/generate gambar" atau slash command.
# Cek SEBELUM generic seniman patterns supaya gen image gak ke-route ke HTML pipeline.
_IMAGE_GEN = re.compile(
    # Cabang A: verba + noun ("bikin gambar", "generate image", "buat ilustrasi", dll)
    r'\b(bikin|buat|generate|render|visualis\w+|illustrat\w+|ilustras\w+)\b.{0,40}\b(gambar|image|ilustrasi|picture|art|foto|illustration)\b'
    # Cabang B: verba khusus image gen yang udah implisit ("gambarin X", "gambarkan Y")
    r'|\bgambar(in|kan|kn)\b'
    r'|\billustrate\b'
    # Cabang C: slash command
    r'|^\s*/anisa\s+(gambar|image|foto)\b',
    re.IGNORECASE,
)

# Canvas: PDF iterative editing. Init trigger eksplisit lewat "draft pdf" / "canvas".
# Session-active check di-handle di intent_classifier_node sebelum regex.
_CANVAS_INIT = re.compile(
    r'\b(draft|iterati[fv]e?|canvas)\b.{0,30}\b(pdf|dokumen|laporan)\b'
    r'|\b(pdf|dokumen|laporan)\b.{0,30}\b(draft|iterati[fv]e?|canvas)\b'
    r'|\bmulai\s+(canvas|sesi\s+pdf)\b',
    re.IGNORECASE,
)

# Kodok: code understanding di repo BIMA_CORE.
# Branch A: verba (jelasin/cari/summary/di mana) + konteks code (file/kode/modul/path).
# Branch B: "di mana <symbol> dipakai/dipanggil" tanpa perlu kata file.
# Branch C: keyword spesifik kodok/repo rag/reindex.
_KODOK = re.compile(
    r'\b(jelasin|jelaskan|summary|ringkas\w*|cari\s+(fungsi|class|method|symbol)|di\s+mana.*\b(fungsi|class|method)\b|review|baca|lihat\s+isi|tunjukin\s+kode|callgraph|dependensi|overview)\b'
    r'.{0,80}\b(file|kode|modul|repo|folder|direktori|\.py|\.js|\.ts|\.rs|\.go|\.md|core/|teams/|tools/)'
    r'|\b(di\s+mana|where)\b.{0,40}\b(fungsi|class|method|tool|symbol|variabel|function)\b.{0,30}\b(dipakai|dipanggil|digunakan|used|called|defined|defin\w+)\b'
    r'|\b(kodok|code\s+doctor|repo\s+rag|index\s+repo|reindex\s+repo)\b',
    re.IGNORECASE,
)

_VISUAL_INTENT = re.compile(
    r'\b(analis\w*|jelas\w*|baca|review|cek|terjemah\w*|deskripsi)\b',
    re.IGNORECASE,
)

# Fase 3a: observer (lihat screen Bima via desktop bridge Windows)
_OBSERVE_SCREEN = re.compile(
    r'(/lihat\b|\blihat\s+(screen|layar|monitor)\b|\bngintip\s+(screen|layar)\b|\bscreen\s+check\b|\bcek\s+(screen|layar)\b|\bapa\s+yang\s+(gue|gw|aku)\s+(lagi\s+)?kerj\w*\s+(di\s+)?(screen|layar|komputer)\b)',
    re.IGNORECASE,
)

# Multi-step / multi-team signals → fallback ke manager (LLM tau urutan)
_MULTI_STEP = re.compile(
    r'\b(lalu|terus|trus|kemudian|setelah\s+itu|abis\s+itu|baru\s+(simpan|buat|kirim))\b',
    re.IGNORECASE,
)
_INTEL_SIGNAL = re.compile(
    r'\bcari\b.{0,50}\b(tokopedia|shopee|google|internet|web|reddit|github|tiktok|x\.com|twitter)\b',
    re.IGNORECASE,
)


def classify_intent(user_request: str, has_attachment: bool) -> tuple[list[str], float, str]:
    """Return (active_teams, confidence, label). confidence 0 = no match → fallback."""
    text = user_request or ""

    if _MULTI_STEP.search(text) or _INTEL_SIGNAL.search(text):
        return [], 0.0, "multi-step → manager"

    if has_attachment and _VISUAL_INTENT.search(text):
        return ["visual"], 0.90, "analisis attachment"

    if _OBSERVE_SCREEN.search(text):
        return ["observer"], 0.93, "observe desktop screen"

    if _TICKER_HARGA.search(text) or _TICKER_DOLLAR.search(text) or _SAHAM_KEYWORDS.search(text):
        return ["saham"], 0.92, "saham/ticker"

    vault_negated = _VAULT_NEGATED.search(text)
    if not vault_negated and _VAULT_SEARCH.search(text):
        return ["arsip"], 0.88, "cari di vault"
    if not vault_negated and _VAULT_SAVE.search(text):
        return ["arsip"], 0.90, "simpan ke vault"

    if _RUN_CODE.search(text):
        return ["mekanik"], 0.90, "eksekusi kode"

    # Video gen DULU karena lebih spesifik (kata "video" >> "gambar" prio)
    if _VIDEO_GEN.search(text):
        return ["seniman"], 0.93, "video gen"

    if _IMAGE_GEN.search(text):
        return ["seniman"], 0.93, "image gen"

    if _PROMPT_OPTIMIZE.search(text):
        return ["seniman"], 0.88, "prompt optimize/rewrite"

    if _KODOK.search(text):
        return ["kodok"], 0.88, "code understanding (kodok)"

    if _CANVAS_INIT.search(text):
        return ["canvas"], 0.90, "canvas init (PDF iterative)"

    if _CUACA.search(text) or _YOUTUBE.search(text):
        return ["lifestyle"], 0.88, "cuaca/youtube"

    return [], 0.0, "no_match"


async def intent_classifier_node(state: BimaState) -> dict:
    user_request = state.get("user_request", "")
    has_attachment = bool(state.get("attachment_paths"))
    user_id = state.get("discord_user_id", "")

    # Canvas session check — kalau user punya active session, semua message
    # routed ke canvas_node (kecuali super-override yang bakal di-handle di node-nya).
    if user_id:
        try:
            from core import canvas_session
            if canvas_session.has_active(user_id):
                logger.info(f"[CLASSIFIER] Active canvas session user={user_id} → canvas_node")
                return {"active_teams": ["canvas"], "is_finished": False}
        except Exception as e:
            logger.debug(f"[CLASSIFIER] canvas_session check error (non-fatal): {e}")

    teams, confidence, label = classify_intent(user_request, has_attachment)

    if confidence >= 0.85 and teams:
        logger.info(f"[CLASSIFIER] FAST-PATH '{label}' (conf={confidence:.2f}) → teams={teams}")
        update: dict = {
            "active_teams": teams,
            "is_finished": False,
        }
        # Tag generative mode supaya seniman_node tau harus branch ke image / video gen
        if label == "image gen":
            update["gen_mode"] = "image"
        elif label == "video gen":
            update["gen_mode"] = "video"
        return update
    logger.info("[CLASSIFIER] No fast-path → fallback ke manager_node")
    return {}


def route_from_classifier(state: BimaState) -> str:
    """Decide: fast-path ke specialist langsung, atau ke manager_node."""
    active_teams = state.get("active_teams", [])
    if not active_teams:
        return "manager_node"

    # Same priority order as route_from_manager (observer first — single-team standalone)
    priority = ["observer", "canvas", "intel", "arsip", "seniman", "admin", "visual", "lifestyle", "kodok", "mekanik", "saham"]
    for team in priority:
        if team in active_teams:
            return f"{team}_node"
    return "manager_node"
