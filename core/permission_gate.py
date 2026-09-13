# core/permission_gate.py
import asyncio
import logging
import uuid
import contextvars

logger = logging.getLogger('bima_core')

class PermissionTimeoutError(asyncio.TimeoutError):
    """Exception raised when a permission request times out."""
    pass

# ContextVar to store the current discord user ID across threads/tasks
current_user_id = contextvars.ContextVar("current_user_id", default="anon")

_pending_approvals = {}
_pending_users = {}   # user_id -> req_id
_req_to_user = {}     # req_id -> user_id
_pending_details = {}  # req_id -> original approval details
_pending_revisions = {}  # req_id -> revised_text_str
_revision_tokens = {}  # req_id -> token revisi yang masih diproses
_send_approval_request_cb = None
_request_terminal_cb = None
_main_loop = None
_user_locks = {}

def _get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]

def set_main_loop(loop):
    global _main_loop
    _main_loop = loop
    logger.info("[PERMISSION_GATE] Main event loop registered.")

def get_main_loop():
    return _main_loop

def register_send_handler(cb):
    global _send_approval_request_cb
    _send_approval_request_cb = cb
    logger.info("[PERMISSION_GATE] Discord send handler registered.")


def register_terminal_handler(cb):
    """Daftarkan cleanup sinkron yang dipanggil saat request berakhir."""
    global _request_terminal_cb
    _request_terminal_cb = cb
    logger.info("[PERMISSION_GATE] Terminal cleanup handler registered.")


def _request_is_active(req_id: str) -> bool:
    future = _pending_approvals.get(req_id)
    return req_id in _req_to_user and future is not None and not future.done()


def get_pending_req_id_by_user(user_id: str) -> str | None:
    """Ambil req_id yang sedang menggantung untuk user tertentu."""
    req_id = _pending_users.get(user_id)
    return req_id if req_id and _request_is_active(req_id) else None

def set_pending_revision(req_id: str, revised_text: str) -> bool:
    """Simpan revisi hanya untuk approval request yang masih aktif."""
    if not _request_is_active(req_id):
        return False
    _pending_revisions[req_id] = revised_text
    return True


def begin_revision(req_id: str) -> str | None:
    """Tandai revisi request aktif agar approval ditahan sampai preview siap."""
    if not _request_is_active(req_id):
        return None
    token = str(uuid.uuid4())
    _revision_tokens[req_id] = token
    return token


def finish_revision(req_id: str, token: str) -> bool:
    """Selesaikan hanya revisi terbaru; task lama tidak boleh membuka gate."""
    if _revision_tokens.get(req_id) != token:
        return False
    _revision_tokens.pop(req_id, None)
    return True


def is_revision_inflight(req_id: str) -> bool:
    return req_id in _revision_tokens


def get_pending_details(req_id: str) -> str | None:
    """Ambil draf terbaru milik request aktif, atau detail awalnya."""
    if not _request_is_active(req_id):
        return None
    return _pending_revisions.get(req_id, _pending_details.get(req_id))


def resolve_approval_with_revision(req_id: str, revised_text: str):
    """Selesaikan request approval dengan status Setuju dan simpan teks revisinya."""
    if not set_pending_revision(req_id, revised_text):
        return False
    return resolve_approval(req_id, True)

