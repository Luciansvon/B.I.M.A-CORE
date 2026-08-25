import asyncio
import re
import tomllib
from pathlib import Path

from core.music_commands import _cmd_play
from core.music_player import MusicLoadError, MusicPlayer, _YDL_OPTS


ROOT = Path(__file__).resolve().parents[1]
MIN_FIXED_YTDLP = (2026, 8, 19)


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def test_ytdlp_manifests_exclude_broken_android_vr_default() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependency = next(
        item for item in pyproject["project"]["dependencies"] if item.startswith("yt-dlp==")
    )
    assert _version_tuple(dependency.removeprefix("yt-dlp==")) >= MIN_FIXED_YTDLP

    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    match = re.search(r"^yt-dlp>=(\d+(?:\.\d+)+)$", requirements, re.MULTILINE)
    assert match is not None
    assert _version_tuple(match.group(1)) >= MIN_FIXED_YTDLP


def test_ytdlp_uses_working_android_client_without_browser_cookies() -> None:
    youtube_args = _YDL_OPTS["extractor_args"]["youtube"]

    assert youtube_args["player_client"] == ["android"]
    assert "cookiefile" not in _YDL_OPTS
    assert "cookiesfrombrowser" not in _YDL_OPTS


class _FakePendingMessage:
    def __init__(self) -> None:
        self.content = ""

    async def edit(self, *, content: str) -> None:
        self.content = content


class _FakeMessage:
    def __init__(self) -> None:
        self.author = type("Author", (), {"display_name": "Bima"})()
        self.pending = _FakePendingMessage()

    async def reply(self, _content: str) -> _FakePendingMessage:
        return self.pending


class _FailingPlayer:
    current = None
    queue: list[object] = []

    async def connect(self, _voice_channel: object) -> bool:
        return True

    async def enqueue(self, _query: str, *, requester: str):
        del requester
        raise RuntimeError(
            "ERROR: Sign in to confirm you're not a bot; secret-stream-url"
        )


class _KnownLoadFailurePlayer(_FailingPlayer):
    async def enqueue(self, _query: str, *, requester: str):
        del requester
        raise MusicLoadError("YouTube lagi membatasi akses. Coba lagi sebentar.")


def test_play_command_hides_raw_extractor_error() -> None:
    message = _FakeMessage()

    asyncio.run(_cmd_play(message, _FailingPlayer(), "lagu", object()))  # type: ignore[arg-type]

    assert message.pending.content == "❌ Gagal cari/load audio. Coba lagi atau pakai URL lain."
    assert "secret-stream-url" not in message.pending.content


def test_play_command_shows_safe_known_load_error() -> None:
    message = _FakeMessage()

    asyncio.run(
        _cmd_play(message, _KnownLoadFailurePlayer(), "lagu", object())  # type: ignore[arg-type]
    )

    assert message.pending.content == "❌ YouTube lagi membatasi akses. Coba lagi sebentar."


class _FakeVoiceClient:
    def __init__(self, *, connected: bool, channel: object | None = None) -> None:
        self.connected = connected
        self.channel = channel
        self.disconnect_forces: list[bool] = []
        self.cleanup_calls = 0
        self.stop_calls = 0
        self.raise_disconnect = False
        self.raise_stop = False

    def is_connected(self) -> bool:
        return self.connected

    def stop(self) -> None:
        self.stop_calls += 1
        if self.raise_stop:
            raise RuntimeError("audio source already closed")

    async def disconnect(self, *, force: bool) -> None:
        self.disconnect_forces.append(force)
        if self.raise_disconnect:
            raise RuntimeError("voice websocket already dead")
        self.connected = False

    async def move_to(self, channel: object) -> None:
        self.channel = channel

    def cleanup(self) -> None:
        self.cleanup_calls += 1


class _FakeGuild:
    def __init__(self, voice_client: _FakeVoiceClient | None = None) -> None:
        self.id = 123
        self.voice_client = voice_client


class _FakeVoiceChannel:
    def __init__(self, connected_client: _FakeVoiceClient) -> None:
        self.connected_client = connected_client
        self.connect_calls: list[tuple[int, bool]] = []

    async def connect(self, *, timeout: int, reconnect: bool) -> _FakeVoiceClient:
        self.connect_calls.append((timeout, reconnect))
        return self.connected_client


def test_connect_reuses_connected_guild_voice_cache() -> None:
    channel = object()
    cached = _FakeVoiceClient(connected=True, channel=channel)
    player = MusicPlayer(_FakeGuild(cached))  # type: ignore[arg-type]

    assert asyncio.run(player.connect(channel)) is True  # type: ignore[arg-type]
    assert player.voice_client is cached


def test_connect_cleans_stale_guild_voice_before_reconnect() -> None:
    stale = _FakeVoiceClient(connected=False)
    fresh = _FakeVoiceClient(connected=True)
    channel = _FakeVoiceChannel(fresh)
    player = MusicPlayer(_FakeGuild(stale))  # type: ignore[arg-type]

    assert asyncio.run(player.connect(channel)) is True  # type: ignore[arg-type]
    assert stale.disconnect_forces == [True]
    assert channel.connect_calls == [(15, True)]
    assert player.voice_client is fresh


def test_disconnect_cleans_stale_guild_cache_without_local_reference() -> None:
    stale = _FakeVoiceClient(connected=False)
    player = MusicPlayer(_FakeGuild(stale))  # type: ignore[arg-type]

    assert asyncio.run(player.disconnect()) is True
    assert stale.disconnect_forces == [True]
    assert player.voice_client is None


def test_disconnect_uses_cleanup_when_voice_disconnect_raises() -> None:
    stale = _FakeVoiceClient(connected=False)
    stale.raise_disconnect = True
    player = MusicPlayer(_FakeGuild(stale))  # type: ignore[arg-type]

    assert asyncio.run(player.disconnect()) is True
    assert stale.cleanup_calls == 1


def test_disconnect_still_closes_voice_when_stop_raises() -> None:
    connected = _FakeVoiceClient(connected=True)
    connected.raise_stop = True
    player = MusicPlayer(_FakeGuild(connected))  # type: ignore[arg-type]

    assert asyncio.run(player.disconnect()) is True
    assert connected.disconnect_forces == [False]
