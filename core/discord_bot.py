import os
import re
import asyncio
import threading
import discord
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from core.utils import get_waktu, smart_chunks, extract_output_files
from core.langgraph_engine import run_langgraph_engine
from core.saham_scheduler import start_saham_scheduler
from core.saham_commands import handle_saham_command
from core.arsip_commands import handle_arsip_command
from core.furniture_qc import handle_qc_command
from core.cutlist import handle_cutlist_command
from core.ocr import handle_ocr_command
from core.music_commands import handle_music_command
from teams.t1_manager import simpan_sesi

# Logging diatur di main.py (loguru + stdlib intercept). Cukup ambil logger di sini.
logger = logging.getLogger('bima_core')

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
STATUS_CHANNEL_ID = os.getenv('BOT_STATUS_CHANNEL_ID')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# T2-A: Slash command tree (untuk /private start|stop opt-in thread isolation)
from discord import app_commands
tree = app_commands.CommandTree(client)

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Rate limiting store
_rate_limit = {}

# Anti-duplikat startup notif (Discord on_ready bisa fire ulang saat reconnect)
_startup_notified = False

# T2-A: Per-user private thread mapping (in-memory; persistence opsional via SQLite nanti)
# user_id (int) → discord_thread_id (int)
_private_threads: dict[int, int] = {}

# Debounce store untuk DM revision (mencegah resolve terlalu cepat saat masih ngetik)
_dm_debounce_timers: dict[str, asyncio.Task] = {}  # user_id -> debounce task
_dm_debounce_texts: dict[str, str] = {}              # user_id -> latest revision text


@tree.command(name="private", description="Mulai/akhiri dedicated thread privat dengan Anisa")
@app_commands.describe(action="Pilih 'start' untuk buka thread privat, 'stop' untuk akhiri")
@app_commands.choices(action=[
    app_commands.Choice(name="start", value="start"),
    app_commands.Choice(name="stop", value="stop"),
])
async def private_cmd(interaction: discord.Interaction, action: app_commands.Choice[str]):
    if os.environ.get("ENABLE_THREAD_ISOLATION", "true").lower() != "true":
        await interaction.response.send_message(
            "🔒 Fitur thread isolation disabled. Set `ENABLE_THREAD_ISOLATION=true` di .env.",
            ephemeral=True,
        )
        return

    user_id = interaction.user.id
    if action.value == "start":
        if user_id in _private_threads:
            await interaction.response.send_message(
                f"✨ Lu udah punya thread privat aktif: <#{_private_threads[user_id]}>",
                ephemeral=True,
            )
            return
        try:
            channel = interaction.channel
            if not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message(
                    "⚠️ `/private` cuma bisa dipakai di text channel biasa (bukan DM/thread).",
                    ephemeral=True,
                )
                return
            thread = await channel.create_thread(
                name=f"Anisa × {interaction.user.display_name}",
                type=discord.ChannelType.private_thread,
                invitable=False,
                reason="User opt-in private isolation via /private",
            )
            await thread.add_user(interaction.user)
            _private_threads[user_id] = thread.id
            await interaction.response.send_message(
                f"✨ Thread privat aktif: {thread.mention}. Lanjutin obrolan di sana ya.",
                ephemeral=True,
            )
            try:
                await thread.send(
                    f"Hai {interaction.user.mention}! Ini thread privat lu sama Anisa. "
                    f"Context isolated dari channel utama — ketik `/private` stop kalau mau akhirin."
                )
            except Exception:
                pass
            logger.info(f"[PRIVATE] user={user_id} thread={thread.id} created")
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Bot ga punya izin bikin private thread di channel ini.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"[PRIVATE] start gagal user={user_id}: {e}", exc_info=True)
            await interaction.response.send_message(f"⚠️ Gagal bikin thread: `{e}`", ephemeral=True)
    elif action.value == "stop":
        thread_id = _private_threads.pop(user_id, None)
        if not thread_id:
            await interaction.response.send_message(
                "Lu lagi gak punya thread privat aktif.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "✨ Thread privat di-stop. Kembali ke channel mode biasa.", ephemeral=True
        )
        logger.info(f"[PRIVATE] user={user_id} thread={thread_id} stopped")


