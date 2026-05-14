#!/bin/bash
# =============================================
# BIMA CORE — VPS Deployment Script
# Jalankan script ini di VPS baru setelah
# upload project ke ~/BIMA_CORE
# =============================================

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════╗"
echo "║   B.I.M.A CORE — VPS DEPLOYMENT SETUP   ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

PROJECT_DIR="$HOME/BIMA_CORE"
VENV_DIR="$PROJECT_DIR/bima_env"

# ─────────────────────────────────────────────
# 1. System dependencies
# ─────────────────────────────────────────────
echo -e "${CYAN}[1/8] 📦 Installing system dependencies...${NC}"
sudo apt update -qq
sudo apt install -y -qq python3.11 python3.11-venv python3-pip \
    build-essential libffi-dev libssl-dev curl wget git \
    chromium-browser > /dev/null 2>&1
echo -e "${GREEN}[✓] System dependencies installed${NC}"

# ─────────────────────────────────────────────
# 2. Python virtual environment
# ─────────────────────────────────────────────
echo -e "${CYAN}[2/8] 🐍 Setting up Python environment...${NC}"
cd "$PROJECT_DIR"

if [ ! -d "$VENV_DIR" ]; then
    python3.11 -m venv "$VENV_DIR"
    echo -e "${GREEN}[✓] Virtual environment created${NC}"
else
    echo -e "${YELLOW}[!] Virtual environment already exists, skipping${NC}"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}[✓] Python dependencies installed${NC}"

# ─────────────────────────────────────────────
# 3. Verify Python imports
# ─────────────────────────────────────────────
echo -e "${CYAN}[3/8] 🔍 Verifying Python imports...${NC}"
python3 -c "
import crewai
import fastapi
import discord
import langgraph
import sentence_transformers
print('[✓] All critical imports OK')
" || {
    echo -e "${RED}[ERROR] Some Python packages failed to import!${NC}"
    echo -e "${YELLOW}Try: pip install -r requirements.txt${NC}"
    exit 1
}
echo -e "${GREEN}[✓] All Python imports verified${NC}"

# ─────────────────────────────────────────────
# 4. Node.js & PM2
# ─────────────────────────────────────────────
echo -e "${CYAN}[4/8] ⚙️  Setting up Node.js & PM2...${NC}"
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash - > /dev/null 2>&1
    sudo apt install -y -qq nodejs
fi

if ! command -v pm2 &> /dev/null; then
    sudo npm install -g pm2 > /dev/null 2>&1
fi

# Install log rotation
pm2 install pm2-logrotate > /dev/null 2>&1 || true
pm2 set pm2-logrotate:max_size 50M > /dev/null 2>&1 || true
pm2 set pm2-logrotate:retain 7 > /dev/null 2>&1 || true
pm2 set pm2-logrotate:compress true > /dev/null 2>&1 || true

echo -e "${GREEN}[✓] Node.js $(node -v) & PM2 $(pm2 -v) ready${NC}"

# ─────────────────────────────────────────────
# 5. Cloudflared
# ─────────────────────────────────────────────
echo -e "${CYAN}[5/8] 🌐 Setting up Cloudflare Tunnel...${NC}"
if ! command -v cloudflared &> /dev/null; then
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        DEB_ARCH="amd64"
    elif [ "$ARCH" = "aarch64" ]; then
        DEB_ARCH="arm64"
    else
        echo -e "${RED}[ERROR] Unsupported architecture: $ARCH${NC}"
        exit 1
    fi
    wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${DEB_ARCH}.deb" -O /tmp/cloudflared.deb
    sudo dpkg -i /tmp/cloudflared.deb > /dev/null 2>&1
    rm -f /tmp/cloudflared.deb
fi
echo -e "${GREEN}[✓] cloudflared $(cloudflared version 2>&1 | head -1) ready${NC}"

# ─────────────────────────────────────────────
# 6. Swap file (kalau RAM < 6GB)
# ─────────────────────────────────────────────
echo -e "${CYAN}[6/8] 💾 Checking swap...${NC}"
TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
SWAP_SIZE=$(free -m | awk '/^Swap:/{print $2}')

