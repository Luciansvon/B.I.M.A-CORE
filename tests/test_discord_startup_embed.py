"""Regression tests untuk notifikasi startup Discord Anisa."""

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
