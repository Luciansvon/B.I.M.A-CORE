import asyncio
import pytest
from core.permission_gate import (
    current_user_id,
    set_main_loop,
    register_send_handler,
    request_permission,
    check_permission_sync,
    resolve_approval
)

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
