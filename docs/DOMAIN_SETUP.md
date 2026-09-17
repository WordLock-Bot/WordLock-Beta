# Eigene Domain einrichten

Anleitung für den Umstieg von der schnell wechselnden Quick-Tunnel-URL
(`https://<zufall>.trycloudflare.com`) auf eine **stabile, eigene Domain**.

Ziel am Ende:

| Teil | URL |
| --- | --- |
| Dashboard (Vercel) | `https://wordlock.deine-domain.tld` |
| API (dein Server) | `https://api.deine-domain.tld` |

Damit ist `NEXT_PUBLIC_API_URL` **einmalig** gesetzt und ändert sich nie
wieder — kein Tunnel-URL-Rotieren, kein erneutes Deployen bei jedem
Container-Neustart.

---

## 0. Voraussetzungen

- Eine Domain (empfohlen: bei **Cloudflare Registrar** registrieren → keine
  Extrakosten, DNS und Tunnel in einem Account).
  - `.dev` / `.bot` als gTLD, oder eine passende Länderdomain.
- Ein Cloudflare-Account (kostenlos).
- Zugriff auf den Server, auf dem API + Bot + DB laufen (Docker).
- Zugriff auf das Vercel-Projekt `wordlock`, org/team
  `team_8L0RAhPNLU0MeIqhqmPBvYBY`, projectId `prj_d8GZkgkHs0BwX8jsWaNrv9IOp6yG`.

> **Wichtig:** Für einen **benannten Tunnel** müssen Domain und Tunnel im
> **selben** Cloudflare-Account liegen. Deshalb scheidet eine
> `is-a.bot`-Subdomain für die API aus (siehe Abschnitt 8).

---

## 1. Domain zu Cloudflare hinzufügen

1. Domain bei Cloudflare Registrar kaufen (oder Nameserver der Domain auf
   Cloudflare umstellen).
2. In der Cloudflare-Übersicht warten, bis die Zone **Active** ist.
3. Nichts weiteres an DNS ändern — der Tunnel legt die Records selbst an.

---

## 2. Benannten Tunnel anlegen

Auf dem **Server** (dort, wo die API läuft):

```bash
# 1) Login im Browser (erzeugt ~/.cloudflared/cert.pem)
cloudflared tunnel login

# 2) Tunnel erstellen – notiere die Tunnel-ID aus der Ausgabe
cloudflared tunnel create wordlock

# 3) DNS-Record für die API anlegen (CNAME -> <tunnel-id>.cfargotunnel.com)
cloudflared tunnel route dns wordlock api.deine-domain.tld
```

Konfiguration `~/.cloudflared/config.yml`:

```yaml
tunnel: wordlock
credentials-file: /home/<user>/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: api.deine-domain.tld
    service: http://localhost:8000
  - service: http_status:404
```

Tunnel testen:

```bash
cloudflared tunnel run wordlock
# in zweitem Terminal:
curl https://api.deine-domain.tld/api/status
```

### Tunnel als Dienst (dauerhaft, übersteht Reboots)

