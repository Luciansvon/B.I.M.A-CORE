#!/usr/bin/env bash
# B.I.M.A Core — MCP manifest installer
#
# Register MCP server BIMA_CORE ke Claude Code dan/atau Claude Desktop.
# Idempotent: aman dijalanin berulang kali.
#
# Usage:
#   ./scripts/install_mcp_manifest.sh                # interaktif, tanya per target
#   ./scripts/install_mcp_manifest.sh --code         # cuma Claude Code
#   ./scripts/install_mcp_manifest.sh --desktop      # cuma Claude Desktop
#   ./scripts/install_mcp_manifest.sh --all          # dua-duanya, no prompt
#   ./scripts/install_mcp_manifest.sh --dry-run      # print command/JSON doang

set -euo pipefail

SERVER_NAME="bima_core"
PROJECT_ROOT="/home/bima_lucian/BIMA_CORE"
PYTHON_BIN="${PROJECT_ROOT}/bima_env/bin/python"
MODULE="mcp_server.server"
WRAPPER="${PROJECT_ROOT}/mcp_server/run.sh"

# Detect platform — WSL path ke Claude Desktop config Windows
WIN_USER="${WIN_USER:-shint}"
DESKTOP_CONFIG="/mnt/c/Users/${WIN_USER}/AppData/Roaming/Claude/claude_desktop_config.json"

MODE="${1:-interactive}"

color() {
    case "$1" in
        green) printf "\033[0;32m%s\033[0m\n" "$2" ;;
        yellow) printf "\033[1;33m%s\033[0m\n" "$2" ;;
        red) printf "\033[0;31m%s\033[0m\n" "$2" ;;
        cyan) printf "\033[0;36m%s\033[0m\n" "$2" ;;
        *) echo "$2" ;;
    esac
}

# ---- Sanity checks ----
[ -x "${PYTHON_BIN}" ] || { color red "ERR: Python venv gak ada di ${PYTHON_BIN}"; exit 1; }
[ -f "${PROJECT_ROOT}/mcp_server/server.py" ] || { color red "ERR: mcp_server/server.py gak ada"; exit 1; }
[ -x "${WRAPPER}" ] || { color red "ERR: wrapper ${WRAPPER} gak executable. Jalanin: chmod +x ${WRAPPER}"; exit 1; }

color cyan "=== B.I.M.A Core MCP Installer ==="
echo "Server name: ${SERVER_NAME}"
echo "Python:      ${PYTHON_BIN}"
echo "Module:      ${MODULE}"
echo ""

# ---- Claude Code (via CLI) ----
install_claude_code() {
    if ! command -v claude >/dev/null 2>&1; then
        color yellow "SKIP Claude Code: \`claude\` CLI tidak ditemukan di PATH."
        echo "  → Install: https://docs.claude.com/claude-code"
        return
    fi

    color cyan "[Claude Code]"
    local cmd="claude mcp add -s user ${SERVER_NAME} \"${WRAPPER}\""
    echo "  Command: ${cmd}"

    if [ "${MODE}" = "--dry-run" ]; then
        return
    fi

    # Remove existing entry kalau ada (idempotent)
    claude mcp remove "${SERVER_NAME}" >/dev/null 2>&1 || true
    eval "${cmd}"
    color green "  OK: registered ke Claude Code."
    echo "  Cek: claude mcp list"
}

# ---- Claude Desktop (edit JSON via Python untuk safety) ----
install_claude_desktop() {
    if [ ! -d "$(dirname "${DESKTOP_CONFIG}")" ]; then
        color yellow "SKIP Claude Desktop: folder config gak ada di ${DESKTOP_CONFIG}."
        echo "  → Install Claude Desktop dulu di Windows."
        return
    fi

    color cyan "[Claude Desktop]"
    echo "  Config: ${DESKTOP_CONFIG}"

    if [ "${MODE}" = "--dry-run" ]; then
        cat <<JSON
  Akan inject snippet:
  {
    "mcpServers": {
      "${SERVER_NAME}": {
        "command": "wsl.exe",
        "args": ["-d", "Ubuntu", "--", "${WRAPPER}"]
      }
    }
  }
JSON
        return
    fi

    # Backup
    if [ -f "${DESKTOP_CONFIG}" ]; then
        cp "${DESKTOP_CONFIG}" "${DESKTOP_CONFIG}.bak.$(date +%s)"
        color yellow "  Backup: ${DESKTOP_CONFIG}.bak.*"
    fi

    # Patch via Python (json module — safe dari shell quoting)
    "${PYTHON_BIN}" - <<PYEOF
import json, os
path = r"${DESKTOP_CONFIG}"
config = {}
if os.path.exists(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                config = json.loads(content)
    except Exception as e:
        print(f"WARN: parse existing config gagal ({e}), pakai default kosong")
        config = {}

config.setdefault("mcpServers", {})
config["mcpServers"]["${SERVER_NAME}"] = {
    "command": "wsl.exe",
    "args": ["-d", "Ubuntu", "--", "${WRAPPER}"],
}

os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)
print(f"OK: patched {path}")
PYEOF

    color green "  OK: registered ke Claude Desktop."
    echo "  Restart Claude Desktop biar config ter-load."
}

# ---- Mode dispatch ----
case "${MODE}" in
    --code)
        install_claude_code
        ;;
    --desktop)
        install_claude_desktop
        ;;
    --all)
        install_claude_code
        install_claude_desktop
        ;;
    --dry-run)
        install_claude_code
        install_claude_desktop
        ;;
    interactive)
        echo "Pilih target (default: keduanya):"
        echo "  [1] Claude Code only"
        echo "  [2] Claude Desktop only"
        echo "  [3] Keduanya"
        echo "  [4] Dry-run (print doang, gak install)"
        read -rp "Pilih [3]: " choice
        case "${choice:-3}" in
            1) install_claude_code ;;
            2) install_claude_desktop ;;
            3) install_claude_code; install_claude_desktop ;;
            4) MODE=--dry-run; install_claude_code; install_claude_desktop ;;
            *) color red "Pilihan invalid."; exit 1 ;;
        esac
        ;;
    *)
        color red "Unknown mode: ${MODE}"
        sed -n '4,15p' "$0"
        exit 1
        ;;
esac

echo ""
color green "Done. Quick test:"
echo "  Claude Code:    claude mcp list"
echo "  Manual run:     ${PYTHON_BIN} -m ${MODULE}"
