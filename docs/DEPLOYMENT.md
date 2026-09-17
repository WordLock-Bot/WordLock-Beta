# Deployment

WordLock besteht aus drei Teilen, die unabhängig voneinander gehostet werden
können: **Dashboard** (Vercel), **API** (Docker) und **Bot** (Docker), dazu eine
**PostgreSQL-Datenbank**.

> Alles auf dem eigenen Server betreiben (Home Lab / VPS): siehe
> [docs/HOMESERVER.md](HOMESERVER.md).

```
┌───────────────┐   HTTPS    ┌──────────────────┐   Tunnel   ┌──────────────┐
│  Dashboard    │ ─────────► │  cloudflared     │ ─────────► │      API     │
│  (Vercel)     │            │  (Tunnel)        │            │ (Docker VM)  │
└───────────────┘            └──────────────────┘            └──────┬───────┘
                                                                    │  TCP
                                                             ┌──────▼───────┐
                                                             │  PostgreSQL  │
                                                             │ (lokal, VM)  │
                                                             └──────────────┘
                                                                    │
                                                             ┌──────▼───────┐
                                                             │  Bot (Docker)│  ◄──► Discord Gateway
                                                             └──────────────┘
```

## 1. Datenbank (PostgreSQL)

Die Datenbank läuft lokal auf demselben Server wie Bot und API — als
`db`-Service aus `docker-compose.yml` (PostgreSQL 16, Port 5432).

```bash
docker compose up -d db
```

Das Schema wird beim ersten Start von Bot und API automatisch angelegt.

## 2. Bot (Docker)

```bash
docker build -f Dockerfile.bot -t wordlock-bot .
docker run -d --name wordlock-bot \
  --env-file .env \
  -e DATABASE_URL=postgresql://user:pass@db-host:5432/wordlock \
  wordlock-bot
```

Der Bot verbindet sich mit dem Discord Gateway, synchronisiert Slash-Commands
und meldet sich in `servers`-Tabelle an, sobald er auf einem Server ist.

## 3. API (Docker)

```bash
docker build -f Dockerfile.api -t wordlock-api .
docker run -d --name wordlock-api -p 8000:8000 --env-file .env wordlock-api
```

Wichtig für die API:

- `DISCORD_REDIRECT_URI` auf die **Dashboard-URL** zeigen lassen (z. B.
  `https://wordlock.vercel.app/api/auth/callback`). Das Dashboard leitet
  `/api/*` serverseitig an die API weiter; nur so landet der Login-Cookie
  auf dem Dashboard-Host.
- `DASHBOARD_URL` auf die Dashboard-URL zeigen lassen (z. B.
  `https://wordlock.vercel.app`) — dorthin leitet die API nach dem Login.
- `CORS_ORIGINS` auf die Dashboard-URL setzen
- `COOKIE_SECURE=true` in Produktion
- `JWT_SECRET` = langes, zufälliges Secret

### 3a. API öffentlich erreichen (Cloudflare Tunnel)

Das auf Vercel gehostete Dashboard muss die lokale API über das Internet
erreichen können. Da die API auf dem eigenen Server (ohne öffentliche IP /
Domain) läuft, wird sie über einen **Cloudflare Tunnel** öffentlich
bereitgestellt — ganz ohne Port-Freigabe und ohne Root-Rechte.

```bash
# 1) cloudflared installieren (einmalig, ohne Root)
bash scripts/install-cloudflared.sh

# 2) API + Bot + DB starten und den Tunnel anlegen
./start.sh --tunnel
# → schreibt die öffentliche URL nach .tunnel-url und gibt sie aus
#   (https://<zufall>.trycloudflare.com)

# 3) Tunnel-URL in Vercel setzen und Dashboard neu deployen
bash scripts/update-vercel-api-url.sh
```

> **Hinweis:** Ein „Quick Tunnel" ohne eigene Domain bekommt bei jedem
> Neustart eine neue, zufällige URL. Nach einem Neustart des Tunnels einfach
> `bash scripts/update-vercel-api-url.sh` erneut ausführen. Für eine stabile
> URL: eigene Domain in Cloudflare registrieren und einen benannten Tunnel
> mit Hostname anlegen.

## 4. Dashboard (Vercel)

Ohne Git-Repo über die Vercel CLI (empfohlen für dieses Projekt):

```bash
bash scripts/deploy-vercel.sh
```

Umgebungsvariablen in Vercel setzen:

| Variable | Wert |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | die Tunnel-URL, z. B. `https://xxx.trycloudflare.com` |
| `NEXT_PUBLIC_INVITE_URL` | Discord-Invite-URL mit Bot-Permissions |

Hinweis: Der in `next.config.mjs` konfigurierte `rewrites`-Proxy leitet
`/api/*` an `NEXT_PUBLIC_API_URL` weiter, damit OAuth-Cookies
same-origin funktionieren.

## 5. Bot-Updates über das Admin-Panel

Im Adminbereich → **Updates** kann eine neue Version veröffentlicht werden.

- Das Update wird in der Tabelle `updates` gespeichert und im Dashboard angezeigt.
- Optional: `DEPLOY_WEBHOOK_URL` in `.env` setzen (z. B. Vercel Deploy Hook
  oder ein CI-Webhook). Beim Veröffentlichen wird dieser Webhook mit
  `{"version": ..., "title": ...}` aufgerufen und die Bot-Instanzen neu gebaut.
- Ein Wartungsmodus kann pro Update mit aktiviert werden und wird im
  öffentlichen Dashboard als Hinweis angezeigt.

## Sicherheit

- Der Adminbereich ist nur mit **Discord OAuth2** + **Whitelist**
  (`ADMIN_WHITELIST_IDS`) erreichbar.
- Rollen (Owner/Developer/Moderator) werden in der Tabelle `users` verwaltet
  und pro Endpoint geprüft.
- Sessions laufen über signierte JWTs in `httpOnly`-Cookies.
- Secrets ausschließlich über Umgebungsvariablen, niemals im Repo.
