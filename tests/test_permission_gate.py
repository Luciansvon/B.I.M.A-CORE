import asyncio
import pytest
import core.permission_gate as permission_gate
from core.permission_gate import (
    current_user_id,
    set_main_loop,
    register_send_handler,
    request_permission,
    check_permission_sync,
    resolve_approval
)


@pytest.fixture(autouse=True)
def reset_permission_state():
    original_terminal_handler = getattr(permission_gate, "_request_terminal_cb", None)
    permission_gate._pending_approvals.clear()
    permission_gate._pending_users.clear()
    permission_gate._req_to_user.clear()
    if hasattr(permission_gate, "_pending_details"):
        permission_gate._pending_details.clear()
    if hasattr(permission_gate, "_pending_revisions"):
        permission_gate._pending_revisions.clear()
    if hasattr(permission_gate, "_revision_tokens"):
        permission_gate._revision_tokens.clear()
    if hasattr(permission_gate, "_revised_texts"):
        permission_gate._revised_texts.clear()
    yield
    permission_gate._pending_approvals.clear()
    permission_gate._pending_users.clear()
    permission_gate._req_to_user.clear()
    if hasattr(permission_gate, "_pending_details"):
        permission_gate._pending_details.clear()
    if hasattr(permission_gate, "_pending_revisions"):
        permission_gate._pending_revisions.clear()
    if hasattr(permission_gate, "_revision_tokens"):
        permission_gate._revision_tokens.clear()
    if hasattr(permission_gate, "_request_terminal_cb"):
        permission_gate._request_terminal_cb = original_terminal_handler
    if hasattr(permission_gate, "_revised_texts"):
        permission_gate._revised_texts.clear()

@pytest.mark.asyncio
async def test_permission_gate_async_flow():
    # Setup test handlers
    received_reqs = []
    
    async def mock_send_handler(req_id, user_id, action_type, details, attachment_paths=None):
        received_reqs.append((req_id, user_id, action_type, details))
        # Simulate user reacting after a short delay
        asyncio.create_task(simulate_user_approval(req_id, True))
        return True

    async def simulate_user_approval(req_id, approved):
        await asyncio.sleep(0.05)
        resolve_approval(req_id, approved)

    register_send_handler(mock_send_handler)
    
    # Run the request
    approved = await request_permission("12345", "Test Action", "Running test commands")
    assert approved is True
    assert len(received_reqs) == 1
    assert received_reqs[0][1] == "12345"
    assert received_reqs[0][2] == "Test Action"

@pytest.mark.asyncio
async def test_permission_gate_deny_flow():
    async def mock_send_handler(req_id, user_id, action_type, details, attachment_paths=None):
        asyncio.create_task(simulate_user_approval(req_id, False))
        return True

    async def simulate_user_approval(req_id, approved):
        await asyncio.sleep(0.05)
        resolve_approval(req_id, approved)

    register_send_handler(mock_send_handler)
    
    approved = await request_permission("12345", "Test Action", "Running test commands")
    assert approved is False

@pytest.mark.asyncio
async def test_permission_gate_sync_bridge():
    # We must register the main event loop
    loop = asyncio.get_running_loop()
    set_main_loop(loop)
    
    async def mock_send_handler(req_id, user_id, action_type, details, attachment_paths=None):
        # Resolve immediately
        resolve_approval(req_id, True)
        return True
        
    register_send_handler(mock_send_handler)
    
    # Set the user ID in the contextvar
    current_user_id.set("12345")
    
    # Run the sync check in a thread (simulating CrewAI tool thread execution)
    def run_in_thread():
        # Contextvar is thread-local, but in asyncio.to_thread it's copied.
        # Since we are running manually here, let's set it in the thread or check if it works.
        current_user_id.set("12345")
        return check_permission_sync("Sync Action", "Details")
        
    result = await asyncio.to_thread(run_in_thread)
    assert result is True