def _build_startup_embed() -> discord.Embed:
    embed = discord.Embed(
        title='🟢 ANISA ONLINE • B.I.M.A CORE',
        description=(
            '**Semua sistem aktif — 8 tim siap dipakai.**\n'
            '> Mention **@Anisa** atau kirim **DM**, lalu langsung tulis tugasmu.\n'
            '`@Anisa buat ...` • Lampirkan file bila diperlukan.'
        ),
        color=0x22C55E,
        timestamp=datetime.now()
    )
    sections = [
        ('🧠 RISET & MEMORI',
         '**T1 Manager** — orkestrasi & memori\n'
         '**T3 Arsip** — vault & semantic search\n'
         '**T5 Intel** — riset web & OSINT\n'
         '**T6 Lifestyle** — cuaca, jadwal & maps', True),
        ('🎨 VISUAL & PRODUKSI',
         '**T2 Visual** — baca file & analisis gambar\n'
         '**T4 Admin** — Word, Excel, PDF & chart\n'
         '**T7 Seniman** — HTML, SVG & Mermaid\n'
         '**T8 Mekanik** — coding, Git & security', True),
        ('⚡ TOOLS & FILE',
         '`!status` — cek kesehatan VPS\n'
         '`!ocr` + gambar — ambil teks dari gambar\n'
         '`!qc` + drawing — QC gambar furnitur\n'
         '`!cutlist` — optimasi potongan panel\n'
         '`!arsip help` — menu vault & catatan', True),
        ('📈 CONTENT & MARKET',
         '`!saham help` — analisis, chart & portfolio\n'
         '`!threads <topik>` — buat draft Threads\n'
         '`/private start|stop` — buka/tutup thread privat', True),
        ('🎵 MUSIC CONTROL',
         '`!play <judul>` — putar lagu  •  `!queue` — lihat antrean\n'
         '`!skip` — lewati  •  `!pause` / `!resume` — jeda/lanjut\n'
         '`!stop` / `!leave` — hentikan  •  `!np` / `!loop` — status/ulang\n'
         '`!music` — tampilkan menu musik lengkap', False),
    ]
    for name, description, inline in sections:
        embed.add_field(name=name, value=description, inline=inline)
    embed.set_footer(text='B.I.M.A Core • CrewAI × LangGraph • Ready when you are')
    return embed


