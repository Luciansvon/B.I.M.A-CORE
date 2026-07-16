"""Discord !arsip command router.

Subcommands:
    !arsip help                              — list commands
    !arsip hubungkan                         — connect wiki links and clean formatting
    !arsip index                             — rebuild vector store index
"""
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger('bima_core')

HELP_TEXT = """📚 **`!arsip` — Perintah Vault & Catatan**
```
!arsip help       → tampilkan bantuan ini
!arsip hubungkan  → sambungkan [[WikiLink]] semantik & rapikan catatan
!arsip index      → indeks ulang semua catatan di vault ke database vector
```
"""


async def handle_arsip_command(message, args: str, bot_client=None) -> bool:
    """Process !arsip command. Return True if handled."""
    args = args.strip()
    if not args or args.lower() in {"help", "?", "-h", "--help"}:
        await message.reply(HELP_TEXT)
        return True

    parts = args.split()
    sub = parts[0].lower()

    try:
        if sub in {"hubungkan", "rapih", "rapihkan", "link"}:
            await message.reply("⏳ *Anisa sedang memproses vault Obsidian (sambung link semantik & rapikan format)...*")
            from teams.t3_arsip import VaultLinkerTool
            result = await asyncio.to_thread(VaultLinkerTool()._run)
            await message.reply(result)
            return True

        if sub in {"index", "reindex"}:
            await message.reply("⏳ *Anisa sedang mengindeks ulang vault ke database vector...*")
            from teams.t3_arsip import index_vault
            await asyncio.to_thread(index_vault)
            await message.reply("✅ Vault berhasil diindeks ulang!")
            return True

        await message.reply(f"❌ Subcommand `{sub}` tidak dikenal. Ketik `!arsip help` untuk bantuan.")
        return True

    except Exception as e:
        logger.error(f"[ARSIP CMD] Error '{args}': {e}", exc_info=True)
        try:
            from core.public_errors import public_message
            await message.reply(public_message("Gagal menjalankan perintah arsip"))
        except Exception:
            pass
        return True
