"""Discord !arsip command router.

Subcommands:
    !arsip help                              — list commands
    !arsip hubungkan                         — connect wiki links and clean formatting
    !arsip index                             — incremental vector index sync
    !arsip reindex --full                    — full vector index rebuild
"""

import asyncio
import logging

logger = logging.getLogger("bima_core")

HELP_TEXT = """📚 **`!arsip` — Perintah Vault & Catatan**
```
!arsip help            → tampilkan bantuan ini
!arsip hubungkan       → sambungkan [[WikiLink]] semantik & rapikan catatan
!arsip index           → sinkronkan file baru/berubah (incremental)
!arsip reindex --full  → rebuild seluruh database vector
```
"""


def _format_result(result: str) -> str:
    status, separator, detail = result.partition("|")
    if not separator:
        return result
    icon = {
        "SUCCESS": "✅",
        "SKIPPED": "ℹ️",
        "PARTIAL": "⚠️",
        "FAILED": "❌",
    }.get(status, "ℹ️")
    return f"{icon} {detail}"


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
            await message.reply(
                "⏳ *Anisa sedang memproses vault Obsidian "
                "(sambung link semantik & rapikan format)...*"
            )
            from teams.t3_arsip import VaultLinkerTool

            result = await asyncio.to_thread(VaultLinkerTool()._run)
            await message.reply(result)
            return True

        if sub in {"index", "reindex"}:
            full_rebuild = sub == "reindex" and "--full" in {
                part.lower() for part in parts[1:]
            }
            mode = "full rebuild" if full_rebuild else "sinkronisasi incremental"
            await message.reply(
                f"⏳ *Anisa sedang menjalankan {mode} vault ke database vector...*"
            )
            from teams.t3_arsip import index_vault

            result = await asyncio.to_thread(
                index_vault,
                full_rebuild=full_rebuild,
            )
            await message.reply(_format_result(result))
            return True

        await message.reply(
            f"❌ Subcommand `{sub}` tidak dikenal. "
            "Ketik `!arsip help` untuk bantuan."
        )
        return True

    except Exception as e:
        logger.error(f"[ARSIP CMD] Error '{args}': {e}", exc_info=True)
        try:
            from core.public_errors import public_message
            await message.reply(public_message("Gagal menjalankan perintah arsip"))
        except Exception:
            pass
        return True
