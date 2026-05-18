"""Music player Discord — per-guild voice client + queue.

Pattern:
    player = get_player(guild)
    await player.connect(voice_channel)
    await player.enqueue(query_or_url, requester)

Source: yt-dlp (YouTube/SoundCloud/direct URL). Streaming via FFmpegPCMAudio
dengan reconnect flags supaya gak drop saat network blip.
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from dataclasses import dataclass
from typing import Optional

import discord

logger = logging.getLogger("bima_core")

# Auto-disconnect kalau queue kosong + voice idle selama ini
_IDLE_DISCONNECT_SEC = 5 * 60

# Cap track per playlist (cegah enqueue 1000+ lagu sekaligus)
_MAX_PLAYLIST_TRACKS = 50

# Base yt-dlp options — bestaudio, quiet
_YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch1:",
    "source_address": "0.0.0.0",
}

# FFmpeg options
# - before: reconnect on network blip, -nostdin biar gak nyangkut nunggu stdin
# - opts: paksa output 48kHz stereo s16le (Discord native — kalau gak set, sample
#   rate dari source dipakai apa adanya → playback cepet/lambat kalau bukan 48k).
#   -bufsize lebarin buffer biar gak underrun di network jelek.
_FFMPEG_BEFORE = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin"
_FFMPEG_OPTS = "-vn -ar 48000 -ac 2 -f s16le -bufsize 1M -loglevel warning"


@dataclass
class Track:
    title: str
    url: str           # source URL (YouTube watch page atau direct)
    stream_url: str    # audio stream URL (extracted)
    duration: int      # seconds
    requester: str     # Discord username (display)
    thumbnail: str = ""

    def short(self) -> str:
        m, s = divmod(self.duration, 60)
        return f"**{self.title}** [{m}:{s:02d}] (req: {self.requester})"


def _is_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s.strip(), re.I))


def _is_youtube_playlist(url: str) -> bool:
    """YT playlist URL punya ?list= atau /playlist? param."""
    if not _is_url(url):
        return False
    return bool(re.search(r"[?&]list=[A-Za-z0-9_-]+", url, re.I))


async def _ytdl_extract_one(query: str) -> Track | None:
    """Full extract single track (return Track dengan stream_url siap pakai).
    noplaylist=True: kalau URL kebetulan ada di playlist, ambil track-nya doang."""
    try:
        import yt_dlp
    except ImportError:
        logger.error("[MUSIC] yt-dlp belum terinstall")
        return None

    def _extract():
        opts = {**_YDL_OPTS, "noplaylist": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                entries = info["entries"]
                if not entries:
                    return None
                info = entries[0]
            return info

    info = await asyncio.to_thread(_extract)
    if not info:
        return None

    return Track(
        title=info.get("title", "Unknown"),
        url=info.get("webpage_url") or info.get("url", ""),
        stream_url=info["url"],
        duration=int(info.get("duration") or 0),
        requester="",
        thumbnail=info.get("thumbnail", ""),
    )


async def _ytdl_extract_playlist(url: str, max_tracks: int = _MAX_PLAYLIST_TRACKS) -> list[Track]:
    """Flat extract playlist URL (cuma metadata, fast). Track.stream_url kosong —
    nanti fresh extract on demand di _play_next biar gak block enqueue."""
    try:
        import yt_dlp
    except ImportError:
        logger.error("[MUSIC] yt-dlp belum terinstall")
        return []

    def _extract():
        opts = {**_YDL_OPTS, "extract_flat": "in_playlist", "noplaylist": False}
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    info = await asyncio.to_thread(_extract)
    if not info or "entries" not in info:
        return []

    tracks: list[Track] = []
    for e in (info.get("entries") or [])[:max_tracks]:
        if not e:
            continue
        vid = e.get("id") or ""
        webpage = e.get("webpage_url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
        if not webpage:
            continue
        tracks.append(Track(
            title=e.get("title", "Unknown"),
            url=webpage,
            stream_url="",  # lazy fresh extract di _play_next
            duration=int(e.get("duration") or 0),
            requester="",
            thumbnail=e.get("thumbnail", ""),
        ))
    return tracks


class MusicPlayer:
    """Voice client + queue manager untuk satu guild."""

    def __init__(self, guild: discord.Guild):
        self.guild = guild
        self.voice_client: Optional[discord.VoiceClient] = None
        self.text_channel: Optional[discord.abc.Messageable] = None
        self.queue: deque[Track] = deque()
        self.current: Optional[Track] = None
        self.loop_mode: str = "off"  # off | track | queue
        self._idle_task: Optional[asyncio.Task] = None

    # -------- connection lifecycle --------

    async def connect(self, voice_channel: discord.VoiceChannel) -> bool:
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.channel == voice_channel:
                return True
            await self.voice_client.move_to(voice_channel)
            return True
        try:
            self.voice_client = await voice_channel.connect(timeout=15, reconnect=True)
            return True
        except Exception as e:
            logger.error(f"[MUSIC] Connect gagal: {e}", exc_info=True)
            return False

    async def disconnect(self):
        self._cancel_idle()
        self.queue.clear()
        self.current = None
        if self.voice_client and self.voice_client.is_connected():
            try:
                self.voice_client.stop()
                await self.voice_client.disconnect(force=False)
            except Exception:
                pass
        self.voice_client = None

    def _cancel_idle(self):
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    def _schedule_idle_disconnect(self):
        self._cancel_idle()

        async def _idle():
            await asyncio.sleep(_IDLE_DISCONNECT_SEC)
            if not self.queue and not self.current:
                logger.info(f"[MUSIC] Auto-disconnect guild={self.guild.id} (idle)")
                if self.text_channel:
                    try:
                        await self.text_channel.send("👋 Anisa keluar voice channel — idle 5 menit.")
                    except Exception:
                        pass
                await self.disconnect()

        self._idle_task = asyncio.create_task(_idle())

    # -------- enqueue / play --------

    async def enqueue(self, query: str, requester: str) -> tuple[Track | None, int]:
        """Return (first_added_track, count_added). count_added > 1 = playlist."""
        if _is_youtube_playlist(query):
            tracks = await _ytdl_extract_playlist(query)
            if not tracks:
                return None, 0
            for t in tracks:
                t.requester = requester
                self.queue.append(t)
            first = tracks[0]
            count = len(tracks)
        else:
            track = await _ytdl_extract_one(query)
            if not track:
                return None, 0
            track.requester = requester
            self.queue.append(track)
            first = track
            count = 1

        if self.voice_client and not self.voice_client.is_playing() and not self.current:
            await self._play_next()
        return first, count

    async def _play_next(self):
        self._cancel_idle()
        if not self.voice_client or not self.voice_client.is_connected():
            self.current = None
            return
        # Loop track mode: re-enqueue current di depan
        if self.loop_mode == "track" and self.current:
            self.queue.appendleft(self.current)
        # Loop queue mode: re-append current di belakang
        elif self.loop_mode == "queue" and self.current:
            self.queue.append(self.current)

        if not self.queue:
            self.current = None
            self._schedule_idle_disconnect()
            return

        next_track = self.queue.popleft()
        self.current = next_track

        # Lazy fresh-extract buat playlist track (stream_url kosong saat enqueue flat).
        # Juga handle: stream URL expired (YouTube tokens biasanya ~6 jam) — re-extract.
        if not next_track.stream_url:
            fresh = await _ytdl_extract_one(next_track.url)
            if not fresh:
                logger.warning(f"[MUSIC] Fresh extract gagal, skip: {next_track.title}")
                self.current = None
                await self._play_next()
                return
            next_track.stream_url = fresh.stream_url
            # Update title/duration kalau metadata flat tadi minimal
            if next_track.title == "Unknown":
                next_track.title = fresh.title
            if not next_track.duration:
                next_track.duration = fresh.duration

        try:
            source = discord.FFmpegPCMAudio(
                next_track.stream_url,
                before_options=_FFMPEG_BEFORE,
                options=_FFMPEG_OPTS,
            )
        except Exception as e:
            logger.error(f"[MUSIC] FFmpeg source gagal: {e}", exc_info=True)
            self.current = None
            await self._play_next()
            return

        def _after(error):
            if error:
                logger.error(f"[MUSIC] Playback error: {error}")
            # Schedule next track di event loop
            fut = asyncio.run_coroutine_threadsafe(self._play_next(), self.voice_client.loop)
            try:
                fut.result(timeout=5)
            except Exception:
                pass

        try:
            self.voice_client.play(source, after=_after)
        except Exception as e:
            logger.error(f"[MUSIC] play() gagal: {e}", exc_info=True)
            self.current = None
            await self._play_next()
            return

        if self.text_channel:
            try:
                await self.text_channel.send(f"🎵 Now playing: {next_track.short()}")
            except Exception:
                pass

    # -------- transport controls --------

    def skip(self) -> bool:
        if not self.voice_client or not self.voice_client.is_playing():
            return False
        self.voice_client.stop()  # triggers _after → _play_next
        return True

    def pause(self) -> bool:
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            return True
        return False

    def resume(self) -> bool:
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            return True
        return False

    async def stop(self):
        self.queue.clear()
        self.current = None
        self.loop_mode = "off"
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        self._schedule_idle_disconnect()

    def set_loop(self, mode: str) -> str:
        mode = (mode or "").lower().strip()
        if mode not in ("off", "track", "queue"):
            return self.loop_mode
        self.loop_mode = mode
        return self.loop_mode


# -------- global player registry --------

_players: dict[int, MusicPlayer] = {}


def get_player(guild: discord.Guild) -> MusicPlayer:
    p = _players.get(guild.id)
    if p is None:
        p = MusicPlayer(guild)
        _players[guild.id] = p
    return p


def remove_player(guild_id: int):
    _players.pop(guild_id, None)