@pytest.mark.asyncio
async def test_rejected_revision_cannot_leak_into_next_approved_request():
    request_with_revision = getattr(permission_gate, "request_permission_with_revision", None)
    assert request_with_revision is not None
    user_id = "threads-user"

    async def reject_with_revision(req_id, *_args, **_kwargs):
        permission_gate.set_pending_revision(req_id, "DRAF LAMA")
        resolve_approval(req_id, False)
        return True

    register_send_handler(reject_with_revision)
    assert await request_with_revision(user_id, "THREADS_POST", "draf A") == (False, None)

    async def approve_without_revision(req_id, *_args, **_kwargs):
        resolve_approval(req_id, True)
        return True

    register_send_handler(approve_without_revision)
    assert await request_with_revision(user_id, "THREADS_POST", "draf B") == (True, None)


@pytest.mark.asyncio
async def test_timed_out_revision_is_removed(monkeypatch):
    request_with_revision = getattr(permission_gate, "request_permission_with_revision", None)
    assert request_with_revision is not None
    user_id = "threads-timeout-user"

    async def send_with_revision(req_id, *_args, **_kwargs):
        permission_gate.set_pending_revision(req_id, "DRAF TIMEOUT")
        return True

    async def timeout_immediately(future, timeout):
        future.cancel()
        raise asyncio.TimeoutError

    register_send_handler(send_with_revision)
    monkeypatch.setattr(permission_gate.asyncio, "wait_for", timeout_immediately)

    assert await request_with_revision(user_id, "THREADS_POST", "draf") == (False, None)


@pytest.mark.asyncio
async def test_approved_revision_is_promoted_from_current_request_only():
    request_with_revision = getattr(permission_gate, "request_permission_with_revision", None)
    set_pending_revision = getattr(permission_gate, "set_pending_revision", None)
    assert request_with_revision is not None
    assert set_pending_revision is not None

    request_ids = []

    async def approve_current_revision(req_id, *_args, **_kwargs):
        request_ids.append(req_id)
        set_pending_revision(req_id, "DRAF REQUEST SEKARANG")
        resolve_approval(req_id, True)
        return True

    register_send_handler(approve_current_revision)
    decision = await request_with_revision("threads-current-user", "THREADS_POST", "draf")
    assert decision == (True, "DRAF REQUEST SEKARANG")
    assert request_ids[0] not in permission_gate._pending_revisions


@pytest.mark.asyncio
async def test_pending_details_tracks_latest_revision_and_cleans_terminal_state():
    get_pending_details = getattr(permission_gate, "get_pending_details", None)
    set_pending_revision = getattr(permission_gate, "set_pending_revision", None)
    assert get_pending_details is not None
    assert set_pending_revision is not None

    request_ids = []

    async def revise_twice_then_reject(req_id, *_args, **_kwargs):
        request_ids.append(req_id)
        assert get_pending_details(req_id) == "DRAF AWAL"
        assert set_pending_revision(req_id, "DRAF REVISI 1") is True
        assert get_pending_details(req_id) == "DRAF REVISI 1"
        assert set_pending_revision(req_id, "DRAF REVISI 2") is True
        assert get_pending_details(req_id) == "DRAF REVISI 2"
        resolve_approval(req_id, False)
        return True

    register_send_handler(revise_twice_then_reject)
    assert await request_permission("threads-revision-user", "THREADS_POST", "DRAF AWAL") is False
    assert get_pending_details(request_ids[0]) is None


@pytest.mark.asyncio
async def test_approval_waits_until_current_revision_finishes():
    request_with_revision = permission_gate.request_permission_with_revision

    async def revise_then_approve(req_id, *_args, **_kwargs):
        token = permission_gate.begin_revision(req_id)
        assert token is not None
        assert permission_gate.resolve_approval(req_id, True) is False
        assert permission_gate._pending_approvals[req_id].done() is False
        assert permission_gate.set_pending_revision(req_id, "DRAF PALING BARU") is True
        assert permission_gate.finish_revision(req_id, token) is True
        assert permission_gate.resolve_approval(req_id, True) is True
        return True

    register_send_handler(revise_then_approve)

    assert await request_with_revision(
        "threads-race-user", "THREADS_POST", "DRAF AWAL"
    ) == (True, "DRAF PALING BARU")


