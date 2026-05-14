"""B.I.M.A Core — MCP Server.

Expose tool internal BIMA_CORE (vault_search, memory_query, generate_pdf) ke
klien MCP (Claude Desktop, Claude Code, dll) via stdio transport.

Jalanin: `python -m mcp_server.server`
"""
import logging
import sys

from mcp.server.fastmcp import FastMCP

from mcp_server.tools_registry import (
    generate_pdf as _generate_pdf,
    memory_query as _memory_query,
    vault_search as _vault_search,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("bima_mcp.server")

mcp = FastMCP(
    name="bima_core",
    instructions=(
        "B.I.M.A Core — agentic system Anisa. Tool yang di-expose: "
        "vault_search (cari di Obsidian vault), memory_query (semantic memory Anisa), "
        "generate_pdf (bikin PDF lewat PDFGeneratorTool). Use case: integrate Anisa "
        "ke workflow Claude Code / Desktop."
    ),
)


@mcp.tool()
async def vault_search(query: str, top_k: int = 3) -> str:
    """Search Obsidian vault Bima — return chunk paling relevan.

    Args:
        query: kata kunci atau pertanyaan natural language.
        top_k: jumlah hasil (1-20, default 3).
    """
    logger.info(f"vault_search query={query!r} top_k={top_k}")
    return await _vault_search(query, top_k)


@mcp.tool()
async def memory_query(query: str, limit: int = 5) -> str:
    """Query semantic memory Anisa (agentmemory server di port 3111).

    Args:
        query: pertanyaan natural language soal hal yang pernah dibahas dengan Anisa.
        limit: jumlah hasil (1-50, default 5).
    """
    logger.info(f"memory_query query={query!r} limit={limit}")
    return await _memory_query(query, limit)


@mcp.tool()
async def generate_pdf(input_json: str) -> str:
    """Generate PDF via PDFGeneratorTool (cover, TOC, multi-section).

    Args:
        input_json: JSON string sesuai schema PDFGeneratorTool. Field utama:
            - title (str): judul dokumen
            - subtitle (str): subjudul opsional
            - author (str): nama penulis
            - sections (list): list section dengan heading, content, image_path, chart, table
            - style (str): "formal" | "casual" | "academic"

    Return: "SUCCESS|<absolute_path>|<keterangan>" atau "FAILED|<error>".
    """
    logger.info(f"generate_pdf input_json_len={len(input_json)}")
    return await _generate_pdf(input_json)


def main() -> None:
    logger.info("Starting B.I.M.A Core MCP server (stdio transport)")
    mcp.run()


if __name__ == "__main__":
    main()
