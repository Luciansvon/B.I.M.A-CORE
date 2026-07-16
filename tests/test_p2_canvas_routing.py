import pytest

from core import canvas_session
from core.langgraph_nodes.canvas import canvas_node
from core.langgraph_nodes.intent_classifier import intent_classifier_node


@pytest.mark.asyncio
async def test_whatsapp_sender_resumes_active_canvas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(canvas_session, "has_active", lambda user_id: user_id == "628111")

    result = await intent_classifier_node(
        {
            "user_request": "ganti judul jadi Kursi Rotan",
            "attachment_paths": [],
            "discord_user_id": "628111",
            "source_channel": "whatsapp",
            "conversation_id": "628111",
        }
    )

    assert result["active_teams"] == ["canvas"]


@pytest.mark.asyncio
async def test_canvas_missing_identity_message_is_channel_neutral() -> None:
    result = await canvas_node(
        {
            "user_request": "draft pdf tentang kursi",
            "attachment_paths": [],
            "discord_user_id": "",
            "source_channel": "whatsapp",
        }
    )

    message = result["messages"][0].content
    assert "Discord" not in message
    assert "identitas user" in message.lower()
