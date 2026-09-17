# Home-Server Deployment

Dieses Dokument beschreibt, wie du WordLock auf deinem eigenen Server
(Homelab, VPS oder alter PC mit Linux) betreibst. Das **Dashboard läuft auf
Vercel**, auf deinem Server laufen **Bot, API und PostgreSQL**. Der Zugriff
von außen läuft über eine Domain mit HTTPS (nötig für den Discord-OAuth-Login).

## Architektur

```
┌──────────────────────────── Vercel (Cloud) ─────────────────────────────┐
│  Dashboard (Next.js)   ──────────HTTPS──────────┐                       │
└─────────────────────────────────────────────────┼───────────────────────┘
                                                   ▼
┌───────────────────────────── Home Server ─────────────────────────────┐
│  Caddy (HTTPS, automatisch) ──► API (Docker, Port 8000)                │
│        │                        PostgreSQL (Docker, nur intern)        │
│        │                        Bot (Docker, verbindet Discord Gateway)│
│        │                                                               │
│   Port 80/443  ◄──── Router-Portweiterung ◄──── Internet               │
└────────────────────────────────────────────────────────────────────────┘
```

Das Dashboard leitet alle `/api/*`-Aufrufe serverseitig an die API weiter
(`NEXT_PUBLIC_API_URL`). Der Discord-Login läuft deshalb über die
**Dashboard-URL** (`DISCORD_REDIRECT_URI`), damit der Session-Cookie auf dem
Dashboard-Host landet; die API selbst muss nicht direkt öffentlich sein.

## 1. Voraussetzungen

- Linux-Server (empfohlen: Ubuntu 22.04/24.04 LTS)
- Docker + Docker Compose
- Eine Domain, die auf deine öffentliche IP zeigt (z. B. `api.deinedomain.de`)
- Alternativ ohne Domain/Portfreigabe: Cloudflare Tunnel (Abschnitt 7)

### Docker installieren

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
# danach neu einloggen oder: newgrp docker
```

## 2. Projekt auf den Server kopieren

```bash
git clone <dein-repo-url> wordlock
cd wordlock
cp .env.example .env
```

**`.env` ausfüllen:**

| Variable | Wert |
| --- | --- |
| `DISCORD_TOKEN` | Bot-Token aus dem Discord Developer Portal |
| `DISCORD_CLIENT_ID` | Application-ID |
| `DISCORD_CLIENT_SECRET` | OAuth2-Secret |
| `ADMIN_WHITELIST_IDS` | deine Discord-ID (kommagetrennt) |
| `JWT_SECRET` | langes zufälliges Secret (`openssl rand -hex 32`) |
| `DISCORD_REDIRECT_URI` | deine **Vercel-Dashboard-URL** + `/api/auth/callback` (z. B. `https://wordlock.vercel.app/api/auth/callback`) |
| `DASHBOARD_URL` | deine Vercel-Dashboard-URL (z. B. `https://wordlock.vercel.app`) |
| `CORS_ORIGINS` | deine Vercel-Dashboard-URL (damit nur dein Dashboard die API nutzt) |
| `COOKIE_SECURE` | `true` |
| `DATA_DIR` | `/app/data` |

Die `NEXT_PUBLIC_*`-Variablen gehören **nicht** in die Server-`.env`, sondern
werden beim Vercel-Deploy gesetzt (siehe Abschnitt 5).

Hinweis: Die Redirect-URI musst du **auch im Discord Developer Portal**
unter OAuth2 → Redirects eintragen, sonst schlägt der Login fehl.

## 3. Discord Developer Portal vorbereiten

- Application anlegen, Name/Beschreibung/Icon hinterlegen.
- OAuth2 → Redirects: `https://api.deinedomain.de/api/auth/callback`
- Scopes: `identify`, `guilds`, `bot`, `applications.commands`
- Bot → Intents aktivieren: `Message Content`, `Server Members`
  (siehe `docs/VERIFICATION.md` für Details)

## 4. Backend starten (Bot + API + Datenbank)

```bash
docker compose up -d --build
```

Status prüfen:

```bash
docker compose ps
docker compose logs -f api bot
```

Die API ist lokal auf Port 8000 erreichbar. Teste:

```bash
curl http://localhost:8000/api/health
```

## 5. Dashboard auf Vercel deployen

Das Dashboard wird nicht auf dem Server betrieben, sondern als statische
Next.js-App auf Vercel veröffentlicht:

```bash
cd dashboard
npm install
vercel            # beim ersten Mal: vercel login
vercel --prod
```

Alternativ verbindest du das Repo in der Vercel-Web-UI (Import → dein
Git-Repo, Root-Verzeichnis: `dashboard`).

**Umgebungsvariablen in Vercel setzen**
(Projekt → Settings → Environment Variables):

| Variable | Wert |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `https://api.deinedomain.de` |
| `NEXT_PUBLIC_INVITE_URL` | Invite-URL mit deiner Client-ID |

