#!/usr/bin/env bash
#
# Installiert cloudflared (Cloudflare Tunnel) für den aktuellen User —
# OHNE Root-Rechte. Das Binary wird nach ~/.local/bin gelegt.
#
# Nutzung:  bash scripts/install-cloudflared.sh
set -euo pipefail

DEST="$HOME/.local/bin/cloudflared"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64) ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) echo "Nicht unterstützte Architektur: $ARCH"; exit 1 ;;
esac

mkdir -p "$HOME/.local/bin"

if [[ -x "$DEST" ]]; then
    echo "[ok] cloudflared ist bereits installiert: $DEST"
    "$DEST" --version
    exit 0
fi

echo "[!] Lade cloudflared herunter (linux-$ARCH)..."
URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$ARCH"
if command -v curl >/dev/null 2>&1; then
    curl -L --fail -o "$DEST" "$URL"
else
    wget -O "$DEST" "$URL"
fi
chmod +x "$DEST"

echo "[ok] Installiert: $DEST"
"$DEST" --version

if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo
    echo "[!] '$HOME/.local/bin' ist nicht im PATH."
    echo "    Füge es hinzu (in ~/.bashrc):"
    echo "      echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "      source ~/.bashrc"
fi
