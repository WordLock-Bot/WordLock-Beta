#!/usr/bin/env bash
#
# Erstes Deployment des Dashboards auf Vercel via CLI (ohne Git-Repo).
#
# Nutzung:
#   bash scripts/deploy-vercel.sh
#
# Ablauf:
#   1. npx vercel login   (einmalig, öffnet Browser)
#   2. Projekt linken/erstellen (Root-Verzeichnis: dashboard/)
#   3. NEXT_PUBLIC_API_URL setzen (Tunnel-URL aus .tunnel-url oder manuell)
#   4. Deployment: vercel deploy --prod
#
set -euo pipefail

cd "$(dirname "$0")/.."

v() { # wrapper: "vercel" oder "npx vercel"
    if command -v vercel >/dev/null 2>&1; then
        vercel "$@"
    else
        npx --yes vercel "$@"
    fi
}

if ! v whoami >/dev/null 2>&1; then
    echo "[!] Bitte bei Vercel anmelden (Browser öffnet sich)..."
    v login
fi

if [[ ! -f .tunnel-url ]]; then
    echo "[!] .tunnel-url fehlt — ohne Tunnel kann das Dashboard die API nicht erreichen."
    echo "    Starte zuerst:  ./start.sh tunnel"
    echo "    (oder trage deine API-URL weiter unten manuell ein.)"
fi

URL="${1:-}"
if [[ -z "$URL" && -f .tunnel-url ]]; then
    URL="$(cat .tunnel-url)"
fi
if [[ -z "$URL" ]]; then
    read -r -p "NEXT_PUBLIC_API_URL (öffentliche API-URL, z.B. https://xxx.trycloudflare.com): " URL
fi

echo "[!] Verlinke Vercel-Projekt (nur falls nicht schon verlinkt) ..."
if [[ ! -f dashboard/.vercel/project.json ]]; then
    v link --cwd dashboard --yes
else
    PROJ="$(sed -n 's/.*"projectName":"\([^"]*\)".*/\1/p' dashboard/.vercel/project.json)"
    echo "    (bestehende Verlinkung genutzt: $PROJ)"
fi

echo "[!] Setze NEXT_PUBLIC_API_URL=$URL (production) ..."
(
    cd dashboard
    v env rm NEXT_PUBLIC_API_URL production --yes 2>/dev/null || true
    echo "$URL" | v env add NEXT_PUBLIC_API_URL production
)

echo "[!] Deploye ..."
v deploy --cwd dashboard --prod --yes

echo
echo "[ok] Deployment abgeschlossen. Deine URL: https://<projekt>.vercel.app"
echo "     Diese URL danach in der Server-.env eintragen:"
echo "       DISCORD_REDIRECT_URI=https://<projekt>.vercel.app/api/auth/callback"
echo "       DASHBOARD_URL=https://<projekt>.vercel.app"
echo "       COOKIE_SECURE=true"
echo "       CORS_ORIGINS=https://<projekt>.vercel.app"
echo "     Und den API-Container neu starten:  ./start.sh restart"