```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

> Ab hier ist die API-URL **stabil** — der Tunnel verbindet sich vom Server
> nach außen, es wird **kein Port** geöffnet.

---

## 3. API-Umgebungsvariablen anpassen (`.env`)

Auf dem Server in `.env` eintragen und API/Bot neu starten:

```env
DISCORD_REDIRECT_URI=https://wordlock.deine-domain.tld/api/auth/callback
DASHBOARD_URL=https://wordlock.deine-domain.tld
CORS_ORIGINS=https://wordlock.deine-domain.tld
COOKIE_SECURE=true
```

```bash
docker compose up -d --force-recreate api bot
```

---

## 4. Dashboard-Domain mit Vercel verbinden

1. Vercel → Projekt `wordlock` → **Settings → Domains** → Domain
   hinzufügen (`wordlock.deine-domain.tld`).
2. Vercel zeigt die nötigen DNS-Records, z. B.:
   - `CNAME  wordlock  →  <hash>.vercel-dns-017.com` (bzw. `cname.vercel-dns.com`)
3. Diese Records in Cloudflare anlegen. Nach wenigen Minuten steht der Status
   auf **Valid**.

> Falls die Domain direkt auf Vercel zeigen soll (kein Cloudflare-Proxy
> nötig): einfach die von Vercel angezeigten Werte übernehmen.

---

## 5. `NEXT_PUBLIC_API_URL` einmalig setzen

Nur noch **einmal** nötig, danach nie wieder:

```bash
cd dashboard
npx vercel env rm NEXT_PUBLIC_API_URL production -y
npx vercel env add NEXT_PUBLIC_API_URL production
# → Wert eingeben: https://api.deine-domain.tld
```

Danach einmal deployen (siehe Abschnitt 6).

---

## 6. Dashboard deployen

Der Code-Deploy läuft über die **GitHub Action** (`.github/workflows/deploy-vercel.yml`),
getriggert durch Pushes auf `config/instance-url.json` oder manuell:

```bash
git commit --allow-empty -m "deploy: dashboard" && git push
# oder: GitHub → Actions → "Deploy to Vercel (dashboard)" → Run workflow
```

Benötigtes Secret im Repo: `VERCEL_TOKEN` (existiert bereits).

---

## 7. Discord-OAuth umstellen

Im [Discord Developer Portal](https://discord.com/developers/applications)
unter **OAuth2 → Redirects** ergänzen:

```
https://wordlock.deine-domain.tld/api/auth/callback
```

(Die alte Vercel-URL kann entfernt werden.)

---

## 8. `is-a.bot` — was geht, was nicht

`is-a.bot` ist ein kostenloser Subdomain-Dienst (PR-basiert). Es gilt:

| Nutzung | Möglich? |
| --- | --- |
| Dashboard-Front über CNAME zu `*.vercel-dns-017.com` | ✅ ja |
| API über `cfargotunnel.com` | ❌ nein (Tunnel muss im **selben** CF-Account liegen) |
| Self-Hosting per NS-Records | ❌ nein (nicht erlaubt) |
| `URL`-Records | ❌ nein (nur CNAME/TXT/…) |

**Fazit:** `is-a.bot` eignet sich für eine schöne Dashboard-Adresse, aber
**nicht** als stabile API-Domain. Für die API braucht es eine eigene Domain
(Abschnitte 1–3).

Registrierung (falls gewünscht): Fork von `free-domains/is-a.bot`,
`domains/<name>.json` + `domains/_vercel.<name>.json` anlegen, Pull Request
gegen `main`. Aktuell offen: PR **#352** für `wordlock.is-a.bot`
(CI grün, wartet auf Maintainer-Review).

---

## 9. Aufräumen (nach dem Umstieg)

Nicht mehr benötigt, sobald die eigene Domain läuft:

- Quick-Tunnel-Automatik / `.tunnel-url`
- `scripts/update-vercel-api-url.sh`
- Der URL-Watcher, der `config/instance-url.json` automatisch committet
  (kann abgeschaltet werden — die URL ist jetzt fest).

Optional in `.env` bzw. Portainer entfernen:

```env
VERCEL_TOKEN=
VERCEL_PROJECT_ID=
VERCEL_DEPLOY_HOOK_URL=
```

---

## 10. Checkliste

- [ ] Domain bei Cloudflare aktiv
- [ ] `cloudflared tunnel create wordlock` ausgeführt
- [ ] `cloudflared tunnel route dns wordlock api.deine-domain.tld`
- [ ] API erreichbar: `curl https://api.deine-domain.tld/api/status`
- [ ] `cloudflared service install` + `systemctl enable --now cloudflared`
- [ ] `.env`: `DISCORD_REDIRECT_URI`, `DASHBOARD_URL`, `CORS_ORIGINS`, `COOKIE_SECURE`
- [ ] Vercel-Domain `wordlock.deine-domain.tld` auf **Valid**
- [ ] `NEXT_PUBLIC_API_URL=https://api.deine-domain.tld` gesetzt + neu deployt
- [ ] Discord-OAuth-Redirect ergänzt
- [ ] Login auf dem Dashboard getestet
- [ ] Quick-Tunnel-Automatik abgeschaltet

---

## Kurzfassung (TL;DR)

```bash
# Server
cloudflared tunnel login
cloudflared tunnel create wordlock
cloudflared tunnel route dns wordlock api.deine-domain.tld
# config.yml anlegen (siehe 2.), dann:
sudo cloudflared service install && sudo systemctl enable --now cloudflared

# Dashboard-Env (einmalig)
cd dashboard && npx vercel env rm NEXT_PUBLIC_API_URL production -y \
  && npx vercel env add NEXT_PUBLIC_API_URL production   # https://api.deine-domain.tld
```

Danach in Vercel die Dashboard-Domain verbinden und in den API-Env-Variablen
`DISCORD_REDIRECT_URI` / `DASHBOARD_URL` / `CORS_ORIGINS` auf die neue Domain
setzen. Fertig — die URL bleibt für immer stabil.
