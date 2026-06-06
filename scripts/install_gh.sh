#!/usr/bin/env bash
# Install GitHub CLI (gh) ke ~/.local/bin tanpa sudo.
set -euo pipefail

mkdir -p ~/.local/bin
cd /tmp

VER=$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest | grep '"tag_name"' | head -1 | cut -d'"' -f4)
echo "Latest gh release: $VER"

TAR="gh_${VER#v}_linux_amd64.tar.gz"
URL="https://github.com/cli/cli/releases/download/${VER}/${TAR}"
echo "Downloading: $URL"

curl -fsSL -o gh.tgz "$URL"
tar xzf gh.tgz
cp gh_*/bin/gh ~/.local/bin/gh
chmod +x ~/.local/bin/gh

# Cleanup
rm -rf gh.tgz gh_*

echo ""
echo "Installed to: $HOME/.local/bin/gh"
~/.local/bin/gh --version | head -2

# Ensure ~/.local/bin di PATH .bashrc kalau belum
if ! grep -q '\.local/bin' ~/.bashrc 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo "PATH updated di ~/.bashrc — buka shell baru atau 'source ~/.bashrc'"
fi
