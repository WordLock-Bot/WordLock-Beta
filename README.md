# WordLock

> Professioneller Discord-Moderation-Bot für automatische Wortfilterung,
> Beleidigungserkennung und Community-Sicherheit.

WordLock analysiert Nachrichten in Echtzeit, erkennt Schimpfwörter, Beleidigungen,
toxische Begriffe, Spam und benutzerdefinierte verbotene Wörter — selbst dann,
wenn der Absender versucht, den Filter zu umgehen.

```
"id.iot"  → erkannt
"1di0t"   → erkannt
"i d i o t" → erkannt
"idiot!!!" → erkannt
```

## Features

- **Erweiterte Filter-Engine** mit Textnormalisierung:
  - Unicode/Homoglyph-Erkennung (`sсheisse` → `scheisse`, `fµck` → `fuck`)
  - Leetspeak (`1di0t` → `idiot`, `1d10t` → `idiot`)
  - Zeichen-Separatoren (`i.d.i.o.t`, `f-u-c-k`)
  - Wiederholte Zeichen (`idiottttt` → `idiot`)
  - Deutsche Sonderzeichen (`scheiße` → `scheisse`)
  - Aho-Corasick-Automat für einen einzigen, schnellen Durchlauf
- **Hybrides Filtersystem**
  - Offizielle Standardlisten (`data/default_words_de.json`, `…_en.json`)
  - Server-eigene Wörter in PostgreSQL mit Kategorie, Schweregrad und Aktion
- **Aktionen pro Server**: Nachricht löschen, Benutzer warnen, Timeout, nur loggen
- **Moderationslevel** 1–5 steuert, ab welchem Schweregrad aktiv gehandelt wird
- **Slash-Commands**: `/filter add|remove|list|enable|disable`, `/settings …`
- **Bot-Profilbild** (Dashboard): Server-Admins laden das Profilbild des Bots
  hoch; Bot-Admins können anstößige Bilder im Adminbereich ändern oder
  zurücksetzen (Änderungsverlauf)
- **Feste Activity**: Der Bot zeigt immer „Made by DevCoder“ als Status
- **Web-Dashboard** (Next.js + Tailwind, Discord OAuth2)
  - Übersicht mit Statistiken & Verläufen
  - Filterverwaltung (Standardlisten + eigene Wörter)
  - Einstellungen (Aktionen, Log Channel, Sprache, Moderationslevel)
- **Entwickler-Adminbereich** (rollenbasiert: Owner / Developer / Moderator)
  - Server-Verwaltung, Statistiken, Update-System, Wortlisten-Management, Fehler-Logs
- **Skalierbar**: Bot + API als Docker-Container, PostgreSQL als Datenspeicher

## Architektur

```
WordLock/
├── bot/                    # Discord-Bot (Python, discord.py)
│   ├── main.py             # Einstiegspunkt
│   ├── filter_engine.py    # Normalisierung + Aho-Corasick + Tier-Matching
│   ├── filter_manager.py   # Per-Server kompilierte Filter (Cache)
│   ├── database.py         # PostgreSQL-Zugriff (asyncpg)
│   ├── commands/           # /filter, /settings Slash-Commands
│   └── events/             # on_message, on_message_edit, on_guild_join…
├── api/                    # FastAPI-Backend für das Dashboard
│   ├── main.py             # FastAPI-App, CORS, Lifespan
│   ├── auth.py             # Discord OAuth2 + JWT-Sessions + Rollen
│   ├── database.py         # PostgreSQL-Zugriff
│   └── routers/            # dashboard.py (öffentlich), profile.py (Bot-Profil), admin.py (Entwickler)
├── dashboard/              # Next.js 14 + React + TailwindCSS
│   ├── app/                # Pages (Landing, Dashboard, Admin)
│   ├── components/         # Sidebar, StatCard, Charts, …
│   └── lib/                # API-Client & TypeScript-Typen
├── data/                   # Offizielle Standardwortlisten (JSON)
├── tests/                  # Unit-Tests für die Filter-Engine
├── Dockerfile.bot          # Bot-Container
├── Dockerfile.api          # API-Container
└── docker-compose.yml      # DB + API + Bot
```

## Schnellstart (lokal / Docker)

### 1. Voraussetzungen

- Docker + Docker Compose
- Discord Developer Application (Bot + OAuth2)

Erstelle in der [Discord Developer Portal](https://discord.com/developers/applications):
1. **Application** anlegen.
2. Unter **Bot** den Token kopieren.
3. Unter **OAuth2 → General** `Client ID` und `Client Secret` kopieren,
   als Redirect URL `http://localhost:3000/api/auth/callback` eintragen.
4. Unter **OAuth2 → URL Generator** Scopes `bot` + `applications.commands`
   und die Permissions aus `.env.example` wählen.

### 2. Konfiguration

```bash
cp .env.example .env
# .env ausfüllen: DISCORD_TOKEN, DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET,
# ADMIN_WHITELIST_IDS (deine Discord-ID), JWT_SECRET, DATABASE_URL …
```

### 3. Starten

```bash
docker compose up -d --build
```

- Bot: läuft im Container und ist danach auf Discord online.
- API: http://localhost:8000 (Doku unter `/docs`)
- Dashboard: lokal starten mit

```bash
cd dashboard
npm install
npm run dev
# → http://localhost:3000
```

### 4. Bot einladen

Rufe die in `.env` konfigurierte Invite-URL im Browser auf und wähle einen Server.
Alternativ öffnet das Dashboard nach dem Login „Mit Discord anmelden“ → „Bot einladen“.

## Tests

```bash
python -m unittest tests.test_filter_engine -v
```

## Hosting

| Komponente | Empfehlung |
| --- | --- |
| Dashboard | Vercel (`dashboard/`) |
| Bot | Docker-Container auf Linux-Server / Cloud-VM (`Dockerfile.bot`) |
| API | Docker-Container, gleiche VM (`Dockerfile.api`) |
| API-Verbindung | Cloudflare Tunnel (`./start.sh tunnel`) |
| Datenbank | PostgreSQL 16, lokal beim Bot (Docker `db`-Service) |

Details: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) ·
Eigener Server (Home Lab / VPS): [docs/HOMESERVER.md](docs/HOMESERVER.md)

## Datenschutz

- Der Bot speichert nur Daten, die für die Moderation nötig sind
  (Server-Konfiguration, benutzerdefinierte Wörter, Verstoß-Logs).
- Keine Weitergabe an Dritte, keine Gesprächsaufzeichnungen.
- Details & Löschung: [docs/PRIVACY.md](docs/PRIVACY.md)

## Discord-Verifizierung

WordLock ist auf Verifizierung & Listung ausgelegt
(öffentliche Webseite, OAuth2-Login, Datenschutzerklärung, Datenlöschung,
Wartung über den Adminbereich). Vorbereitung: [docs/VERIFICATION.md](docs/VERIFICATION.md)

## Lizenz

Nur für den Einsatz mit einem eigenen WordLock-Bot. Das Projekt ist als
Ausgangsbasis für einen professionellen Discord-Moderation-Bot gedacht.
