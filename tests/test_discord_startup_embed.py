"""Regression tests untuk startup dan state approval Discord Anisa."""

import pytest

import core.discord_bot as discord_bot
from core.discord_bot import _build_startup_embed


def test_startup_embed_lists_active_commands() -> None:
    embed = _build_startup_embed()
    rendered = "\n".join(
        [embed.title or "", embed.description or ""]
        + [f"{field.name}\n{field.value}" for field in embed.fields]
    )

    required_commands = (
        "/private start|stop",
        "!status",
        "!ocr",
        "!qc",
        "!cutlist",
        "!arsip help",
        "!saham help",
        "!threads <topik>",
        "!play <judul>",
        "!queue",
        "!skip",
        "!music",
    )
    for command in required_commands:
        assert command in rendered


def test_startup_embed_stays_within_discord_limits() -> None:
    embed = _build_startup_embed()

    assert len(embed.fields) <= 25
    assert len(embed) <= 6000
    assert all(len(field.name) <= 256 for field in embed.fields)
    assert all(len(field.value) <= 1024 for field in embed.fields)


def test_discord_approval_cleanup_removes_only_terminal_request(monkeypatch) -> None:
    class FakeTask:
        def __init__(self):
            self.cancelled = False

        def done(self):
            return False

        def cancel(self):
            self.cancelled = True

    old_task = FakeTask()
    active_task = FakeTask()
    monkeypatch.setattr(
        discord_bot,
        "_discord_approval_messages",
        {
            10: ("req-old", "user-old", "THREADS_POST", "awal"),
            11: ("req-old", "user-old", "THREADS_POST", "revisi"),
            20: ("req-active", "user-active", "THREADS_POST", "aktif"),
        },
    )
    monkeypatch.setattr(
        discord_bot,
        "_dm_debounce_timers",
        {"user-old": old_task, "user-active": active_task},
    )
    monkeypatch.setattr(
        discord_bot,
        "_dm_debounce_texts",
        {"user-old": "lama", "user-active": "aktif"},
    )
    monkeypatch.setattr(
        discord_bot,
        "_dm_debounce_request_ids",
        {"user-old": "req-old", "user-active": "req-active"},
    )

    assert discord_bot._get_latest_discord_approval_message_id("req-old") == 11
    discord_bot._cleanup_discord_approval_request("req-old")

    assert discord_bot._discord_approval_messages == {
        20: ("req-active", "user-active", "THREADS_POST", "aktif")
    }
    assert discord_bot._dm_debounce_request_ids == {"user-active": "req-active"}
    assert discord_bot._dm_debounce_texts == {"user-active": "aktif"}
    assert discord_bot._dm_debounce_timers == {"user-active": active_task}
    assert old_task.cancelled is True
    assert active_task.cancelled is False


@pytest.mark.asyncio
async def test_initial_approval_is_registered_before_reactions(monkeypatch) -> None:
    registration_checks = []

    class FakeMessage:
        id = 321

        async def add_reaction(self, _emoji):
            registration_checks.append(self.id in discord_bot._discord_approval_messages)

    class FakeDM:
        async def send(self, _content, files=None):
            return FakeMessage()

    class FakeUser:
        dm_channel = FakeDM()

    class FakeClient:
        async def fetch_user(self, _user_id):
            return FakeUser()

    monkeypatch.setattr(discord_bot, "client", FakeClient())
    monkeypatch.setattr(discord_bot, "_discord_approval_messages", {})

    assert await discord_bot.send_discord_approval(
        "req-fast-reaction", "42", "THREADS_POST", "DRAF"
    ) is True
    assert registration_checks == [True, True]