@pytest.mark.asyncio
async def test_terminal_handler_runs_and_revision_state_is_cleaned_on_timeout(monkeypatch):
    terminal_request_ids = []
    request_ids = []

    async def start_revision_then_wait(req_id, *_args, **_kwargs):
        request_ids.append(req_id)
        assert permission_gate.begin_revision(req_id) is not None
        return True

    async def timeout_immediately(future, timeout):
        future.cancel()
        raise asyncio.TimeoutError

    permission_gate.register_terminal_handler(terminal_request_ids.append)
    register_send_handler(start_revision_then_wait)
    monkeypatch.setattr(permission_gate.asyncio, "wait_for", timeout_immediately)

    assert await request_permission("threads-timeout-cleanup", "THREADS_POST", "DRAF") is False
    assert terminal_request_ids == request_ids
    assert request_ids[0] not in permission_gate._revision_tokens


@pytest.mark.asyncio
async def test_revision_cannot_start_after_request_future_is_resolved():
    user_id = "threads-terminal-race"

    async def resolve_then_try_revision(req_id, *_args, **_kwargs):
        assert resolve_approval(req_id, True) is True
        assert permission_gate.get_pending_req_id_by_user(user_id) is None
        assert permission_gate.begin_revision(req_id) is None
        assert permission_gate.set_pending_revision(req_id, "TERLAMBAT") is False
        return True

    register_send_handler(resolve_then_try_revision)

    assert await permission_gate.request_permission_with_revision(
        user_id, "THREADS_POST", "DRAF AWAL"
    ) == (True, None)


@pytest.mark.asyncio
async def test_timeout_during_revision_cannot_trigger_afk_auto_publish(monkeypatch):
    async def start_revision(req_id, *_args, **_kwargs):
        assert permission_gate.begin_revision(req_id) is not None
        return True

    async def timeout_immediately(future, timeout):
        future.cancel()
        raise asyncio.TimeoutError

    register_send_handler(start_revision)
    monkeypatch.setattr(permission_gate.asyncio, "wait_for", timeout_immediately)

    assert await permission_gate.request_permission_with_revision(
        "threads-revision-timeout",
        "THREADS_POST",
        "DRAF AWAL",
        raise_on_timeout=True,
    ) == (False, None)


@pytest.mark.asyncio
async def test_timeout_after_revision_preview_cannot_publish_original_draft(monkeypatch):
    async def store_revision_then_wait(req_id, *_args, **_kwargs):
        assert permission_gate.set_pending_revision(req_id, "REVISI BELUM DISETUJUI") is True
        return True

    async def timeout_immediately(future, timeout):
        future.cancel()
        raise asyncio.TimeoutError

    register_send_handler(store_revision_then_wait)
    monkeypatch.setattr(permission_gate.asyncio, "wait_for", timeout_immediately)

    assert await permission_gate.request_permission_with_revision(
        "threads-preview-timeout",
        "THREADS_POST",
        "DRAF AWAL",
        raise_on_timeout=True,
    ) == (False, None)


@pytest.mark.asyncio
async def test_revision_uses_raw_source_instead_of_display_wrapper():
    async def inspect_then_approve(req_id, _user_id, _action, details, **_kwargs):
        assert details == "WRAPPER UI + URL GAMBAR"
        assert permission_gate.get_pending_details(req_id) == "DRAF RAW"
        assert permission_gate.set_pending_revision(req_id, "DRAF RAW REVISI") is True
        assert resolve_approval(req_id, True) is True
        return True

    register_send_handler(inspect_then_approve)

    assert await permission_gate.request_permission_with_revision(
        "threads-raw-source",
        "THREADS_POST",
        "WRAPPER UI + URL GAMBAR",
        revision_base="DRAF RAW",
    ) == (True, "DRAF RAW REVISI")