@client.event
async def on_ready():
    global _startup_notified
    logger.info(f'✨ B.I.M.A Core FULL SYSTEM online sebagai {client.user}!')
    logger.info('8 Team + Memory + Real-time + File Reader siap tempur! 🚀')

    # Register main event loop for permission gate
    from core.permission_gate import set_main_loop
    set_main_loop(asyncio.get_running_loop())

    if _startup_notified:
        logger.info('Reconnect terdeteksi, skip startup notif duplikat')
        return
    _startup_notified = True

    # T1-A: Init async checkpointer (idempotent, no-op kalau ENABLE_CHECKPOINTING=false)
    try:
        from core.langgraph_engine import init_engine
        await init_engine()
    except Exception as e:
        logger.error(f'Gagal init checkpoint engine (bot tetap jalan tanpa persistence): {e}', exc_info=True)

    # T2-A: Sync slash command tree (sekali per startup; idempotent)
    try:
        synced = await tree.sync()
        logger.info(f'[TREE] Slash commands synced: {len(synced)}')
    except Exception as e:
        logger.warning(f'[TREE] Sync slash commands gagal (non-fatal): {e}')

    try:
        start_saham_scheduler(client)
    except Exception as e:
        logger.error(f'Gagal start saham scheduler: {e}', exc_info=True)

    # T1-G: Briefing scheduler (opt-in via ENABLE_BRIEFING=true)
    try:
        from core.briefing_scheduler import start_briefing_scheduler
        start_briefing_scheduler(client)
    except Exception as e:
        logger.error(f'Gagal start briefing scheduler: {e}', exc_info=True)

    # Threads posting scheduler (opt-in via ENABLE_THREADS_AUTO=true)
    try:
        from core.threads_scheduler import start_threads_scheduler
        start_threads_scheduler(client)
    except Exception as e:
        logger.error(f'Gagal start threads scheduler: {e}', exc_info=True)

    # Observability scheduler (opt-in via ENABLE_OBSERVABILITY=true)
    try:
        from core.observability_scheduler import start_observability_scheduler
        start_observability_scheduler(client)
    except Exception as e:
        logger.error(f'Gagal start observability scheduler: {e}', exc_info=True)

    try:
        from core.mekanik_maintenance_scheduler import start_mekanik_maintenance_scheduler
        start_mekanik_maintenance_scheduler(client)
    except Exception as e:
        logger.error(f'Gagal start Mekanik maintenance scheduler: {e}', exc_info=True)

    def _warmup_reranker():
        try:
            from teams.t3_arsip import _get_reranker
            _get_reranker()
            logger.info('[WARMUP] Cross-encoder reranker siap.')
        except Exception as e:
            logger.warning(f'[WARMUP] Reranker warmup gagal: {e}')
    threading.Thread(target=_warmup_reranker, daemon=True, name='reranker-warmup').start()

    if not STATUS_CHANNEL_ID:
        logger.warning('BOT_STATUS_CHANNEL_ID belum di-set di .env, skip startup notification')
        return

    try:
        channel = client.get_channel(int(STATUS_CHANNEL_ID))
        if channel is None:
            channel = await client.fetch_channel(int(STATUS_CHANNEL_ID))
        from core.notify import safe_notify
        ok = await safe_notify(
            channel,
            embed=_build_startup_embed(),
            content='✨ Anisa B.I.M.A Core online',
            title='Anisa Startup',
        )
        if ok:
            logger.info(f'✅ Startup notif terkirim ke channel {STATUS_CHANNEL_ID}')
        else:
            logger.warning('Startup notif gagal di semua channel (Discord + apprise)')
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        logger.error(f'Channel notif tidak ditemukan / tidak ada izin: {e}')
        from core.notify import broadcast_critical
        await broadcast_critical(f'Channel notif Discord error: {e}', title='Anisa Startup')
    except ValueError:
        logger.error(f'BOT_STATUS_CHANNEL_ID bukan angka valid: {STATUS_CHANNEL_ID}')
    except Exception as e:
        logger.error(f'Gagal kirim startup notif: {e}', exc_info=True)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.author.bot:
        return

    # DM Interception for pending approvals (revision gate)
    # Debounce 5 detik: kalau Bima kirim DM lagi dalam 5 detik, teks baru replace teks lama
    # PENTING: Revisi TIDAK auto-approve. Harus tetap klik 👍/👎 setelah preview revisi.
    if isinstance(message.channel, discord.DMChannel):
        from core.permission_gate import get_pending_req_id_by_user, resolve_approval_with_revision, resolve_approval
        req_id = get_pending_req_id_by_user(str(message.author.id))
        if req_id:
            revised_text = message.content.strip()
            user_id_str = str(message.author.id)
            
            # Cek jika input text adalah perintah pembatalan / tolak
            cancel_keywords = {"tolak", "batal", "cancel", "no", "reject", "jangan", "pembatalan", "tidak"}
            clean_text = re.sub(r'[^\w\s]', '', revised_text.lower()).strip()
            if clean_text in cancel_keywords:
                logger.info(f"[DM_APPROVAL] Bima membatalkan request {req_id} via pesan teks: '{revised_text}'")
                if user_id_str in _dm_debounce_timers:
                    _dm_debounce_timers[user_id_str].cancel()
                    _dm_debounce_timers.pop(user_id_str, None)
                _dm_debounce_texts.pop(user_id_str, None)
                resolve_approval(req_id, False)
                await message.reply("❌ **Tindakan dibatalkan/ditolak oleh Bima.**")
                return

            # Simpan revisi terbaru + cancel timer sebelumnya (last-write-wins)
            if user_id_str in _dm_debounce_timers:
                _dm_debounce_timers[user_id_str].cancel()
            _dm_debounce_texts[user_id_str] = revised_text
            
            async def _finalize_revision(uid: str, rid: str):
                """Setelah 5 detik tanpa pesan baru, generate preview revisi dan kirim
                pesan BARU dengan 👍/👎 untuk persetujuan eksplisit.
                TIDAK auto-approve — Bima harus klik reaksi."""
                await asyncio.sleep(5)
                final_revision_input = _dm_debounce_texts.pop(uid, revised_text)
                _dm_debounce_timers.pop(uid, None)
                
                # Lookup the original draft from the stored approval message
                original_draft = None
                for msg_id, (stored_req_id, stored_uid, action_type, details) in _discord_approval_messages.items():
                    if stored_req_id == rid:
                        original_draft = details
                        break
                
                # Generate revised draft preview using smart revision
                try:
                    from core.threads_commands import apply_smart_revision
                    if original_draft:
                        revised_draft = await apply_smart_revision(original_draft, final_revision_input)
                    else:
                        revised_draft = final_revision_input
                except Exception as e:
                    logger.error(f"[DM_REVISION] Gagal generate smart revision: {e}")
                    revised_draft = final_revision_input
                
                # Simpan revised text untuk nanti di-consume saat approved
                from core.permission_gate import _revised_texts
                _revised_texts[uid] = revised_draft
                
                # Kirim preview revisi sebagai pesan BARU dengan 👍/👎
                # User HARUS klik reaksi untuk approve/reject
                try:
                    user = await client.fetch_user(int(uid))
                    if user:
                        dm_channel = user.dm_channel or await user.create_dm()
                        preview_msg = await dm_channel.send(
                            f"📝 **DRAF REVISI THREADS** 📝\n\n"
                            f"Hasil revisi berdasarkan masukan lu:\n\n"
                            f"{revised_draft[:1800]}\n\n"
                            f"👍 **Setuju & Publish**  |  👎 **Tolak/Batal**\n"
                            f"💬 Atau **balas lagi** buat revisi ulang!"
                        )
                        await preview_msg.add_reaction("👍")
                        await preview_msg.add_reaction("👎")
                        
                        # Register pesan baru ini di approval messages (pakai req_id yang sama)
                        _discord_approval_messages[preview_msg.id] = (rid, uid, "THREADS_POST", revised_draft)
                        logger.info(f"[DM_REVISION] Preview revisi terkirim ke {uid}, menunggu 👍/👎 eksplisit")
                except Exception as e:
                    logger.error(f"[DM_REVISION] Gagal kirim preview revisi ke DM: {e}")
            
            task = asyncio.create_task(_finalize_revision(user_id_str, req_id))
            _dm_debounce_timers[user_id_str] = task
            
            await message.reply("📝 **Revisi diterima!** Tunggu 5 detik — kalau lu mau nambah/ganti, kirim lagi aja...")
            return

    # Rate limit: max 1 request per 3 detik per user
    uid = message.author.id
    now_ts = datetime.now().timestamp()
    if uid in _rate_limit and now_ts - _rate_limit[uid] < 3:
        return
    _rate_limit[uid] = now_ts
    # Cleanup entries > 60s
    for k in list(_rate_limit.keys()):
        if now_ts - _rate_limit[k] > 60:
            del _rate_limit[k]

    waktu_sekarang = get_waktu()
    logger.info(f"Chat dari {message.author}: '{message.content}'")

    perintah = message.content
    if client.user in message.mentions:
        perintah = perintah.replace(f'<@{client.user.id}>', '').replace(f'<@!{client.user.id}>', '').strip()

    # Voice-only Discord upload: perintah boleh kosong asal ada audio attachment
    _DISCORD_AUDIO_EXTS = {".ogg", ".oga", ".opus", ".mp3", ".m4a", ".wav", ".flac", ".aac"}
    has_audio_attachment = any(
        Path(att.filename).suffix.lower() in _DISCORD_AUDIO_EXTS
        for att in (message.attachments or [])
    )

    if not perintah and not has_audio_attachment:
        return

    # === !saham command pre-route ===
    if perintah.lower().startswith("!saham"):
        args = perintah[6:].strip()
        await handle_saham_command(message, args, bot_client=client)
        return

    # === !arsip command pre-route ===
    if perintah.lower().startswith("!arsip"):
        args = perintah[6:].strip()
        await handle_arsip_command(message, args, bot_client=client)
        return

    # === !threads command pre-route ===
    if perintah.lower().startswith("!threads") or perintah.lower().startswith("!thread"):
        slice_len = 8 if perintah.lower().startswith("!threads") else 7
        args = perintah[slice_len:].strip()
        from core.threads_commands import handle_threads_command
        await handle_threads_command(message, args, bot_client=client)
        return

    # === !qc command (furniture drawing QC) ===
    if perintah.lower().startswith("!qc"):
        await handle_qc_command(message, bot_client=client)
        return

    # === !cutlist command (2D bin packing buat panel kayu) ===
    if perintah.lower().startswith("!cutlist"):
        await handle_cutlist_command(message)
        return

    # === !ocr command (extract text dari image) ===
    if perintah.lower().startswith("!ocr"):
        await handle_ocr_command(message, bot_client=client)
        return

    # === !status command (VPS health snapshot) ===
    if perintah.lower().startswith("!status"):
        try:
            from core.system_metrics import snapshot, format_status_text
            snap = snapshot()
            await message.reply(format_status_text(snap))
        except Exception as e:
            await message.reply(f"❌ Gagal ambil status: `{e}`")
        return

    # === Music commands (!play, !skip, !queue, !pause, !resume, !stop, !np, !leave, !loop, !music) ===
    _music_prefixes = ("!play", "!skip", "!queue", "!q ", "!pause", "!resume",
                       "!stop", "!np", "!leave", "!loop", "!music", "!musik")
    _lower = perintah.lower().strip()
    if _lower == "!q" or _lower.startswith(_music_prefixes):
        await handle_music_command(message, perintah)
        return

    # ============================================================
    # TANGKAP ATTACHMENT + AUTO-DOWNLOAD
    # ============================================================
    downloaded_files = []
    audio_files = []
    attachment_info = ""
    
    if message.attachments:
        # Discord max 25MB; reject lebih awal supaya gak buang bandwidth
        MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
        ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
                        ".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".md", ".json",
                        ".ogg", ".oga", ".opus", ".mp3", ".m4a", ".wav", ".flac", ".aac"}

        urls = [att.url for att in message.attachments]
        attachment_info = f"\n\n[ATTACHMENT] File dari Bima: {', '.join(urls)}"

        for att in message.attachments:
            ext = Path(att.filename).suffix.lower()
            if ext not in ALLOWED_EXTS:
                logger.warning(f"Tolak attachment ekstensi tidak diizinkan: {att.filename}")
                await message.reply(f"⚠️ Maaf Bima, ekstensi `{ext or '?'}` tidak didukung.")
                continue
            if att.size and att.size > MAX_ATTACHMENT_BYTES:
                size_mb = att.size / 1024 / 1024
                logger.warning(f"Tolak attachment kebesaran: {att.filename} ({size_mb:.1f}MB)")
                await message.reply(f"⚠️ File `{att.filename}` terlalu besar ({size_mb:.1f}MB). Max 25MB.")
                continue
            try:
                filename = f"discord_{os.urandom(4).hex()}{ext}"
                filepath = OUTPUT_DIR / filename
                await att.save(filepath)
                downloaded_files.append(str(filepath))
                logger.info(f"File didownload: {filename} ({filepath.stat().st_size} bytes)")
            except Exception as e:
                logger.error(f"Gagal download attachment {att.filename}: {e}", exc_info=True)
        
        # Split audio (untuk STT) dari attachment lain (visual/canvas/dll)
        audio_files = [p for p in downloaded_files if Path(p).suffix.lower() in _DISCORD_AUDIO_EXTS]
        other_files = [p for p in downloaded_files if Path(p).suffix.lower() not in _DISCORD_AUDIO_EXTS]

        # Transcribe semua audio attachment (auto, gak perlu arming)
        if audio_files:
            from core.stt import transcribe_audio
            transcripts = []
            for ap in audio_files:
                text = await asyncio.to_thread(transcribe_audio, ap, "id")
                if text:
                    transcripts.append(text)
            logger.info(f"[DISCORD STT] {len(transcripts)}/{len(audio_files)} audio ditranscribe")
            if transcripts:
                # Prepend transcript jadi konteks utama, caption text ke-append
                tr_block = "[VOICE TRANSCRIPT]\n" + "\n".join(transcripts)
                perintah = f"{tr_block}\n\n{perintah}" if perintah else tr_block

        # Auto-append "baca file" cuma kalau ada non-audio attachment + perintah belum nyebut keyword
        if other_files and not any(k in perintah.lower() for k in ['gambar', 'foto', 'pdf', 'lihat', 'analisis', 'baca', 'baca file', 'voice transcript']):
            perintah += " baca file"

        # Replace downloaded_files dengan non-audio biar visual_node ga error analyze audio
        downloaded_files = other_files

    perintah_lengkap = perintah + attachment_info
    if downloaded_files:
        perintah_lengkap += f"\n\n[FILE_PATHS] File sudah didownload ke: {' | '.join(downloaded_files)}"

    konteks_waktu = f"""
=== KONTEKS WAKTU REAL-TIME ===
Sekarang: {waktu_sekarang}
Gunakan info waktu ini saat menjawab pertanyaan tentang hari ini, sekarang, atau waktu terkini.
Saat mencari data real-time, gunakan tahun/bulan yang sesuai.
================================"""

    # T1-D: Daily LLM cost guardrail — block kalau user sudah lewat budget hari ini
    try:
        from core.gen_rate_limit import check_daily_cost
        allowed, err_msg = check_daily_cost(str(message.author.id))
        if not allowed:
            await message.reply(err_msg)
            return
    except Exception as e:
        logger.debug(f"[cost_guard] check skipped (non-fatal): {e}")

    try:
        logger.info(f"LangGraph Engine mengolah permintaan: {perintah}")
        pesan_tunggu = await message.reply("⏳ *Anisa (LangGraph) sedang memproses...*")

        async def update_progress(content: str):
            try:
                await pesan_tunggu.edit(content=content)
            except discord.errors.HTTPException as e:
                logger.warning(f"Skip update progress (HTTP): {e}")
            except Exception as e:
                logger.warning(f"Skip update progress: {e}")

        # Eksekusi LangGraph secara Asynchronous
        hasil_str = await run_langgraph_engine(
            user_request=perintah_lengkap,
            konteks_waktu=konteks_waktu,
            attachment_paths=downloaded_files,
            progress_callback=update_progress,
            discord_user_id=str(message.author.id),
            source_channel="discord",
        )
        
        # Simpan sesi (untuk histori dan memori)
        simpan_sesi(perintah_lengkap, hasil_str)

        # Bersihkan baris SUCCESS dari teks tampilan agar user tidak lihat raw metadata
        display_str = re.sub(r'\nSUCCESS\|[^\n]+', '', hasil_str).strip()

        # Fallback kalau strip ngosongin semua (agent reply cuma SUCCESS|...|... single line):
        # ambil bagian <msg> setelah pipe ketiga supaya user lihat sesuatu yang bermakna.
        if not display_str:
            tail_msg = re.sub(r'^SUCCESS\|[^|]*\|', '', hasil_str.strip(), flags=re.MULTILINE).strip()
            display_str = tail_msg or "✅ Tugas selesai. Cek file lampiran kalau ada."

        # TTS auto-mirror: kalau input lewat audio attachment, reply pakai voice juga.
        # 'full' (reply <=80 chars): voice baca lengkap. 'opener' (>80 chars): voice basa-basi + text full.
        voice_path = None
        voice_mode = None
        if audio_files and display_str:
            from core.tts import synthesize_voice, decide_voice_mode, generate_opener
            voice_mode = decide_voice_mode(display_str)
            if voice_mode == "full":
                voice_path = await synthesize_voice(display_str, slug_hint="dc")
            elif voice_mode == "opener":
                opener_text = await generate_opener(display_str)
                voice_path = await synthesize_voice(opener_text, slug_hint="dc_op")

        # Voice "full" mode → kirim voice doang (chunks[0] tetep kirim sbg fallback display)
        # Voice "opener" mode → kirim text full + 1 voice basa-basi context-aware
        chunks = smart_chunks(display_str)
        await pesan_tunggu.edit(content=chunks[0])
        for chunk in chunks[1:]:
            await message.reply(chunk)

        # Kirim voice attachment kalau ada
        if voice_path:
            try:
                await message.reply(file=discord.File(str(voice_path)))
            except Exception as e:
                logger.warning(f"Gagal kirim TTS voice ke Discord: {e}")

        # Ekstrak file dari string asli (bukan display_str) agar path tetap terdeteksi
        output_files = extract_output_files(hasil_str)
        if output_files:
            await message.reply(
                f"📎 *File siap didownload ({len(output_files)} file):*",
                files=[discord.File(str(f)) for f in output_files[:10]]
            )

    except discord.errors.Forbidden:
        logger.error("Nggak punya izin di channel ini!")
    except Exception as e:
        logger.error(f"ERROR SISTEM: {e}", exc_info=True)
        try:
            await message.reply(f"Aduh Bima sayang, ada error: `{e}`")
        except Exception as reply_err:
            logger.error(f"Gagal kirim pesan error ke Discord: {reply_err}")

