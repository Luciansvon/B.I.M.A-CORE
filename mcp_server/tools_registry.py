"""Central registry: wrap BIMA_CORE tool existing → callable async untuk MCP server.

Tiap fungsi di sini SATU PERMUKAAN BERSIH per tool. Server (`server.py`) hanya
register tipis tanpa logic. Kalau implementasi internal berubah (mis. PDFGeneratorTool
ganti signature), update di sini, server tetap.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Pastikan project root ke-import-able saat dijalanin sebagai `python -m mcp_server.server`
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger("bima_mcp")


async def vault_search(query: str, top_k: int = 3) -> str:
    """Search Obsidian vault via Arsip tool.

    Wrap `teams.t3_arsip.search_vault` (sync) di executor biar gak block event loop.
    """
    if not query or not query.strip():
        return "ERROR: query kosong"

    try:
        from teams.t3_arsip import search_vault as _search
    except Exception as e:
        return f"ERROR: gak bisa import search_vault: {e}"

    try:
        result = await asyncio.to_thread(_search, query, max(1, min(20, top_k)))
        return result or "(tidak ada hasil)"
    except Exception as e:
        logger.exception("vault_search error")
        return f"ERROR: {e}"


async def memory_query(query: str, limit: int = 5) -> str:
    """Query semantic memory Anisa (agentmemory server di port 3111).

    `core.agentmemory_client.recall` sudah async — langsung await.
    Return empty string kalau server mati / gak ada hasil (safe-default existing).
    """
    if not query or not query.strip():
        return "ERROR: query kosong"

    try:
        from core.agentmemory_client import recall
    except Exception as e:
        return f"ERROR: gak bisa import agentmemory_client: {e}"

    try:
        result = await recall(query, max(1, min(50, limit)))
        return result or "(tidak ada hasil — agentmemory mungkin down atau kosong)"
    except Exception as e:
        logger.exception("memory_query error")
        return f"ERROR: {e}"


async def generate_pdf(input_json: str) -> str:
    """Generate PDF via PDFGeneratorTool dari teams/t4_admin.py.

    Input JSON sesuai schema PDFGeneratorTool existing (lihat description tool-nya
    di t4_admin.py:890). Sync method di-jalanin via executor.

    Return: "SUCCESS|<path>|<keterangan>" atau "FAILED|<error>".
    """
    if not input_json or not input_json.strip():
        return "FAILED|input_json kosong"

    try:
        from teams.t4_admin import PDFGeneratorTool
    except Exception as e:
        return f"FAILED|gak bisa import PDFGeneratorTool: {e}"

    tool = PDFGeneratorTool()
    try:
        result = await asyncio.to_thread(tool._run, input_json)
        return result
    except Exception as e:
        logger.exception("generate_pdf error")
        return f"FAILED|{e}"
