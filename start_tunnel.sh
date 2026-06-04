#!/bin/bash
# =============================================
# BIMA CORE — Public Tunnel Script
# Expose dashboard ke internet via Cloudflare
# =============================================

set -e

PORT=${DASHBOARD_PORT:-8000}
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════╗"
echo "║   B.I.M.A CORE — PUBLIC TUNNEL SETUP    ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# 1. Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo -e "${YELLOW}[!] cloudflared belum terinstall. Installing...${NC}"
    
    # Detect architecture
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        DEB_ARCH="amd64"
    elif [ "$ARCH" = "aarch64" ]; then
        DEB_ARCH="arm64"
    else
        echo -e "${RED}[ERROR] Arsitektur tidak didukung: $ARCH${NC}"
        exit 1
    fi
    
    # Download dan install cloudflared
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${DEB_ARCH}.deb"
    echo -e "${CYAN}[*] Downloading cloudflared dari $CLOUDFLARED_URL ...${NC}"
    
    wget -q "$CLOUDFLARED_URL" -O /tmp/cloudflared.deb
    sudo dpkg -i /tmp/cloudflared.deb
    rm -f /tmp/cloudflared.deb
    
    echo -e "${GREEN}[✓] cloudflared terinstall!${NC}"
fi

# 2. Check if BIMA server is running
echo -e "${CYAN}[*] Mengecek apakah BIMA server jalan di port $PORT ...${NC}"
if ! curl -s "http://localhost:$PORT" > /dev/null 2>&1; then
    echo -e "${YELLOW}[!] Server belum jalan di port $PORT.${NC}"
    echo -e "${YELLOW}    Jalankan dulu: pm2 start ecosystem.config.js${NC}"
    echo -e "${YELLOW}    Atau: python3 main.py${NC}"
    echo ""
    echo -e "${YELLOW}    Tetap lanjut membuka tunnel? (y/n)${NC}"
    read -r answer
    if [ "$answer" != "y" ]; then
        exit 1
    fi
fi

# 3. Start Cloudflare Quick Tunnel (no account needed!)
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗"
echo -e "║   🌐 STARTING CLOUDFLARE TUNNEL...       ║"
echo -e "╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}[*] Mode: Quick Tunnel (gratis, tanpa akun)${NC}"
echo -e "${CYAN}[*] Target: http://localhost:$PORT${NC}"
echo -e "${YELLOW}[!] URL publik akan muncul di bawah ini ↓${NC}"
echo -e "${YELLOW}[!] Bagikan URL tersebut ke device manapun!${NC}"
echo ""

# Run cloudflared with quick tunnel
cloudflared tunnel --url "http://localhost:$PORT" 2>&1 | while IFS= read -r line; do
    # Highlight the public URL when it appears
    if echo "$line" | grep -q "https://.*trycloudflare.com"; then
        URL=$(echo "$line" | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com')
        if [ -n "$URL" ]; then
            echo ""
            echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗"
            echo -e "║  🎉 DASHBOARD BIMA ONLINE!                                  ║"
            echo -e "║                                                              ║"
            echo -e "║  🌍 PUBLIC URL:                                              ║"
            echo -e "║  ${YELLOW}$URL${GREEN}"
            echo -e "║                                                              ║"
            echo -e "║  📱 Dashboard: ${YELLOW}${URL}/dashboard${GREEN}"
            echo -e "║                                                              ║"
            echo -e "║  Bisa diakses dari HP, tablet, laptop manapun!               ║"
            echo -e "║  Tekan Ctrl+C untuk stop tunnel.                             ║"
            echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
            echo ""
        fi
    fi
    echo "$line"
done
