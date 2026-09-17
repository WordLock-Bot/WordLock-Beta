# Discord-Verifizierung & Listung

WordLock ist so gebaut, dass es die Voraussetzungen für eine öffentliche
Listung und Verifizierung bei Discord erfüllt. Diese Checkliste zeigt die
Schritte.

## Voraussetzungen (Discord Developer Portal)

### 1. Application-Einstellungen

- **App Icon** (512×512 PNG) und **App Name** hinterlegen.
- **Description** ausfüllen (kurz, was der Bot tut).
- **Tags** wählen (Moderation, Safety, Tools).

### 2. OAuth2

- Redirect-URL auf die Dashboard-URL setzen (Cookie landet dann auf dem
  Dashboard-Host):
  `https://<dashboard>.vercel.app/api/auth/callback`
- Scopes: `identify`, `guilds`, `bot`, `applications.commands`
- Permissions: siehe `.env.example` (`DISCORD_INVITE_URL`).

### 3. Bot-Einstellungen

- **Public Bot** an.
- **Require OAuth2 Code Grant** aus (falls nicht gewollt).
- Intents in der Discord-App aktivieren:
  - `Message Content Intent` (zwingend für die Filterung)
  - `Server Members Intent` (für Timeout/Moderation)
  - `Presence Intent` (optional)

## Voraussetzungen für die Verifizierung (Discord)

Discord verlangt u. a.:

| Anforderung | Wo im Repo / wie lösen |
| --- | --- |
| Privacy Policy URL | `docs/PRIVACY.md` öffentlich hosten (z. B. `/privacy`) |
| Terms of Service | eigene TOS-Seite anlegen (z. B. `/terms`) |
| Kein Gate hinter Anmeldung | Landing-Page erklärt den Bot (`dashboard/app/page.tsx`) |
| OAuth2 Login | vorhanden (`/api/auth/login`, Callback, `/api/auth/me`) |
| Keine versteckten Daten | Datenschutz-Doku vorhanden |
| Support-Bereich | Support-Server oder Support-URL in der Application angeben |
| Langfristiger Betrieb | Hosting-Doku: `docs/DEPLOYMENT.md` |

### 4. Datenlöschung

Für die Verifizierung kann ein einfacher, öffentlich erreichbarer Endpoint
ergänzt werden, z. B.:

```python
# api/routers/dashboard.py
@router.get("/data-request")
async def data_request(user=Depends(auth.current_user), db: Database = ...):
    uid = user["discord_id"]
    await db._execute("DELETE FROM violations WHERE user_id = $1", uid)
    await db._execute("DELETE FROM warnings WHERE user_id = $1", uid)
    return {"ok": True}
```

## Nach der Listung

- Nutzungsstatistiken über das Admin-Panel pflegen (Updates, Wortlisten).
- Im Adminbereich → **Updates** neue Versionen ankündigen und veröffentlichen.
- Bei Problemen: `docs/DEPLOYMENT.md` Wartung/Neustart der Container.
