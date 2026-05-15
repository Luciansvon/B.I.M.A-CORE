from typing import TypedDict, Annotated, Sequence, Optional, Callable, Awaitable, NotRequired
import logging
import operator
from langchain_core.messages import BaseMessage

logger = logging.getLogger('bima_core')

ProgressCallback = Callable[[str], Awaitable[None]]

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

    # Callback untuk update status realtime ke Discord (opsional)
    progress_callback: NotRequired[Optional[ProgressCallback]]

    # Discord user ID (string) — diperlukan canvas_node untuk session-per-user
    discord_user_id: NotRequired[str]

    # Mode generative output: "image" | "video" | None — diset oleh intent_classifier,
    # dipakai seniman_node untuk branch ke ImageGenTool / VideoGenTool / HTML pipeline
    gen_mode: NotRequired[str]


async def notify_progress(state: BimaState, message: str) -> None:
    """Kirim status progress ke Discord. Silent jika callback tidak ada atau gagal."""
    cb = state.get("progress_callback")
    if cb is None:
        return
    try:
        await cb(message)
    except Exception as e:
        logger.warning(f"[PROGRESS] Gagal update status Discord: {e}")
