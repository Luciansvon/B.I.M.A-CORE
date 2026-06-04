#!/usr/bin/env bash
# Wrapper: cd ke project root dulu sebelum jalanin MCP server.
# Diperlukan karena `python -m mcp_server.server` butuh cwd = BIMA_CORE biar
# module discovery jalan, padahal Claude Code spawn-nya bisa dari mana aja.
set -euo pipefail
cd /home/bima_lucian/BIMA_CORE
exec /home/bima_lucian/BIMA_CORE/bima_env/bin/python -m mcp_server.server
