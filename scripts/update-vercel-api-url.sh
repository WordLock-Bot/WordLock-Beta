#!/usr/bin/env bash
#
# Setzt die aktuelle Tunnel-URL (aus .tunnel-url) in Vercel als
# NEXT_PUBLIC_API_URL (production) und deployed das Dashboard neu.
#
# Nutzung:
#   bash scripts/update-vercel-api-url.sh
#
# Voraussetzungen:
#   - npx verfügbar (Node.js), vorher:  npx vercel login
#   - .tunnel-url existiert (wird von ./start.sh tunnel geschrieben)
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .tunnel-url ]]; then
    echo "[fehler] .tunnel-url existiert nicht."
    echo "Starte zuerst:  ./start.sh tunnel"
    exit 1
fi

URL="$(cat .tunnel-url)"
echo "[ok] Tunnel-URL: $URL"

if ! command -v vercel >/dev/null 2>&1 && ! npx --no-install vercel --version >/dev/null 2>&1; then
    echo "[!] Vercel CLI wird einmalig geholt (npx vercel)..."
    npx vercel login
fi

V="vercel"
command -v vercel >/dev/null 2>&1 || V="npx vercel"

echo "[!] Setze NEXT_PUBLIC_API_URL in Vercel (production)..."
"$V" env rm NEXT_PUBLIC_API_URL production 2>/dev/null || true
echo "$URL" | "$V" env add NEXT_PUBLIC_API_URL production

echo "[!] Deploye Dashboard auf Vercel (production)..."
"$V" deploy --prod --cwd dashboard --yes

echo
echo "[ok] Fertig! Dashboard: $("$V" ls --cwd dashboard 2>/dev/null | head -1 || true)"
echo "     Deploy-Log: https://vercel.com/dashboard"
