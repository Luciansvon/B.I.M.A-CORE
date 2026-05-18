"""Music command handler buat Discord. Pattern serupa handle_saham_command.

Usage di discord_bot.py:
    if perintah.lower().startswith(("!play", "!skip", "!queue", "!q ", "!q\\n",
                                    "!pause", "!resume", "!stop", "!np", "!leave", "!loop")):
        await handle_music_command(message, perintah)
        return
"""
from __future__ import annotations

import logging

import discord

from core.music_player import get_player, MusicPlayer

logger = logging.getLogger("bima_core")


_HELP = (
    "🎵 **Music commands:**\n"
    "`!play <judul/URL>` — putar lagu (auto-join voice channel kamu)\n"
    "`!skip` — skip lagu sekarang\n"
    "`!pause` / `!resume` — pause/lanjut\n"
    "`!queue` / `!q` — lihat antrian\n"
    "`!np` — now playing\n"
    "`!loop [off|track|queue]` — set mode loop\n"
    "`!stop` — clear queue\n"
    "`!leave` — keluar voice channel"
)


async def handle_music_command(message: discord.Message, raw: str) -> None:
    """Entry point — dispatch berdasarkan first token."""
    text = raw.strip()
    parts = text.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    if not message.guild:
        await message.reply("❌ Music command cuma jalan di server Discord, bukan DM.")
        return

    player = get_player(message.guild)
    player.text_channel = message.channel

    # Voice channel resolution dari author (cuma penting buat !play / !leave)
    author_voice = getattr(message.author, "voice", None)
    user_vc: discord.VoiceChannel | None = (
        author_voice.channel if author_voice and author_voice.channel else None
    )

    if cmd == "!play":
        await _cmd_play(message, player, args, user_vc)
    elif cmd == "!skip":
        await _cmd_skip(message, player)
    elif cmd in ("!queue", "!q"):
        await _cmd_queue(message, player)
    elif cmd == "!pause":
        await _cmd_pause(message, player)
    elif cmd == "!resume":
        await _cmd_resume(message, player)
    elif cmd == "!stop":
        await _cmd_stop(message, player)
    elif cmd == "!np":
        await _cmd_np(message, player)
    elif cmd == "!leave":
        await _cmd_leave(message, player)
    elif cmd == "!loop":
        await _cmd_loop(message, player, args)
    elif cmd in ("!music", "!musik"):
        await message.reply(_HELP)
    else:
        await message.reply(_HELP)


async def _cmd_play(message: discord.Message, player: MusicPlayer, args: str, user_vc):
    if not args:
        await message.reply("Pakai: `!play <judul lagu atau URL YouTube/SoundCloud>`")
        return
    if not user_vc:
        await message.reply("❌ Kamu harus join voice channel dulu sebelum `!play`.")
        return

    # Connect / move ke voice channel user
    ok = await player.connect(user_vc)
    if not ok:
        await message.reply("❌ Anisa gak bisa connect ke voice channel-mu.")
        return

    pending = await message.reply(f"🔍 Cari `{args[:80]}`...")
    try:
        first, count = await player.enqueue(args, requester=message.author.display_name)
    except Exception as e:
        logger.error(f"[MUSIC] enqueue error: {e}", exc_info=True)
        await pending.edit(content=f"❌ Gagal cari/load: `{e}`")
        return

    if not first or count == 0:
        await pending.edit(content="❌ Lagu gak ketemu atau yt-dlp gagal extract.")
        return

    if count > 1:
        await pending.edit(content=f"📋 Playlist enqueued: **{count} tracks**. First: {first.short()}")
    else:
        # Kalau queue kosong tadi → langsung play. Kalau ada queue → kasih posisi.
        pos = len(player.queue)
        if player.current and player.current is not first and pos > 0:
            await pending.edit(content=f"➕ Antri #{pos}: {first.short()}")
        else:
            await pending.edit(content=f"▶️ {first.short()}")


async def _cmd_skip(message: discord.Message, player: MusicPlayer):
    if player.skip():
        await message.reply("⏭️ Skipped.")
    else:
        await message.reply("Gak ada yang lagi diputer.")


async def _cmd_queue(message: discord.Message, player: MusicPlayer):
    if not player.queue and not player.current:
        await message.reply("Queue kosong.")
        return
    lines: list[str] = []
    if player.current:
        lines.append(f"▶️ Now: {player.current.short()}")
    for i, t in enumerate(list(player.queue)[:10], start=1):
        lines.append(f"`#{i}` {t.short()}")
    extra = len(player.queue) - 10
    if extra > 0:
        lines.append(f"... (+{extra} lagi)")
    if player.loop_mode != "off":
        lines.append(f"🔁 Loop: `{player.loop_mode}`")
    await message.reply("\n".join(lines))


async def _cmd_pause(message: discord.Message, player: MusicPlayer):
    if player.pause():
        await message.reply("⏸️ Paused.")
    else:
        await message.reply("Gak ada yang lagi diputer / udah paused.")


async def _cmd_resume(message: discord.Message, player: MusicPlayer):
    if player.resume():
        await message.reply("▶️ Resumed.")
    else:
        await message.reply("Gak ada yang paused.")


async def _cmd_stop(message: discord.Message, player: MusicPlayer):
    await player.stop()
    await message.reply("⏹️ Stopped + queue cleared.")


async def _cmd_np(message: discord.Message, player: MusicPlayer):
    if not player.current:
        await message.reply("Gak ada yang lagi diputer.")
        return
    extra = f" (queue: {len(player.queue)} lagu)" if player.queue else ""
    await message.reply(f"🎵 Now playing: {player.current.short()}{extra}")


async def _cmd_leave(message: discord.Message, player: MusicPlayer):
    if not player.voice_client or not player.voice_client.is_connected():
        await message.reply("Anisa gak lagi di voice channel.")
        return
    await player.disconnect()
    await message.reply("👋 Keluar voice channel.")


async def _cmd_loop(message: discord.Message, player: MusicPlayer, args: str):
    mode = args.lower().strip() or ("off" if player.loop_mode != "off" else "track")
    if mode not in ("off", "track", "queue"):
        await message.reply("Mode loop: `off` | `track` | `queue`")
        return
    result = player.set_loop(mode)
    await message.reply(f"🔁 Loop: `{result}`")