Hinweis: Der in `next.config.mjs` konfigurierte `rewrites`-Proxy leitet
`/api/*` an `NEXT_PUBLIC_API_URL` weiter, damit die OAuth-Cookies
same-origin funktionieren.

## 6. HTTPS mit Caddy (Reverse Proxy)

Caddy ist der einfachste Weg zu HTTPS — er holt und erneuert Zertifikate
automatisch.

```bash
sudo apt install -y caddy
sudo nano /etc/caddy/Caddyfile
```

```caddyfile
api.deinedomain.de {
    reverse_proxy 127.0.0.1:8000
}
```

```bash
sudo systemctl restart caddy
```

Das Dashboard braucht keinen Reverse Proxy — es läuft ja auf Vercel.
Danach **Router-Portweiterung** einrichten: TCP 80 und 443 von deiner
öffentlichen IP auf die lokale IP des Servers. Der DNS-Eintrag
(`api.deinedomain.de`) muss auf diese IP zeigen (z. B. A-Record, bei
dynamischer IP ein DDNS-Dienst wie DuckDNS).

## 7. Keine eigene Domain? (kostenlose Optionen)

### Empfehlung: kostenlose Subdomain via DuckDNS

DuckDNS vergibt kostenlos eine stabile Subdomain (z. B. `wordlock.duckdns.org`),
die auf deine Heim-IP zeigt — auch bei wechselnder IP. Damit bekommst du mit
Caddy automatisch HTTPS, und die URL ändert sich nie (anders als bei Tunneln).

```bash
# https://www.duckdns.org  -> kostenlosen Token holen
curl "https://www.duckdns.org/update?domains=wordlock&token=<dein-token>&ip="
```

Für dauerhafte Aktualisierung einen Cron-Job anlegen:

```bash
crontab -e
# alle 5 Minuten die IP aktualisieren:
*/5 * * * * curl -s "https://www.duckdns.org/update?domains=wordlock&token=<dein-token>&ip=" >/dev/null
```

Danach im Caddyfile einfach `api.wordlock.duckdns.org` statt
`api.deinedomain.de` verwenden (Abschnitt 6). Voraussetzung: Port 80/443 im
Router auf den Server weiterleiten.

### Schnelltest ohne Portfreigabe: Cloudflare Quick Tunnel

Wenn du erst einmal nur testen willst, ohne Router oder DNS zu konfigurieren:

```bash
cloudflared tunnel --url http://localhost:8000
```

Du bekommst sofort eine HTTPS-URL wie `https://<zufall>.trycloudflare.com`.
**Nachteil:** Die URL ändert sich bei jedem Neustart — du musst dann jedes Mal
die Redirect-URI im Developer Portal, in `.env` und `CORS_ORIGINS` anpassen.
Gut zum Testen, ungeeignet für den Dauerbetrieb.

### Dauerhaft ohne Domain/Portfreigabe: Cloudflare Tunnel (kostenlos)

Kostenlos und stabil, aber du brauchst einen kostenlosen Cloudflare-Account
und einen Domainnamen in deinem Cloudflare-Dashboard (den kann man kostenlos
als Subdomain eines eigenen Bereichs anlegen, z. B. `api.meinbot.de`):

```bash
sudo apt install -y cloudflared
cloudflared tunnel login            # einmalig, öffnet Browser
cloudflared tunnel create wordlock
sudo nano /etc/cloudflared/config.yml
```

```yaml
tunnel: <tunnel-id>
credentials-file: /root/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: api.meinbot.de
    service: http://localhost:8000
  - service: http_status:404
```

```bash
cloudflared tunnel route dns <tunnel-id> api.meinbot.de
sudo systemctl enable cloudflared
cloudflared tunnel run wordlock
```

Die HTTPS-URL übernimmt dann dieselbe Rolle wie oben `api.deinedomain.de`.

## 8. Firewall (UFW)

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Port 8000 bleibt lokal — nur Caddy (80/443) wird nach außen freigegeben.

## 9. Betrieb & Updates

- **Logs:** `docker compose logs -f bot api`
- **Neustart:** `docker compose restart`
- **Update (Code):** `git pull && docker compose up -d --build`
- **Dashboard-Updates** können im Adminbereich veröffentlicht werden; mit
  `DEPLOY_WEBHOOK_URL` optional einen CI-Hook (z. B. Vercel Deploy Hook)
  anstoßen.
- **Backup:** PostgreSQL-Volume sichern
  (`docker compose exec db pg_dump -U wordlock wordlock > backup.sql`).

## Fehlerbehebung

| Problem | Lösung |
| --- | --- |
| Bot startet nicht | `docker compose logs bot` prüfen; Token & Intents kontrollieren |
| Login im Dashboard schlägt fehl | Redirect-URI in `.env` UND im Developer Portal identisch |
| 401 bei API-Aufrufen | `COOKIE_SECURE=true` bei HTTPS, sonst `false` |
| Zertifikat schlägt fehl | Caddy-Log prüfen: DNS-Eintrag muss auf die öffentliche IP zeigen |
| Bot erscheint offline | Server-Member-Intent aktivieren, Bot neu einladen |