# ============================================================
# INTERACTIVE PERMISSION GATE INTEGRATION
# ============================================================
from core.permission_gate import register_send_handler, resolve_approval

_discord_approval_messages = {} # message_id -> (req_id, user_id, action_type, details)

async def send_discord_approval(req_id: str, discord_user_id: str, action_type: str, details: str, attachment_paths: list[str] = None) -> bool:
    try:
        user = await client.fetch_user(int(discord_user_id))
        if not user:
            logger.warning(f"[PERMISSION_GATE] User {discord_user_id} not found.")
            return False
        
        dm_channel = user.dm_channel or await user.create_dm()
        if action_type == "BOM_APPROVAL":
            msg_text = (
                f"📋 **PERSETUJUAN DAFTAR BAHAN (BOM) & HARGA** 📋\n\n"
                f"Anisa mendeteksi permintaan penulisan BOM ke slide.\n"
                f"Silakan tinjau rincian daftar bahan berikut:\n\n"
                f"{details[:1500]}\n\n"
                f"Apakah draf BOM di atas sudah benar untuk dimasukkan ke slide presentasi?\n"
                f"👍 **Setuju (Approve)**  |  👎 **Tolak (Reject)**"
            )
        elif action_type == "SLIDE_PREVIEW_APPROVAL":
            msg_text = (
                f"🎨 **TINJAUAN PREVIEW SLIDE PRESENTASI** 🎨\n\n"
                f"Anisa telah selesai menyusun draf visual slide presentasi.\n"
                f"Silakan tinjau gambar preview di bawah:\n\n"
                f"{details[:1500]}\n\n"
                f"Apakah desain slide di atas sudah oke untuk dicompile final?\n"
                f"👍 **Setuju (Approve & Compile)**  |  👎 **Revisi (Reject)**"
            )
        elif action_type in ("THREADS_POST", "THREADS_REPLY"):
            msg_text = (
                f"📝 **DRAF POSTINGAN THREADS** 📝\n\n"
                f"Anisa udah buatin draf postingan buat Threads lu:\n\n"
                f"{details[:1800]}\n\n"
                f"👍 **Setuju & Publish**  |  👎 **Tolak**\n"
                f"💬 Atau **balas langsung** di sini buat revisi draftnya!"
            )
        else:
            msg_text = (
                f"⚠️ **IZIN AKSES SISTEM DETEKSI** ⚠️\n\n"
                f"Anisa mendeteksi tindakan tingkat sistem berikut:\n"
                f"• **Tindakan**: `{action_type}`\n"
                f"• **Detail**:\n```python\n{details[:1200]}\n```\n\n"
                f"Apakah kamu mengizinkan tindakan ini?\n"
                f"👍 **Setuju**  |  👎 **Tolak**"
            )
        
        files = [discord.File(str(fp)) for fp in attachment_paths] if attachment_paths else None
        msg = await dm_channel.send(msg_text, files=files)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        
        _discord_approval_messages[msg.id] = (req_id, discord_user_id, action_type, details)
        return True
    except Exception as e:
        logger.error(f"[PERMISSION_GATE] Gagal kirim DM approval ke {discord_user_id}: {e}", exc_info=True)
        return False

