import os
import re
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
from teams.t1_manager import simpan_sesi

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('bima_core')

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
STATUS_CHANNEL_ID = os.getenv('BOT_STATUS_CHANNEL_ID')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Rate limiting store
_rate_limit = {}

# Anti-duplikat startup notif (Discord on_ready bisa fire ulang saat reconnect)
_startup_notified = False


def _build_startup_embed() -> discord.Embed:
    embed = discord.Embed(
        title='✨ Anisa B.I.M.A Core — Online',
        description=(
            'Halo Bima, Anisa sudah aktif dan siap membantu! 🚀\n'
            'Mention aku atau DM langsung untuk mulai.'
        ),
        color=0x6366F1,
        timestamp=datetime.now()
    )
    teams = [
        ('🧠 T1 — Manager',
         'Orkestrasi tugas, memori jangka panjang, simpan fakta tentang Bima'),
        ('📂 T2 — Visual',
         'Baca PDF / Excel / Word / CSV / gambar, analisis visual, Image-to-Code (UI mockup → HTML)'),
        ('📚 T3 — Arsip',
         'Semantic search vault Obsidian (LanceDB + sentence-transformers), simpan catatan otomatis'),
        ('📝 T4 — Admin',
         'Generate Excel/Word/PDF dengan 5 style preset, **auto-render chart** (bar/line/pie), '
         '**image search** Wikimedia + Serper untuk gambar jurnal/laporan, data analysis CSV→chart'),
        ('🔍 T5 — Intel',
         'Riset web (Scrapling stealth Camoufox), Serper Google Search, scrape Reddit/GitHub/X, '
         'OSINT domain (WHOIS/DNS/Geo), smart search dengan caching'),
        ('🌤️ T6 — Lifestyle',
         'YouTube search, cuaca real-time, schedule manager, maps distance (OSRM)'),
        ('🎨 T7 — Seniman',
         'Dashboard HTML interaktif (Chart.js), SVG generator, cutting list kayu, Mermaid diagram'),
        ('🔧 T8 — Mekanik',
         'Eksekusi Python sandbox aman, auto-debug retry hingga 5x, Git automation, security scanner'),
    ]
    for name, desc in teams:
        embed.add_field(name=name, value=desc, inline=False)
    embed.set_footer(text='B.I.M.A Core — Powered by CrewAI + LangGraph')
    return embed


@client.event
async def on_ready():
    global _startup_notified
    logger.info(f'✨ B.I.M.A Core FULL SYSTEM online sebagai {client.user}!')
    logger.info('8 Team + Memory + Real-time + File Reader siap tempur! 🚀')

    if _startup_notified:
        logger.info('Reconnect terdeteksi, skip startup notif duplikat')
        return
    _startup_notified = True

    try:
        start_saham_scheduler(client)
    except Exception as e:
        logger.error(f'Gagal start saham scheduler: {e}', exc_info=True)

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
        await channel.send(embed=_build_startup_embed())
        logger.info(f'✅ Startup notif terkirim ke channel {STATUS_CHANNEL_ID}')
    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
        logger.error(f'Channel notif tidak ditemukan / tidak ada izin: {e}')
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

    if not perintah:
        return

    # === !saham command pre-route ===
    if perintah.lower().startswith("!saham"):
        args = perintah[6:].strip()
        await handle_saham_command(message, args, bot_client=client)
        return

    # ============================================================
    # TANGKAP ATTACHMENT + AUTO-DOWNLOAD
    # ============================================================
    downloaded_files = []
    attachment_info = ""
    
    if message.attachments:
        # Discord max 25MB; reject lebih awal supaya gak buang bandwidth
        MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
        ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
                        ".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".md", ".json"}

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
        
        if not any(k in perintah.lower() for k in ['gambar', 'foto', 'pdf', 'lihat', 'analisis', 'baca', 'baca file']):
            perintah += " baca file"

    perintah_lengkap = perintah + attachment_info
    if downloaded_files:
        perintah_lengkap += f"\n\n[FILE_PATHS] File sudah didownload ke: {' | '.join(downloaded_files)}"

    konteks_waktu = f"""
=== KONTEKS WAKTU REAL-TIME ===
Sekarang: {waktu_sekarang}
Gunakan info waktu ini saat menjawab pertanyaan tentang hari ini, sekarang, atau waktu terkini.
Saat mencari data real-time, gunakan tahun/bulan yang sesuai.
================================"""

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

        chunks = smart_chunks(display_str)
        await pesan_tunggu.edit(content=chunks[0])
        for chunk in chunks[1:]:
            await message.reply(chunk)

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

def run_bot():
    # Start dashboard server di background thread (non-blocking)
    try:
        from core.dashboard_server import start_in_background
        dashboard_port = int(os.getenv('DASHBOARD_PORT', '8000'))
        start_in_background(host="0.0.0.0", port=dashboard_port)
    except Exception as e:
        logger.warning(f"Dashboard server gagal start (bot tetap jalan): {e}")

    if DISCORD_TOKEN:
        client.run(DISCORD_TOKEN)
    else:
        logger.critical("DISCORD_TOKEN tidak ditemukan di .env!")