if [ "$TOTAL_RAM_MB" -lt 6144 ] && [ "$SWAP_SIZE" -lt 2048 ]; then
    echo -e "${YELLOW}[!] RAM ${TOTAL_RAM_MB}MB detected, creating 4GB swap...${NC}"
    if [ ! -f /swapfile ]; then
        sudo fallocate -l 4G /swapfile
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile > /dev/null 2>&1
        sudo swapon /swapfile
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
        sudo sysctl vm.swappiness=10 > /dev/null 2>&1
        echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf > /dev/null
        echo -e "${GREEN}[✓] 4GB swap created${NC}"
    else
        echo -e "${YELLOW}[!] Swap file already exists${NC}"
    fi
else
    echo -e "${GREEN}[✓] Sufficient RAM (${TOTAL_RAM_MB}MB) / swap (${SWAP_SIZE}MB)${NC}"
fi

# ─────────────────────────────────────────────
# 7. Firewall
# ─────────────────────────────────────────────
echo -e "${CYAN}[7/8] 🔒 Configuring firewall...${NC}"
sudo ufw allow 22/tcp > /dev/null 2>&1
sudo ufw allow 8000/tcp > /dev/null 2>&1
echo "y" | sudo ufw enable > /dev/null 2>&1 || true
echo -e "${GREEN}[✓] UFW firewall configured (SSH + port 8000)${NC}"

# ─────────────────────────────────────────────
# 8. Create directories & validate .env
# ─────────────────────────────────────────────
echo -e "${CYAN}[8/8] 📁 Final setup...${NC}"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/outputs"
mkdir -p "$PROJECT_DIR/Bima_Vault"
mkdir -p "$HOME/backups"

# Check .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}[ERROR] .env file not found!${NC}"
    echo -e "${YELLOW}Create it: cp .env.example .env && nano .env${NC}"
    exit 1
fi

# Validate critical env vars
source <(grep -v '^#' "$PROJECT_DIR/.env" | sed 's/\r$//' | xargs -d '\n' printf 'export %s\n')
MISSING=""
[ -z "$OPENROUTER_API_KEY" ] && MISSING="$MISSING OPENROUTER_API_KEY"
[ -z "$DISCORD_TOKEN" ] && MISSING="$MISSING DISCORD_TOKEN"

if [ -n "$MISSING" ]; then
    echo -e "${RED}[WARNING] Missing env vars:${MISSING}${NC}"
    echo -e "${YELLOW}Edit .env: nano $PROJECT_DIR/.env${NC}"
else
    echo -e "${GREEN}[✓] Critical env vars present${NC}"
fi

# Check OBSIDIAN_PATH
if grep -q "/mnt/c/" "$PROJECT_DIR/.env"; then
    echo -e "${YELLOW}[!] OBSIDIAN_PATH masih mengarah ke Windows path!${NC}"
    echo -e "${YELLOW}    Ubah ke: OBSIDIAN_PATH=$PROJECT_DIR/Bima_Vault${NC}"
fi

# ─────────────────────────────────────────────
# Done!
# ─────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗"
echo -e "║  🎉 BIMA CORE VPS SETUP COMPLETE!                    ║"
echo -e "║                                                      ║"
echo -e "║  Next steps:                                         ║"
echo -e "║  1. Review .env:     nano $PROJECT_DIR/.env          ║"
echo -e "║  2. Fix OBSIDIAN_PATH (remove /mnt/c/ Windows path) ║"
echo -e "║  3. Start services:  pm2 start ecosystem.config.js   ║"
echo -e "║  4. Auto startup:    pm2 startup && pm2 save         ║"
echo -e "║  5. Monitor:         pm2 monit                       ║"
echo -e "║                                                      ║"
echo -e "║  Dashboard: http://localhost:8000/dashboard           ║"
echo -e "║  Tunnel URL will appear in: pm2 logs bima-tunnel     ║"
echo -e "╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