async def _request_permission_decision(
    discord_user_id: str,
    action_type: str,
    details: str,
    attachment_paths: list[str] | None = None,
    raise_on_timeout: bool = False,
    revision_base: str | None = None,
) -> tuple[bool, str | None]:
    """Selesaikan satu approval beserta revisinya dalam scope request yang sama."""
    if not discord_user_id or discord_user_id == "anon":
        logger.warning("[PERMISSION_GATE] Anonymous user or missing user ID. Deny by default.")
        return False, None

    if not _send_approval_request_cb:
        logger.warning("[PERMISSION_GATE] No Discord send handler registered. Deny by default.")
        return False, None

    lock = _get_user_lock(discord_user_id)
    async with lock:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        approved = False
        
        req_id = str(uuid.uuid4())
        _pending_approvals[req_id] = future
        _pending_users[discord_user_id] = req_id
        _req_to_user[req_id] = discord_user_id
        _pending_details[req_id] = revision_base if revision_base is not None else details
        
        try:
            logger.info(f"[PERMISSION_GATE] Sending request {req_id} for user {discord_user_id} ({action_type})")
            success = await _send_approval_request_cb(req_id, discord_user_id, action_type, details, attachment_paths=attachment_paths)
            if not success:
                logger.warning(f"[PERMISSION_GATE] Failed to send approval request message for {req_id}")
                return False, None
                
            # Timeout 300 detik (5 menit), jika tidak direspon otomatis Tolak (False)
            approved = await asyncio.wait_for(future, timeout=300.0)
            logger.info(f"[PERMISSION_GATE] Request {req_id} resolved: {approved}")
            revised_text = _pending_revisions.get(req_id) if approved else None
            return approved, revised_text
        except asyncio.TimeoutError:
            logger.warning(f"[PERMISSION_GATE] Request {req_id} timed out after 300s. Aborting.")
            if is_revision_inflight(req_id) or req_id in _pending_revisions:
                logger.warning(
                    f"[PERMISSION_GATE] Request {req_id} timeout dengan revisi aktif; "
                    "fail closed tanpa auto-publish."
                )
                return False, None
            if raise_on_timeout:
                raise PermissionTimeoutError("Request permission timed out after 300 seconds.")
            return False, None
        except Exception as e:
            logger.error(f"[PERMISSION_GATE] Error in request_permission for {req_id}: {e}", exc_info=True)
            return False, None
        finally:
            _pending_details.pop(req_id, None)
            _pending_revisions.pop(req_id, None)
            _revision_tokens.pop(req_id, None)
            _pending_approvals.pop(req_id, None)
            _pending_users.pop(discord_user_id, None)
            _req_to_user.pop(req_id, None)
            if _request_terminal_cb:
                try:
                    _request_terminal_cb(req_id)
                except Exception as cleanup_error:
                    logger.warning(
                        f"[PERMISSION_GATE] Terminal cleanup gagal untuk {req_id}: "
                        f"{cleanup_error}"
                    )


async def request_permission(
    discord_user_id: str,
    action_type: str,
    details: str,
    attachment_paths: list[str] | None = None,
    raise_on_timeout: bool = False,
    revision_base: str | None = None,
) -> bool:
    """Minta izin dan kembalikan status boolean untuk caller umum."""
    approved, _ = await _request_permission_decision(
        discord_user_id,
        action_type,
        details,
        attachment_paths=attachment_paths,
        raise_on_timeout=raise_on_timeout,
        revision_base=revision_base,
    )
    return approved


async def request_permission_with_revision(
    discord_user_id: str,
    action_type: str,
    details: str,
    attachment_paths: list[str] | None = None,
    raise_on_timeout: bool = False,
    revision_base: str | None = None,
) -> tuple[bool, str | None]:
    """Minta izin dan kembalikan revisi dari request yang sama bila disetujui."""
    return await _request_permission_decision(
        discord_user_id,
        action_type,
        details,
        attachment_paths=attachment_paths,
        raise_on_timeout=raise_on_timeout,
        revision_base=revision_base,
    )

def resolve_approval(req_id: str, approved: bool) -> bool:
    """Selesaikan request approval yang sedang menggantung."""
    future = _pending_approvals.get(req_id)
    if not future or future.done():
        return False
    if approved and is_revision_inflight(req_id):
        logger.info(
            f"[PERMISSION_GATE] Approval {req_id} ditahan karena revisi masih diproses."
        )
        return False
    future.set_result(approved)
    logger.info(f"[PERMISSION_GATE] Request {req_id} resolved via callback with: {approved}")
    return True

def check_permission_sync(action_type: str, details: str, attachment_paths: list[str] | None = None) -> bool:
    """Helper synchronous untuk dipanggil dari dalam sync CrewAI tools."""
    user_id = current_user_id.get("anon")
    logger.debug(f"[PERMISSION_GATE] Sync check: user={user_id}, action={action_type}")
    
    if user_id == "anon":
        logger.warning(f"[PERMISSION_GATE] Denied '{action_type}' because user is anonymous.")
        return False
        
    loop = get_main_loop()
    if not loop:
        logger.warning("[PERMISSION_GATE] No main event loop registered. Deny by default.")
        return False
        
    try:
        # Kirim coroutine ke main event loop dan tunggu hasilnya (blocking thread ini)
        future = asyncio.run_coroutine_threadsafe(
            request_permission(user_id, action_type, details, attachment_paths),
            loop
        )
        return future.result()
    except Exception as e:
        logger.error(f"[PERMISSION_GATE] Failed to execute sync check: {e}", exc_info=True)
        return False
