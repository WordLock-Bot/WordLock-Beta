#!/usr/bin/env bash
#
# WordLock – Startskript für den VPS/Home-Server.
#
# Startet die PostgreSQL-Datenbank, die API und den Bot als Docker-Container
# (alles AUSSER dem Dashboard, das auf Vercel läuft).
#
# Nutzung:
#   ./start.sh                 Build + Start aller Container
#   ./start.sh --no-build      Start ohne Rebuild (nur wenn Images existieren)
#   ./start.sh --tunnel        Start + Cloudflare-Tunnel für die API (Vercel!)
#   ./start.sh tunnel          Nur den Cloudflare-Tunnel starten
#   ./start.sh status          Zeigt Container-Status
#   ./start.sh logs [dienst]   Zeigt Logs (bot, api, db)
#   ./start.sh restart         Neustart
#   ./start.sh stop            Alle Container stoppen
#
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE="docker compose"
API_URL="http://127.0.0.1:8000/api/health"
TIMEOUT=90

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[ok]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
fail()  { echo -e "${RED}[fehler]${NC} $*"; }

check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        fail "Docker ist nicht installiert."
        echo "Installiere es mit:  sudo apt install docker.io docker-compose-v2"
        exit 1
    fi
    if ! docker info >/dev/null 2>&1; then
        fail "Docker-Daemon läuft nicht. Starte ihn mit:  sudo systemctl start docker"
        exit 1
    fi
}

check_env() {
    if [[ ! -f .env ]]; then
        fail ".env existiert nicht."
        echo "Erstelle sie:  cp .env.example .env"
        echo "Dann alle Werte in der .env ausfüllen (Token, Client-ID, Secret, JWT_SECRET)."
        exit 1
    fi
}

wait_for_api() {
    local elapsed=0
    echo -n "Warte auf API (http://127.0.0.1:8000) "
    until curl -sf --max-time 3 "$API_URL" >/dev/null 2>&1; do
        elapsed=$((elapsed + 2))
        if [[ $elapsed -ge $TIMEOUT ]]; then
            echo
            fail "API wurde nicht rechtzeitig erreichbar."
            echo "Bot-Log prüfen (oft fehlt ein gültiger DISCORD_TOKEN):"
            docker compose logs bot | tail -n 20 || true
            echo "API-Log:"
            docker compose logs api | tail -n 20 || true
            exit 1
        fi
        echo -n "."
        sleep 2
    done
    echo
    info "API ist online."
}

# --- Cloudflare Tunnel --------------------------------------------------
# Exponiert die lokale API (Port 8000) öffentlich, damit das auf Vercel
# gehostete Dashboard sie erreichen kann. Kein Root nötig (Einzel-Binary).
#
# ACHTUNG: Ein "quick tunnel" (ohne eigene Domain) bekommt eine zufällige
# URL (https://*.trycloudflare.com), die sich bei jedem Neustart ändert.
# Nach jedem Neustart muss NEXT_PUBLIC_API_URL in Vercel neu gesetzt und
# das Dashboard neu gebaut werden (siehe scripts/update-vercel-api-url.sh).
CF_BIN="$(command -v cloudflared || true)"

check_cloudflared() {
    if [[ -z "$CF_BIN" ]]; then
        warn "cloudflared ist nicht installiert."
        echo "Installiere es mit:  bash scripts/install-cloudflared.sh"
        exit 1
    fi
}

start_tunnel() {
    check_cloudflared
    info "Starte Cloudflare-Tunnel für die API (http://127.0.0.1:8000)..."
    local logf
    logf="$(mktemp)"
    "$CF_BIN" tunnel --url http://127.0.0.1:8000 --no-autoupdate >"$logf" 2>&1 &
    local pid=$!
    local url=""
    for _ in $(seq 1 30); do
        url="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$logf" | head -1 || true)"
        [[ -n "$url" ]] && break
        sleep 1
    done
    if [[ -n "$url" ]]; then
        echo "$url" > .tunnel-url
        info "API öffentlich erreichbar unter: $url"
        warn "Diese URL in Vercel als NEXT_PUBLIC_API_URL setzen:"
        warn "  bash scripts/update-vercel-api-url.sh"
    else
        warn "Konnte die Tunnel-URL nicht ermitteln. Log: $logf"
    fi
    echo
    echo "Tunnel läuft (PID $pid). Strg+C beendet ihn."
    tail -f "$logf" &
    local tailpid=$!
    trap 'kill "$pid" "$tailpid" 2>/dev/null || true' INT TERM
    wait "$pid"
}

case "${1:-start}" in
    start)
        check_docker
        check_env
        warn "Starte Bot, API und Datenbank (Dashboard läuft auf Vercel)."
        $COMPOSE up -d --build
        wait_for_api
        info "Fertig. Status:"
        $COMPOSE ps
        echo
        info "API-Test:  curl ${API_URL}"
        info "Logs:      ./start.sh logs bot"
        echo
        warn "Für das Vercel-Dashboard die API öffentlich machen:  ./start.sh tunnel"
        ;;
    --tunnel)
        check_docker
        check_env
        warn "Starte Bot, API und Datenbank (Dashboard läuft auf Vercel)."
        $COMPOSE up -d --build
        wait_for_api
        $COMPOSE ps
        echo
        start_tunnel
        ;;
    tunnel)
        check_docker
        check_env
        start_tunnel
        ;;
    --no-build)
        check_docker
        check_env
        $COMPOSE up -d
        wait_for_api
        $COMPOSE ps
        ;;
    status)
        check_docker
        $COMPOSE ps
        ;;
    logs)
        check_docker
        shift || true
        $COMPOSE logs -f --tail=100 "${1:-bot}"
        ;;
    restart)
        check_docker
        check_env
        $COMPOSE restart
        info "Container neu gestartet."
        ;;
    stop)
        check_docker
        $COMPOSE stop
        info "Container gestoppt."
        ;;
    *)
        echo "Unbekannter Befehl: $1"
        sed -n '2,12p' "$0"
        exit 1
        ;;
esac
