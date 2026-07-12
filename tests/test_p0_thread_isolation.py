from pathlib import Path

from core.langgraph_nodes.state import build_thread_id


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_whatsapp_senders_get_distinct_thread_ids() -> None:
    first = build_thread_id("628111", "whatsapp", "628111")
    second = build_thread_id("628222", "whatsapp", "628222")

    assert first != second


def test_discord_channels_get_distinct_thread_ids_for_same_user() -> None:
    first = build_thread_id("123", "discord", "channel-1")
    second = build_thread_id("123", "discord", "channel-2")

    assert first != second


def test_legacy_call_has_stable_fallback_scope() -> None:
    assert build_thread_id("123", "discord", "") == "discord:123:discord"


def test_whatsapp_bridge_payload_contains_sender_id() -> None:
    source = (PROJECT_ROOT / "whatsapp" / "index.js").read_text(
        encoding="utf-8"
    )

    assert (
        "async function sendToAnisa(message, senderId, attachmentPaths = [])"
        in source
    )
    assert "sender_id: senderId" in source
    assert "sendToAnisa(perintah, senderId, attachmentPaths)" in source


def test_discord_passes_real_conversation_id() -> None:
    source = (PROJECT_ROOT / "core" / "discord_bot.py").read_text(
        encoding="utf-8"
    )

    assert "conversation_id=str(message.channel.id)" in source