register_send_handler(send_discord_approval)

@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id == client.user.id:
        return
    msg_id = payload.message_id
    if msg_id in _discord_approval_messages:
        req_id, target_user_id, action_type, details = _discord_approval_messages[msg_id]
        if str(payload.user_id) == target_user_id:
            emoji_str = str(payload.emoji)
            
            # Fetch message since it might be uncached (especially after restarts)
            try:
                channel = client.get_channel(payload.channel_id)
                if not channel:
                    channel = await client.fetch_channel(payload.channel_id)
                message = await channel.fetch_message(msg_id)
            except Exception as e:
                logger.error(f"Gagal fetch message untuk raw reaction: {e}")
                return
                
            if emoji_str == "👍":
                resolve_approval(req_id, True)
                try:
                    if action_type == "BOM_APPROVAL":
                        await message.edit(content=f"✅ **BOM DISETUJUI BIMA**\n\n{details[:1200]}\n\nStatus: Disetujui.")
                    elif action_type == "SLIDE_PREVIEW_APPROVAL":
                        await message.edit(content=f"✅ **PREVIEW SLIDE DISETUJUI BIMA**\n\n{details[:1200]}\n\nStatus: Disetujui, sedang memproses compile final...")
                    elif action_type in ("THREADS_POST", "THREADS_REPLY"):
                        await message.edit(content=f"✅ **DRAF THREADS DISETUJUI BIMA**\n\n{details[:1800]}\n\nStatus: Sukses dipublikasikan.")
                    else:
                        await message.edit(content=f"✅ **TINDAKAN DISETUJUI BIMA**\n```python\n# {action_type}\n{details[:500]}\n```\nStatus: Sukses disetujui.")
                except Exception as e:
                    logger.warning(f"Gagal edit approval message: {e}")
            elif emoji_str == "👎":
                resolve_approval(req_id, False)
                try:
                    if action_type == "BOM_APPROVAL":
                        await message.edit(content=f"❌ **BOM DITOLAK BIMA**\n\n{details[:1200]}\n\nStatus: Ditolak.")
                    elif action_type == "SLIDE_PREVIEW_APPROVAL":
                        await message.edit(content=f"❌ **PREVIEW SLIDE DITOLAK BIMA**\n\n{details[:1200]}\n\nStatus: Ditolak (butuh revisi).")
                    elif action_type in ("THREADS_POST", "THREADS_REPLY"):
                        await message.edit(content=f"❌ **DRAF THREADS DIBATALKAN**\n\n{details[:1800]}\n\nStatus: Batal/Ditolak.")
                    else:
                        await message.edit(content=f"❌ **TINDAKAN DITOLAK BIMA**\n```python\n# {action_type}\n{details[:500]}\n```\nStatus: Pembatalan.")
                except Exception as e:
                    logger.warning(f"Gagal edit approval message: {e}")


def run_bot():
    # Dashboard server start di main.py (host=127.0.0.1 loopback-only — cloudflared
    # tunnel yg expose ke internet, ga perlu bind 0.0.0.0).
    if DISCORD_TOKEN:
        client.run(DISCORD_TOKEN)
    else:
        logger.critical("DISCORD_TOKEN tidak ditemukan di .env!")
