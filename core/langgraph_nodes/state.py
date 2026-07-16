from typing import TypedDict, Annotated, Sequence, Optional, Callable, Awaitable, NotRequired
import logging
import operator
from langchain_core.messages import BaseMessage

logger = logging.getLogger('bima_core')

ProgressCallback = Callable[[str], Awaitable[None]]

# T1-A fix: callback registry — disimpan di sini biar gak masuk state (function gak
# msgpack-serializable, akan crash checkpointer aput()). Key = thread_id.
_progress_callbacks: dict[str, ProgressCallback] = {}


def register_progress_callback(thread_id: str, cb: Optional[ProgressCallback]) -> None:
    if cb is None or not thread_id:
        return
    _progress_callbacks[thread_id] = cb


def unregister_progress_callback(thread_id: str) -> None:
    if thread_id:
        _progress_callbacks.pop(thread_id, None)


def build_thread_id(
    user_id: str = "",
    source_channel: str = "",
    conversation_id: str = "",
) -> str:
    user = user_id or "anon"
    channel = source_channel or "unknown"
    conversation = conversation_id or channel
    return f"{channel}:{user}:{conversation}"


def _derive_thread_id_from_state(state: "BimaState") -> str:
    return build_thread_id(
        state.get("discord_user_id", ""),
        state.get("source_channel", ""),
        state.get("conversation_id", ""),
    )

# Ini adalah "Otak Pusat" atau papan tulis bersama untuk agen-agen kita.
# Setiap kali agen bekerja, mereka akan membaca dan memperbarui State ini.
class BimaState(TypedDict):
    # Pesan dari user atau antar agen
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # Metadata dari Discord (file, konteks waktu, dll)
    user_request: str
    attachment_paths: list[str]
    realtime_context: str

    # Rencana yang dibuat oleh Manager
    current_plan: str

    # Tim mana saja yang aktif berdasarkan deteksi intent
    active_teams: list[str]

    # Hasil dari Intel atau agen spesialis lainnya sebelum diberikan ke user
    temp_data: dict

    # Apakah tugas sudah selesai dan siap dikirim ke Discord?
    is_finished: bool

    # Callback untuk update status realtime ke Discord (opsional).
    # DEPRECATED di state: function gak msgpack-serializable → checkpoint crash.
    # Pakai register_progress_callback(thread_id, cb) sebelum invoke graph, lookup
    # otomatis via notify_progress(). Field disimpan untuk backward-compat path lain
    # (e.g. canvas_node manual injection), tapi run_langgraph_engine() tidak isi field ini.
    progress_callback: NotRequired[Optional[ProgressCallback]]

    # Discord user ID (string) — diperlukan canvas_node untuk session-per-user
    discord_user_id: NotRequired[str]

    # Mode generative output: "image" | "video" | None — diset oleh intent_classifier,
    # dipakai seniman_node untuk branch ke ImageGenTool / VideoGenTool / HTML pipeline
    gen_mode: NotRequired[str]

    # Channel asal request — "discord" | "whatsapp" | "" (unknown).
    # Dipakai seniman_node untuk Discord-guard di video gen (Discord 25MB limit ketat,
    # WA 100MB lega — kalau Discord trigger video, redirect user ke WA).
    source_channel: NotRequired[str]

    # ID chat/channel nyata untuk isolasi checkpoint dan progress callback.
    conversation_id: NotRequired[str]

    # T1-E: Conversation summary — diisi context_summarizer_node kalau messages > threshold.
    # Manager + agen pakai field ini untuk konteks panjang tanpa harus parse semua history.
    conversation_summary: NotRequired[str]


async def notify_progress(state: BimaState, message: str) -> None:
    """Kirim status progress ke Discord. Silent jika callback tidak ada atau gagal.

    Resolusi callback (urutan):
    1. State `progress_callback` (legacy path; sekarang biasanya kosong)
    2. Module-level `_progress_callbacks[thread_id]` (T1-A fix)
    """
    cb = state.get("progress_callback")
    if cb is None:
        thread_id = _derive_thread_id_from_state(state)
        cb = _progress_callbacks.get(thread_id)
    if cb is None:
        return
    try:
        await cb(message)
    except Exception as e:
        logger.warning(f"[PROGRESS] Gagal update status Discord: {e}")
