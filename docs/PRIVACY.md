# Datenschutz (WordLock)

WordLock ist als datenschutzfreundlicher Moderation-Bot konzipiert. Diese Seite
dokumentiert, welche Daten verarbeitet werden und wie sie gelöscht werden
können. Sie dient als Grundlage für die Discord-Verifizierung
(Privacy Policy URL) und für DSGVO-Anfragen.

## Verarbeitete Daten

### 1. Server-Konfiguration (Tabelle `servers`)

- Guild-ID, Servername, Besitzer-ID
- Anzahl Mitglieder, Bot-Version
- Einstellungen: Sprache, Moderationslevel, Log-Channel-ID, Aktionen,
  aktive Standardlisten, Status

**Zweck:** Der Bot muss pro Server die gewählte Filter-Konfiguration kennen.

### 2. Benutzerdefinierte Wörter (Tabelle `custom_words`)

- Guild-ID, Wort, Kategorie, Schweregrad, Aktion, aktiviert/Status

**Zweck:** Server-Administratoren pflegen ihre eigenen Filterregeln.

### 3. Verstöße (Tabelle `violations`)

- Guild-ID, User-ID, erkanntes Wort, Kategorie, Schweregrad, Aktion, Zeitpunkt
- **Achtung:** Enthält auch einen Ausschnitt der ursprünglichen Nachricht
  (max. 1500 Zeichen) für die Moderation und Logs.

**Zweck:** Nachvollziehbarkeit der Moderation, Statistiken für das Dashboard.

### 4. Verwarnungen (Tabelle `warnings`)

- Guild-ID, User-ID, Grund, Moderator, Zeitpunkt

**Zweck:** Wiederholungstäter erkennen.

### 5. Dashboard-Benutzer (Tabelle `users`)

- Discord-ID, Benutzername, Discord-Access-/Refresh-Token (nur für OAuth),
  Rolle (Owner/Developer/Moderator)

**Zweck:** Anmeldung am Dashboard und Zugriffskontrolle.

### 6. Bot-Profilbild (Tabelle `bot_profile` + `bot_profile_history`)

- Das aktuelle Bot-Profilbild (als Daten-URI), wer es zuletzt geändert hat
  und wann.
- Änderungsverlauf: Server-ID, wer geändert hat.

**Zweck:** Hochgeladene Profilbilder der Server-Admins speichern und
Änderungen für die Moderation (Reset/Override) nachvollziehen.

## Was WordLock NICHT tut

- Es zeichnet keine Gespräche ohne Grund auf (nur gefilterte Nachrichten).
- Es gibt **keine Daten an Dritte** weiter.
- Es verarbeitet **keine Daten außerhalb von Discord-Kontexten**.
- Nachrichten werden ausschließlich zur Laufzeit geprüft; normale Nachrichten
  werden nicht gespeichert.

## Löschung von Daten

### Selbstbedienung: eigene Daten einsehen & löschen (DSGVO)

Jeder eingeloggte Benutzer kann über die API abfragen, welche persönlichen
Daten über ihn gespeichert sind, und sie selbstständig löschen:

- `GET /api/data-request` → zeigt Anzahl der gespeicherten Verstöße und
  Verwarnungen für die eigene Discord-ID an.
- `POST /api/data-request` → löscht alle `violations` und `warnings` der
  eigenen User-ID und entfernt die OAuth-Tokens (Session wird beendet).

Beide Endpoints setzen eine gültige Session voraus und löschen nur die Daten
der angemeldeten Person. Dadurch entfällt für normale Benutzer der
Kontaktweg über den Betreiber.

### Löschung einzelner Verstöße / Verwarnungen

Server-Administratoren können über das Dashboard Filter-Wörter und Einstellungen
ändern. Die `violations`- und `warnings`-Tabellen können vom Betreiber per SQL
bereinigt werden:

```sql
DELETE FROM violations WHERE guild_id = <guild_id>;
DELETE FROM warnings  WHERE guild_id = <guild_id>;
```

### Löschung eines Servers (Server entfernen / Bot entfernen)

Beim Entfernen des Bots aus einem Server markiert WordLock den Server als
`removed`. Für eine vollständige Löschung:

```sql
DELETE FROM violations   WHERE guild_id = <guild_id>;
DELETE FROM warnings     WHERE guild_id = <guild_id>;
DELETE FROM custom_words WHERE guild_id = <guild_id>;
DELETE FROM servers      WHERE guild_id = <guild_id>;
```

### Kontakt für Lösch- und Auskunftsanfragen

Betreiber: <kontakt@example.com>

Anfragen zur Auskunft oder Löschung gemäß DSGVO werden innerhalb von 30 Tagen
bearbeitet.

## Datenaufbewahrung

| Daten | Aufbewahrung |
| --- | --- |
| `violations` | unbegrenzt, bis gelöscht (Standard) |
| `warnings` | unbegrenzt, bis gelöscht |
| `users` (OAuth-Tokens) | bei Logout nicht gelöscht, Token rotieren |
| `bot_profile` / `bot_profile_history` | unbegrenzt, bis gelöscht |
| Logs (`logs`) | unbegrenzt, bis gelöscht |
