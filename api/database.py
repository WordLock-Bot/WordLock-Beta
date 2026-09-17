from datetime import datetime, timedelta, timezone
import json
from typing import Any, Dict, List, Optional

import asyncpg

DEFAULT_ANTI_SPAM_CONFIG: Dict[str, Any] = {
    "rate_limit": 6,
    "rate_window": 5,
    "mention_limit": 4,
    "mention_window": 5,
    "caps_ratio": 0.8,
    "caps_min_len": 8,
    "link_limit": 3,
    "link_window": 10,
    "emoji_limit": 6,
    "emoji_window": 5,
    "webhook_rate_limit": 8,
    "webhook_window": 5,
    "action": "timeout",
    "timeout_minutes": 60,
}

DEFAULT_ANTI_NUKE_CONFIG: Dict[str, Any] = {
    "channel_limit": 3,
    "channel_window": 5,
    "role_limit": 3,
    "role_window": 5,
    "kick_limit": 3,
    "kick_window": 5,
    "ban_limit": 3,
    "ban_window": 5,
    "webhook_limit": 3,
    "webhook_window": 5,
    "action": "ban",
}


def merge_anti_config(db_config: Any, defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a stored JSONB config (may be {}, partial, or a string) with defaults."""
    if isinstance(db_config, str):
        try:
            db_config = json.loads(db_config)
        except (ValueError, TypeError):
            db_config = {}
    if not isinstance(db_config, dict):
        db_config = {}
    merged = dict(defaults)
    for k, v in db_config.items():
        if v is not None:
            merged[k] = v
    return merged


_SCHEMA = """
CREATE TABLE IF NOT EXISTS servers (
    guild_id         BIGINT PRIMARY KEY,
    name             TEXT DEFAULT '',
    owner_id         BIGINT,
    inviter_id       BIGINT,
    status           TEXT DEFAULT 'active',
    language         TEXT DEFAULT 'en',
    mod_level        INTEGER DEFAULT 3,
    log_channel_id   BIGINT,
    action_delete    BOOLEAN DEFAULT TRUE,
    action_warn      BOOLEAN DEFAULT TRUE,
    action_timeout   BOOLEAN DEFAULT TRUE,
    action_log       BOOLEAN DEFAULT TRUE,
    timeout_minutes  INTEGER DEFAULT 60,
    default_lists    JSONB DEFAULT '{"de": true, "en": true}',
    bypass_roles     JSONB DEFAULT '[]',
    bypass_users     JSONB DEFAULT '[]',
    bypass_privileged BOOLEAN DEFAULT FALSE,
    std_word_action  TEXT DEFAULT 'delete',
    admin_ok         BOOLEAN DEFAULT TRUE,
    bot_version      TEXT,
    member_count     INTEGER DEFAULT 0,
    anti_spam_enabled BOOLEAN DEFAULT FALSE,
    anti_nuke_enabled BOOLEAN DEFAULT FALSE,
    anti_spam_config  JSONB DEFAULT '{}'::jsonb,
    anti_nuke_config  JSONB DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS guild_history (
    id         SERIAL PRIMARY KEY,
    guild_id   BIGINT NOT NULL,
    name       TEXT DEFAULT '',
    joined_at  TIMESTAMPTZ NOT NULL,
    left_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_guild_history_guild ON guild_history (guild_id, id DESC);

CREATE TABLE IF NOT EXISTS custom_words (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    word        TEXT NOT NULL,
    category    TEXT DEFAULT 'custom',
    severity    INTEGER DEFAULT 3,
    action      TEXT DEFAULT 'delete',
    enabled     BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (guild_id, word)
);

CREATE TABLE IF NOT EXISTS standard_word_overrides (
    guild_id    BIGINT NOT NULL,
    word        TEXT NOT NULL,
    action      TEXT,
    enabled     BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS violations (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id     BIGINT,
    user_id      BIGINT,
    message_text TEXT,
    matched_word TEXT,
    category     TEXT,
    severity     INTEGER,
    action       TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS warnings (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id   BIGINT NOT NULL,
    user_id    BIGINT NOT NULL,
    reason     TEXT,
    moderator  BIGINT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS global_stats (
    stat_name  TEXT NOT NULL,
    day        DATE NOT NULL DEFAULT CURRENT_DATE,
    value      BIGINT DEFAULT 0,
    PRIMARY KEY (stat_name, day)
);

CREATE TABLE IF NOT EXISTS users (
    discord_id    BIGINT PRIMARY KEY,
    username      TEXT,
    role          TEXT DEFAULT 'user',
    access_token  TEXT,
    refresh_token TEXT,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS updates (
    id                SERIAL PRIMARY KEY,
    version           TEXT NOT NULL,
    title             TEXT NOT NULL,
    changelog         TEXT,
    maintenance_mode  BOOLEAN DEFAULT FALSE,
    announced         BOOLEAN DEFAULT FALSE,
    kind              TEXT DEFAULT 'announce',
    date              TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS logs (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type       TEXT NOT NULL,
    level      TEXT DEFAULT 'info',
    guild_id   BIGINT,
    message    TEXT,
    stacktrace TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bot_profile (
    id         INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    avatar     TEXT,
    updated_by BIGINT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bot_profile_history (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    field      TEXT NOT NULL,
    guild_id   BIGINT,
    updated_by BIGINT,
    value      TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incidents (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id     BIGINT NOT NULL,
    kind         TEXT NOT NULL,
    severity     TEXT DEFAULT 'high',
    actor_id     BIGINT,
    detail       JSONB NOT NULL DEFAULT '{}'::jsonb,
    consequence  TEXT,
    status       TEXT DEFAULT 'open',
    pushed       BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT now(),
    resolved_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT NOT NULL,
    endpoint   TEXT NOT NULL,
    keys       JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, endpoint)
);

CREATE TABLE IF NOT EXISTS guild_invites (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    discord_id  BIGINT NOT NULL,
    invited_by  BIGINT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'moderator',
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (guild_id, discord_id)
);

CREATE INDEX IF NOT EXISTS idx_guild_invites_guild ON guild_invites (guild_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_guild_invites_user ON guild_invites (discord_id, guild_id);

CREATE INDEX IF NOT EXISTS idx_violations_guild ON violations (guild_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_created ON logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_custom_words_guild ON custom_words (guild_id);
CREATE INDEX IF NOT EXISTS idx_profile_history_created ON bot_profile_history (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_guild ON incidents (guild_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_open ON incidents (pushed, created_at) WHERE status = 'open';
ALTER TABLE updates ADD COLUMN IF NOT EXISTS announced BOOLEAN DEFAULT FALSE;
ALTER TABLE updates ADD COLUMN IF NOT EXISTS kind TEXT DEFAULT 'announce';
ALTER TABLE servers ADD COLUMN IF NOT EXISTS name TEXT DEFAULT '';
ALTER TABLE servers ADD COLUMN IF NOT EXISTS owner_id BIGINT;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS inviter_id BIGINT;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE servers ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en';
ALTER TABLE servers ADD COLUMN IF NOT EXISTS mod_level INTEGER DEFAULT 3;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS log_channel_id BIGINT;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS action_delete BOOLEAN DEFAULT TRUE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS action_warn BOOLEAN DEFAULT TRUE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS action_timeout BOOLEAN DEFAULT TRUE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS action_log BOOLEAN DEFAULT TRUE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS timeout_minutes INTEGER DEFAULT 60;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS default_lists JSONB DEFAULT '{"de": true, "en": true}';
ALTER TABLE servers ADD COLUMN IF NOT EXISTS bypass_roles JSONB DEFAULT '[]';
ALTER TABLE servers ADD COLUMN IF NOT EXISTS bypass_users JSONB DEFAULT '[]';
ALTER TABLE servers ADD COLUMN IF NOT EXISTS bypass_privileged BOOLEAN DEFAULT FALSE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS std_word_action TEXT DEFAULT 'delete';
ALTER TABLE servers ADD COLUMN IF NOT EXISTS admin_ok BOOLEAN DEFAULT TRUE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS bot_version TEXT;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS member_count INTEGER DEFAULT 0;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS anti_spam_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS anti_nuke_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS anti_spam_config JSONB DEFAULT '{}'::jsonb;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS anti_nuke_config JSONB DEFAULT '{}'::jsonb;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS welcome_channel_id BIGINT;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS welcome_message TEXT;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS leave_channel_id BIGINT;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS leave_message TEXT;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS phishing_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS phishing_action TEXT DEFAULT 'delete';
ALTER TABLE servers ADD COLUMN IF NOT EXISTS phishing_config JSONB DEFAULT '{}'::jsonb;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE servers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();


CREATE TABLE IF NOT EXISTS invites (
    guild_id   BIGINT PRIMARY KEY,
    code       TEXT NOT NULL,
    url        TEXT NOT NULL,
    channel_id BIGINT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS team_members (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT '',
    parent_id     INTEGER REFERENCES team_members(id) ON DELETE SET NULL,
    sort_order    INTEGER DEFAULT 0,
    discord_id    BIGINT,
    panel_access  BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE team_members ADD COLUMN IF NOT EXISTS discord_id BIGINT;
ALTER TABLE team_members ADD COLUMN IF NOT EXISTS panel_access BOOLEAN DEFAULT FALSE;
CREATE TABLE IF NOT EXISTS standard_word_overrides (
    guild_id    BIGINT NOT NULL,
    word        TEXT NOT NULL,
    action      TEXT,
    enabled     BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS bot_heartbeat (
    id        INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_seen TIMESTAMPTZ DEFAULT now()
);
INSERT INTO bot_heartbeat (id, last_seen) VALUES (1, now())
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS monitor_settings (
    id              SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    muted           BOOLEAN NOT NULL DEFAULT FALSE,
    down_since      TIMESTAMPTZ,
    last_notified   TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT now()
);
INSERT INTO monitor_settings (id, muted)
VALUES (1, FALSE)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS service_downtime (
    service        TEXT PRIMARY KEY,
    down_since     TIMESTAMPTZ,
    last_notified  TIMESTAMPTZ,
    updated_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ticket_config (
    guild_id             BIGINT PRIMARY KEY,
    panel_channel_id     BIGINT,
    panel_message_id     BIGINT,
    category_id          BIGINT,
    welcome_message      TEXT DEFAULT 'Hallo {mention}! Willkommen in deinem Ticket. Das Team kümmert sich gleich um dich.',
    ticket_name_format   TEXT DEFAULT 'ticket-{user}',
    support_role_ids     JSONB DEFAULT '[]',
    max_open             INTEGER DEFAULT 1,
    enabled              BOOLEAN DEFAULT FALSE,
    created_at           TIMESTAMPTZ DEFAULT now(),
    updated_at           TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE ticket_config ADD COLUMN IF NOT EXISTS panel_needs_deploy BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS discord_tickets (
    id            SERIAL PRIMARY KEY,
    guild_id      BIGINT NOT NULL,
    channel_id    BIGINT,
    creator_id    BIGINT NOT NULL,
    status        TEXT DEFAULT 'open',
    claimed_by    BIGINT,
    transcript_id BIGINT,
    created_at    TIMESTAMPTZ DEFAULT now(),
    closed_at     TIMESTAMPTZ,
    closed_by     BIGINT
);
ALTER TABLE discord_tickets ADD COLUMN IF NOT EXISTS claimed_by BIGINT;
ALTER TABLE discord_tickets ADD COLUMN IF NOT EXISTS transcript_id BIGINT;
ALTER TABLE discord_tickets ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;
ALTER TABLE discord_tickets ADD COLUMN IF NOT EXISTS closed_by BIGINT;
CREATE INDEX IF NOT EXISTS idx_discord_tickets_guild ON discord_tickets (guild_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_discord_tickets_open ON discord_tickets (guild_id, creator_id) WHERE status = 'open';

CREATE TABLE IF NOT EXISTS ticket_transcripts (
    id         SERIAL PRIMARY KEY,
    guild_id   BIGINT NOT NULL,
    ticket_id  BIGINT,
    channel_id BIGINT,
    html       TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE ticket_transcripts ADD COLUMN IF NOT EXISTS channel_id BIGINT;
ALTER TABLE ticket_transcripts ADD COLUMN IF NOT EXISTS html TEXT;

CREATE TABLE IF NOT EXISTS verify_config (
    guild_id             BIGINT PRIMARY KEY,
    panel_channel_id     BIGINT,
    panel_message_id     BIGINT,
    verify_role_id       BIGINT,
    unverified_role_id   BIGINT,
    log_channel_id       BIGINT,
    welcome_message      TEXT DEFAULT '✅ Du wurdest erfolgreich verifiziert. Willkommen, {mention}!',
    dm_message           TEXT DEFAULT 'Willkommen auf {guild}! Du bist jetzt als {user} verifiziert.',
    enabled              BOOLEAN DEFAULT FALSE,
    created_at           TIMESTAMPTZ DEFAULT now(),
    updated_at           TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verify_events (
    id         SERIAL PRIMARY KEY,
    guild_id   BIGINT NOT NULL,
    user_id    BIGINT NOT NULL,
    action     TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_verify_events_guild ON verify_events (guild_id, created_at DESC);

CREATE TABLE IF NOT EXISTS tickets (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type          TEXT NOT NULL DEFAULT 'contact',
    subject       TEXT NOT NULL,
    message       TEXT NOT NULL,
    sender_name   TEXT NOT NULL,
    sender_email  TEXT NOT NULL,
    sender_id     BIGINT,
    guild_id      BIGINT,
    status        TEXT NOT NULL DEFAULT 'open',
    assigned_to   TEXT,
    admin_reply   TEXT,
    replied_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS sender_id BIGINT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS assigned_to TEXT;
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at DESC);
ALTER TABLE servers ADD COLUMN IF NOT EXISTS tickets_enabled BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS ticket_messages (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id   BIGINT NOT NULL,
    author_type TEXT NOT NULL DEFAULT 'user',
    author_name TEXT,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON ticket_messages (ticket_id, created_at);

CREATE TABLE IF NOT EXISTS phishing_domains (
    id         SERIAL PRIMARY KEY,
    guild_id   BIGINT NOT NULL DEFAULT 0,
    domain     TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'block',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (guild_id, domain, kind)
);

CREATE TABLE IF NOT EXISTS invite_track (
    id         SERIAL PRIMARY KEY,
    guild_id   BIGINT NOT NULL,
    inviter_id BIGINT NOT NULL,
    invited_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_invite_track_guild ON invite_track (guild_id, created_at DESC);

CREATE TABLE IF NOT EXISTS scheduled_messages (
    id               SERIAL PRIMARY KEY,
    guild_id         BIGINT NOT NULL,
    channel_id       BIGINT NOT NULL,
    content          TEXT NOT NULL,
    interval_minutes INTEGER,
    daily_hhmm       TEXT,
    run_at           TIMESTAMPTZ,
    enabled          BOOLEAN DEFAULT TRUE,
    created_by       BIGINT,
    created_at       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scheduled_messages_run ON scheduled_messages (enabled, run_at);
"""


class Database:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    @staticmethod
    async def _init_conn(conn: asyncpg.Connection) -> None:
        await conn.set_type_codec(
            "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )
        await conn.set_type_codec(
            "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=1, max_size=10, init=self._init_conn
        )
        async with self._pool.acquire() as conn:
            await conn.execute(_SCHEMA)
            count = await conn.fetchval("SELECT COUNT(*) FROM team_members")
            if count == 0:
                await conn.execute(
                    "INSERT INTO team_members (name, role, sort_order) "
                    "VALUES ('DevCoder', 'Owner/Head developer', 0)"
                )
    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def _fetchrow(self, q: str, *a: Any) -> Optional[dict]:
        async with self._pool.acquire() as c:
            r = await c.fetchrow(q, *a)
            return dict(r) if r else None

    async def _fetch(self, q: str, *a: Any) -> List[dict]:
        async with self._pool.acquire() as c:
            rows = await c.fetch(q, *a)
            return [dict(r) for r in rows]

    async def _execute(self, q: str, *a: Any) -> Any:
        async with self._pool.acquire() as c:
            return await c.execute(q, *a)

    async def _fetchval(self, q: str, *a: Any) -> Any:
        async with self._pool.acquire() as c:
            return await c.fetchval(q, *a)

    # -- users -----------------------------------------------------------

    async def get_user(self, discord_id: int) -> Optional[dict]:
        return await self._fetchrow("SELECT * FROM users WHERE discord_id = $1", discord_id)

    async def upsert_user(
        self,
        discord_id: int,
        username: str,
        access_token: str,
        refresh_token: Optional[str],
    ) -> dict:
        await self._execute(
            """
            INSERT INTO users (discord_id, username, access_token, refresh_token)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (discord_id) DO UPDATE SET
                username = EXCLUDED.username,
                access_token = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token, users.refresh_token),
                updated_at = now()
            """,
            discord_id,
            username,
            access_token,
            refresh_token,
        )
        return await self.get_user(discord_id)

    async def set_user_role(self, discord_id: int, role: str) -> None:
        await self._execute(
            "UPDATE users SET role = $2, updated_at = now() WHERE discord_id = $1",
            discord_id,
            role,
        )

    async def list_developers(self) -> List[dict]:
        return await self._fetch(
            "SELECT discord_id, username, role, created_at, updated_at FROM users "
            "WHERE role IN ('owner','developer','moderator') ORDER BY role"
        )

    # -- servers ---------------------------------------------------------

    async def get_server(self, guild_id: int) -> Optional[dict]:
        return await self._fetchrow("SELECT * FROM servers WHERE guild_id = $1", guild_id)

    async def update_server(self, guild_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ${i + 1}" for i, k in enumerate(fields))
        await self._execute(
            f"UPDATE servers SET {cols}, updated_at = now() WHERE guild_id = ${len(fields) + 1}",
            *fields.values(),
            guild_id,
        )

    async def delete_server(self, guild_id: int) -> None:
        await self._execute("DELETE FROM servers WHERE guild_id = $1", guild_id)

    async def list_guild_history(self, limit: int = 200) -> List[dict]:
        return await self._fetch(
            "SELECT * FROM guild_history ORDER BY id DESC LIMIT $1", limit
        )

    async def guild_history_total(self) -> int:
        return int(
            await self._fetchval("SELECT COUNT(*) FROM guild_history") or 0
        )

    async def guild_history_active(self) -> int:
        return int(
            await self._fetchval(
                "SELECT COUNT(*) FROM guild_history WHERE left_at IS NULL"
            )
            or 0
        )

    async def backfill_guild_history(self) -> None:
        """Seed history entries for the currently active servers so the
        history view shows them even if the bot never emitted a join event
        after this feature shipped."""
        rows = await self._fetch(
            "SELECT guild_id, name, created_at FROM servers WHERE status = 'active'"
        )
        for row in rows:
            existing = await self._fetchrow(
                "SELECT id FROM guild_history WHERE guild_id = $1 ORDER BY id DESC LIMIT 1",
                row["guild_id"],
            )
            if existing:
                continue
            await self._execute(
                "INSERT INTO guild_history (guild_id, name, joined_at) VALUES ($1, $2, $3)",
                row["guild_id"], row.get("name") or "", row.get("created_at") or None,
            )

    # -- panel invites (co-moderators) ----------------------------------

    async def list_guild_invites(self, guild_id: int) -> List[dict]:
        """All users invited to moderate/view this guild's panel."""
        return await self._fetch(
            """
            SELECT gi.*,
                   (u.username IS NOT NULL) AS known,
                   u.username
            FROM guild_invites gi
            LEFT JOIN users u ON u.discord_id = gi.discord_id
            WHERE gi.guild_id = $1
            ORDER BY gi.created_at DESC
            """,
            guild_id,
        )

    async def has_guild_invite(self, guild_id: int, discord_id: int) -> bool:
        row = await self._fetchrow(
            "SELECT id FROM guild_invites WHERE guild_id = $1 AND discord_id = $2",
            guild_id,
            discord_id,
        )
        return row is not None

    async def add_guild_invite(
        self,
        guild_id: int,
        discord_id: int,
        invited_by: int,
        role: str = "moderator",
    ) -> Optional[dict]:
        row = await self._fetchrow(
            """
            INSERT INTO guild_invites (guild_id, discord_id, invited_by, role)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id, discord_id)
            DO UPDATE SET role = EXCLUDED.role, invited_by = EXCLUDED.invited_by, updated_at = now()
            RETURNING *
            """,
            guild_id,
            discord_id,
            invited_by,
            role,
        )
        return row

    async def remove_guild_invite(self, guild_id: int, discord_id: int) -> bool:
        result = await self._fetchrow(
            "DELETE FROM guild_invites WHERE guild_id = $1 AND discord_id = $2 RETURNING id",
            guild_id,
            discord_id,
        )
        return result is not None

    async def guild_invites_for_user(self, discord_id: int) -> List[dict]:
        """Guild ids this user was invited to moderate via invitations."""
        return await self._fetch(
            "SELECT guild_id, role FROM guild_invites WHERE discord_id = $1 ORDER BY created_at DESC",
            discord_id,
        )


    async def force_remove_server(self, guild_id: int) -> None:
        """Delete a server and ALL associated data so it is as if WordLock
        was never on that guild (no Discord call, no leftover rows)."""
        async with self._pool.acquire() as conn:
            for table in (
                "servers",
                "custom_words",
                "standard_word_overrides",
                "violations",
                "warnings",
                "incidents",
                "invites",
                "logs",
                "tickets",
                "discord_tickets",
                "ticket_transcripts",
                "ticket_config",
            ):
                await conn.execute(
                    f"DELETE FROM {table} WHERE guild_id = $1", guild_id
                )

    async def reset_database(self) -> None:
        """Completely wipe the database and recreate the schema + seed rows."""
        async with self._pool.acquire() as conn:
            await conn.execute("DROP SCHEMA public CASCADE")
            await conn.execute("CREATE SCHEMA public")
            await conn.execute(_SCHEMA)
            count = await conn.fetchval("SELECT COUNT(*) FROM team_members")
            if count == 0:
                await conn.execute(
                    "INSERT INTO team_members (name, role, sort_order) "
                    "VALUES ('DevCoder', 'Owner/Head developer', 0)"
                )

    async def all_servers(self) -> List[dict]:
        return await self._fetch("SELECT * FROM servers ORDER BY created_at ASC")

    async def server_count(self) -> int:
        return int(await self._fetchval("SELECT COUNT(*) FROM servers"))

    async def active_server_count(self) -> int:
        return int(
            await self._fetchval("SELECT COUNT(*) FROM servers WHERE status = 'active'")
        )

    # -- custom words ----------------------------------------------------

    async def get_custom_words(self, guild_id: int, enabled_only: bool = True) -> List[dict]:
        q = "SELECT * FROM custom_words WHERE guild_id = $1"
        if enabled_only:
            q += " AND enabled = TRUE"
        return await self._fetch(q + " ORDER BY created_at ASC", guild_id)

    async def add_custom_word(
        self, guild_id: int, word: str, category: str, severity: int, action: str
    ) -> bool:
        try:
            await self._execute(
                """
                INSERT INTO custom_words (guild_id, word, category, severity, action)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (guild_id, word) DO UPDATE SET
                    category = EXCLUDED.category,
                    severity = EXCLUDED.severity,
                    action = EXCLUDED.action,
                    enabled = TRUE
                """,
                guild_id,
                word,
                category,
                severity,
                action,
            )
            return True
        except asyncpg.PostgresError:
            return False

    async def remove_custom_word(self, guild_id: int, word: str) -> bool:
        res = await self._execute(
            "DELETE FROM custom_words WHERE guild_id = $1 AND word = $2", guild_id, word
        )
        return res.endswith(" 1")

    async def set_custom_word_enabled(self, guild_id: int, word: str, enabled: bool) -> None:
        await self._execute(
            "UPDATE custom_words SET enabled = $3 WHERE guild_id = $1 AND word = $2",
            guild_id,
            word,
            enabled,
        )

    # -- standard word overrides ------------------------------------------

    async def get_word_overrides(self, guild_id: int) -> List[dict]:
        return await self._fetch(
            "SELECT * FROM standard_word_overrides WHERE guild_id = $1", guild_id
        )

    async def set_word_override(
        self,
        guild_id: int,
        word: str,
        action: Optional[str],
        enabled: bool = True,
    ) -> None:
        await self._execute(
            """
            INSERT INTO standard_word_overrides (guild_id, word, action, enabled)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id, word) DO UPDATE SET
                action = EXCLUDED.action,
                enabled = EXCLUDED.enabled,
                created_at = now()
            """,
            guild_id,
            word,
            action,
            enabled,
        )

    async def remove_word_override(self, guild_id: int, word: str) -> bool:
        res = await self._execute(
            "DELETE FROM standard_word_overrides WHERE guild_id = $1 AND word = $2",
            guild_id,
            word,
        )
        return res.endswith(" 1")

    # -- violations / stats ----------------------------------------------

    async def violations_today(self) -> int:
        return int(
            await self._fetchval(
                "SELECT COUNT(*) FROM violations WHERE created_at >= CURRENT_DATE"
            )
        )

    async def violations_total(self, guild_id: Optional[int] = None) -> int:
        if guild_id:
            return int(
                await self._fetchval(
                    "SELECT COUNT(*) FROM violations WHERE guild_id = $1", guild_id
                )
            )
        return int(await self._fetchval("SELECT COUNT(*) FROM violations"))

    async def violations_series(self, guild_id: Optional[int] = None, days: int = 30) -> List[dict]:
        base = "WHERE created_at >= CURRENT_DATE - $1::int"
        args: list[Any] = [days]
        if guild_id:
            base += " AND guild_id = $2"
            args.append(guild_id)
        return await self._fetch(
            f"SELECT created_at::date AS day, COUNT(*) AS value "
            f"FROM violations {base} GROUP BY day ORDER BY day",
            *args,
        )

    async def violations_top_words(self, guild_id: Optional[int] = None, limit: int = 10) -> List[dict]:
        base = ""
        args: list[Any] = [limit]
        if guild_id:
            base = "WHERE guild_id = $2 "
            args.append(guild_id)
        return await self._fetch(
            f"SELECT matched_word, COUNT(*) AS count FROM violations "
            f"{base}GROUP BY matched_word ORDER BY count DESC LIMIT $1",
            *args,
        )

    async def action_counts(self, guild_id: Optional[int] = None) -> List[dict]:
        base = ""
        args: list[Any] = []
        if guild_id:
            base = "WHERE guild_id = $1 "
            args.append(guild_id)
        return await self._fetch(
            f"SELECT action, COUNT(*) AS count FROM violations {base}GROUP BY action ORDER BY count DESC",
            *args,
        )

    async def guild_violation_counts(self) -> List[dict]:
        return await self._fetch(
            "SELECT guild_id, COUNT(*) AS count FROM violations GROUP BY guild_id ORDER BY count DESC"
        )

    async def active_users(self) -> int:
        return int(
            await self._fetchval("SELECT COUNT(DISTINCT user_id) FROM violations")
        )

    # -- tickets -----------------------------------------------------------

    async def add_ticket(
        self,
        ticket_type: str,
        subject: str,
        message: str,
        sender_name: str,
        sender_email: str,
        sender_id: Optional[int] = None,
        guild_id: Optional[int] = None,
    ) -> dict:
        return await self._fetchrow(
            """
            INSERT INTO tickets (type, subject, message, sender_name, sender_email, sender_id, guild_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            ticket_type, subject, message, sender_name, sender_email, sender_id, guild_id,
        )

    async def list_tickets(
        self,
        status: Optional[str] = None,
        ticket_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[dict]:
        conditions: List[str] = []
        params: List[Any] = []
        idx = 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if ticket_type:
            conditions.append(f"type = ${idx}")
            params.append(ticket_type)
            idx += 1
        if search:
            conditions.append(f"(subject ILIKE ${idx} OR message ILIKE ${idx} OR sender_name ILIKE ${idx})")
            params.append(f"%{search}%")
            idx += 1
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return await self._fetch(
            f"SELECT * FROM tickets{where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            *params, limit, offset,
        )

    async def get_ticket(self, ticket_id: int) -> Optional[dict]:
        return await self._fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)

    async def update_ticket(self, ticket_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.now(timezone.utc)
        cols = ", ".join(f"{k} = ${i + 1}" for i, k in enumerate(fields))
        await self._execute(
            f"UPDATE tickets SET {cols} WHERE id = ${len(fields) + 1}",
            *fields.values(), ticket_id,
        )

    async def reply_ticket(self, ticket_id: int, admin_reply: str, assigned_to: str) -> None:
        await self._execute(
            "UPDATE tickets SET admin_reply = $2, assigned_to = $3, replied_at = now(), updated_at = now() WHERE id = $1",
            ticket_id, admin_reply, assigned_to,
        )
        await self.add_ticket_message(
            ticket_id, "admin", assigned_to, admin_reply,
        )

    async def delete_ticket(self, ticket_id: int) -> None:
        await self._execute("DELETE FROM tickets WHERE id = $1", ticket_id)
        await self._execute("DELETE FROM ticket_messages WHERE ticket_id = $1", ticket_id)

    async def list_my_tickets(self, sender_id: int) -> List[dict]:
        return await self._fetch(
            "SELECT * FROM tickets WHERE sender_id = $1 ORDER BY created_at DESC",
            sender_id,
        )

    async def add_ticket_message(
        self,
        ticket_id: int,
        author_type: str,
        author_name: Optional[str],
        content: str,
    ) -> dict:
        return await self._fetchrow(
            "INSERT INTO ticket_messages (ticket_id, author_type, author_name, content) "
            "VALUES ($1, $2, $3, $4) RETURNING *",
            ticket_id, author_type, author_name, content,
        )

    async def list_ticket_messages(self, ticket_id: int) -> List[dict]:
        return await self._fetch(
            "SELECT * FROM ticket_messages WHERE ticket_id = $1 ORDER BY created_at, id",
            ticket_id,
        )

    async def open_ticket_count(self) -> int:
        return int(await self._fetchval("SELECT COUNT(*) FROM tickets WHERE status = 'open'"))

    async def ticket_count(self) -> int:
        return int(await self._fetchval("SELECT COUNT(*) FROM tickets"))

    async def server_growth(self, days: int = 30) -> List[dict]:
        return await self._fetch(
            "SELECT created_at::date AS day, COUNT(*) AS value FROM servers "
            "WHERE created_at >= CURRENT_DATE - $1::int GROUP BY day ORDER BY day",
            days,
        )

    # -- updates ---------------------------------------------------------

    async def list_updates(self, limit: int = 20) -> List[dict]:
        return await self._fetch("SELECT * FROM updates ORDER BY date DESC LIMIT $1", limit)

    async def add_update(
        self,
        version: str,
        title: str,
        changelog: Optional[str],
        maintenance_mode: bool = False,
        kind: str = "announce",
    ) -> dict:
        row = await self._fetchrow(
            """
            INSERT INTO updates (version, title, changelog, maintenance_mode, kind)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            version,
            title,
            changelog,
            maintenance_mode,
            kind,
        )
        return row

    async def maintenance_mode(self) -> bool:
        row = await self._fetchrow(
            "SELECT maintenance_mode FROM updates ORDER BY date DESC LIMIT 1"
        )
        return bool(row and row["maintenance_mode"])

    # -- logs ------------------------------------------------------------

    async def add_log(
        self,
        log_type: str,
        message: str,
        level: str = "info",
        guild_id: Optional[int] = None,
        stacktrace: Optional[str] = None,
    ) -> None:
        await self._execute(
            "INSERT INTO logs (type, level, guild_id, message, stacktrace) VALUES ($1,$2,$3,$4,$5)",
            log_type,
            level,
            guild_id,
            message,
            stacktrace,
        )

    async def get_logs(
        self,
        level: Optional[str] = None,
        log_type: Optional[str] = None,
        guild_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[dict]:
        clauses: list[str] = []
        args: list[Any] = []
        if level:
            args.append(level)
            clauses.append(f"level = ${len(args)}")
        if log_type:
            args.append(log_type)
            clauses.append(f"type = ${len(args)}")
        if guild_id:
            args.append(guild_id)
            clauses.append(f"guild_id = ${len(args)}")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        args.append(limit)
        return await self._fetch(
            f"SELECT * FROM logs {where} ORDER BY created_at DESC LIMIT ${len(args)}", *args
        )

    async def error_count(self) -> int:
        return int(
            await self._fetchval(
                "SELECT COUNT(*) FROM logs WHERE level IN ('error','critical')"
            )
        )

    # -- bot profile ------------------------------------------------------

    async def get_bot_profile(self) -> Optional[dict]:
        return await self._fetchrow("SELECT * FROM bot_profile WHERE id = 1")

    async def save_bot_profile(self, fields: Dict[str, Any], updated_by: int) -> dict:
        """Upsert the singleton bot profile row. Values that are None clear a field."""
        if not fields:
            return await self.get_bot_profile()
        existing = await self.get_bot_profile()
        if existing:
            cols = ", ".join(f"{k} = ${i + 1}" for i, k in enumerate(fields))
            await self._execute(
                f"UPDATE bot_profile SET {cols}, updated_by = ${len(fields) + 1}, "
                f"updated_at = now() WHERE id = 1",
                *fields.values(),
                updated_by,
            )
        else:
            cols = ", ".join(["id", *fields.keys(), "updated_by"])
            placeholders = ", ".join(
                [f"${i + 1}" for i in range(len(fields) + 1)]
            )
            await self._execute(
                f"INSERT INTO bot_profile ({cols}) VALUES (1, {placeholders})",
                *fields.values(),
                updated_by,
            )
        return await self.get_bot_profile()

    async def add_profile_history(
        self,
        field: str,
        updated_by: int,
        guild_id: Optional[int] = None,
        value: Optional[str] = None,
    ) -> None:
        await self._execute(
            "INSERT INTO bot_profile_history (field, guild_id, updated_by, value) "
            "VALUES ($1, $2, $3, $4)",
            field,
            guild_id,
            updated_by,
            value,
        )

    async def get_profile_history(self, limit: int = 50) -> List[dict]:
        return await self._fetch(
            "SELECT * FROM bot_profile_history ORDER BY created_at DESC LIMIT $1", limit
        )

    # -- security / incidents --------------------------------------------

    async def list_incidents(
        self, limit: int = 100, guild_id: Optional[int] = None, status: Optional[str] = None
    ) -> List[dict]:
        clauses: list[str] = []
        args: list[Any] = []
        if guild_id:
            args.append(guild_id)
            clauses.append(f"guild_id = ${len(args)}")
        if status:
            args.append(status)
            clauses.append(f"status = ${len(args)}")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        args.append(limit)
        return await self._fetch(
            f"SELECT * FROM incidents {where} ORDER BY created_at DESC LIMIT ${len(args)}",
            *args,
        )

    async def get_incident(self, incident_id: int) -> Optional[dict]:
        return await self._fetchrow("SELECT * FROM incidents WHERE id = $1", incident_id)

    async def open_incident_count(self) -> int:
        return int(
            await self._fetchval("SELECT COUNT(*) FROM incidents WHERE status = 'open'")
        )

    async def resolve_incident(self, incident_id: int) -> bool:
        res = await self._execute(
            "UPDATE incidents SET status = 'resolved', resolved_at = now() WHERE id = $1",
            incident_id,
        )
        return res.endswith(" 1")

    async def resolve_open_incidents(self, guild_id: int) -> int:
        res = await self._execute(
            "UPDATE incidents SET status = 'resolved', resolved_at = now() "
            "WHERE guild_id = $1 AND status = 'open'",
            guild_id,
        )
        try:
            return int(res.split()[-1])
        except (ValueError, IndexError):
            return 0

    async def unprocessed_incidents(self, limit: int = 50) -> List[dict]:
        return await self._fetch(
            "SELECT * FROM incidents WHERE status = 'open' AND pushed = FALSE "
            "ORDER BY created_at ASC LIMIT $1",
            limit,
        )

    async def mark_incident_pushed(self, incident_id: int) -> None:
        await self._execute(
            "UPDATE incidents SET pushed = TRUE WHERE id = $1", incident_id
        )

    # -- push subscriptions ----------------------------------------------

    async def upsert_push_subscription(
        self, user_id: int, endpoint: str, keys: Dict[str, Any]
    ) -> None:
        await self._execute(
            """
            INSERT INTO push_subscriptions (user_id, endpoint, keys)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, endpoint) DO UPDATE SET
                keys = EXCLUDED.keys,
                updated_at = now()
            """,
            user_id,
            endpoint,
            json.dumps(keys),
        )

    async def all_push_subscriptions(self) -> List[dict]:
        return await self._fetch("SELECT * FROM push_subscriptions")

    async def push_subscriptions_for_user(self, user_id: int) -> List[dict]:
        return await self._fetch(
            "SELECT * FROM push_subscriptions WHERE user_id = $1", user_id
        )

    async def admin_push_subscriptions(self) -> List[dict]:
        """All push subscriptions belonging to WordLock staff.

        Staff = users whose stored role is owner/developer/moderator OR whose
        Discord ID is in the ADMIN_WHITELIST_IDS env (same logic as auth).
        """
        import os

        whitelist = {int(i) for i in os.environ.get("ADMIN_WHITELIST_IDS", "").split(",") if i.strip()}
        if whitelist:
            return await self._fetch(
                "SELECT ps.* FROM push_subscriptions ps "
                "JOIN users u ON u.discord_id = ps.user_id "
                "WHERE u.role IN ('owner', 'developer', 'moderator') "
                "OR u.discord_id = ANY($1::bigint[])",
                list(whitelist),
            )
        return await self._fetch(
            "SELECT ps.* FROM push_subscriptions ps "
            "JOIN users u ON u.discord_id = ps.user_id "
            "WHERE u.role IN ('owner', 'developer', 'moderator')"
        )

    async def remove_push_subscription(self, user_id: int, endpoint: str) -> None:
        await self._execute(
            "DELETE FROM push_subscriptions WHERE user_id = $1 AND endpoint = $2",
            user_id,
            endpoint,
        )

    # -- invites ----------------------------------------------------------

    async def get_invite(self, guild_id: int) -> Optional[dict]:
        return await self._fetchrow("SELECT * FROM invites WHERE guild_id = $1", guild_id)

    async def delete_invite(self, guild_id: int) -> None:
        await self._execute("DELETE FROM invites WHERE guild_id = $1", guild_id)

    async def save_invite(
        self,
        guild_id: int,
        code: str,
        url: str,
        channel_id: Optional[int],
        expires_at: datetime,
    ) -> dict:
        await self._execute(
            """
            INSERT INTO invites (guild_id, code, url, channel_id, expires_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id) DO UPDATE SET
                code = EXCLUDED.code,
                url = EXCLUDED.url,
                channel_id = EXCLUDED.channel_id,
                expires_at = EXCLUDED.expires_at,
                created_at = now()
            """,
            guild_id,
            code,
            url,
            channel_id,
            expires_at,
        )
        return await self.get_invite(guild_id)

    # -- team -------------------------------------------------------------

    async def list_team(self) -> List[dict]:
        return await self._fetch("SELECT * FROM team_members ORDER BY sort_order, id")

    async def list_team_public(self) -> List[dict]:
        return await self._fetch(
            "SELECT id, name, role, parent_id, sort_order "
            "FROM team_members ORDER BY sort_order, id"
        )

    async def team_panel_access(self, discord_id: int) -> bool:
        return bool(
            await self._fetchval(
                "SELECT TRUE FROM team_members WHERE discord_id = $1 AND panel_access = TRUE LIMIT 1",
                discord_id,
            )
        )

    async def add_team_member(
        self,
        name: str,
        role: str,
        parent_id: Optional[int],
        sort_order: int,
        discord_id: Optional[int] = None,
        panel_access: bool = False,
    ) -> Optional[dict]:
        return await self._fetchrow(
            "INSERT INTO team_members (name, role, parent_id, sort_order, discord_id, panel_access) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
            name,
            role,
            parent_id,
            sort_order,
            discord_id,
            panel_access,
        )

    async def update_team_member(self, member_id: int, **fields: Any) -> Optional[dict]:
        if not fields:
            return await self._fetchrow(
                "SELECT * FROM team_members WHERE id = $1", member_id
            )
        cols = ", ".join(f"{k} = ${i + 1}" for i, k in enumerate(fields))
        await self._execute(
            f"UPDATE team_members SET {cols} WHERE id = ${len(fields) + 1}",
            *fields.values(),
            member_id,
        )
        return await self._fetchrow("SELECT * FROM team_members WHERE id = $1", member_id)

    async def delete_team_member(self, member_id: int) -> bool:
        res = await self._execute(
            "DELETE FROM team_members WHERE id = $1", member_id
        )
        return res.endswith(" 1")

    # -- heartbeat ---------------------------------------------------------

    async def update_heartbeat(self) -> None:
        await self._execute(
            "INSERT INTO bot_heartbeat (id, last_seen) VALUES (1, now()) "
            "ON CONFLICT (id) DO UPDATE SET last_seen = now()"
        )

    async def last_heartbeat(self) -> Optional[float]:
        row = await self._fetchrow(
            "SELECT EXTRACT(EPOCH FROM last_seen)::float AS ts FROM bot_heartbeat WHERE id = 1"
        )
        return row["ts"] if row else None

    # -- monitor settings (downtime alerts) --------------------------------

    async def get_monitor_settings(self) -> dict:
        row = await self._fetchrow("SELECT * FROM monitor_settings WHERE id = 1")
        return row or {"muted": False, "down_since": None, "last_notified": None}

    async def set_monitor_muted(self, muted: bool) -> None:
        await self._execute(
            "UPDATE monitor_settings SET muted = $1, updated_at = now() WHERE id = 1",
            muted,
        )

    async def set_monitor_state(
        self, down_since: Optional[float], last_notified: Optional[float]
    ) -> None:
        await self._execute(
            "UPDATE monitor_settings "
            "SET down_since = CASE WHEN $1::float IS NULL THEN NULL "
            "   ELSE to_timestamp($1) END, "
            "last_notified = CASE WHEN $2::float IS NULL THEN NULL "
            "   ELSE to_timestamp($2) END, "
            "updated_at = now() "
            "WHERE id = 1",
            down_since,
            last_notified,
        )

    async def get_service_downtime(self) -> dict:
        rows = await self._fetch("SELECT * FROM service_downtime")
        return {
            r["service"]: {
                "down_since": r["down_since"].isoformat() if r["down_since"] else None,
                "last_notified": r["last_notified"].isoformat()
                if r["last_notified"]
                else None,
            }
            for r in rows
        }

    async def set_service_downtime(
        self, service: str, down_since: Optional[float], last_notified: Optional[float]
    ) -> None:
        await self._execute(
            "INSERT INTO service_downtime (service, down_since, last_notified, updated_at) "
            "VALUES ($1, CASE WHEN $2::float IS NULL THEN NULL ELSE to_timestamp($2) END, "
            "   CASE WHEN $3::float IS NULL THEN NULL ELSE to_timestamp($3) END, now()) "
            "ON CONFLICT (service) DO UPDATE SET "
            "   down_since = CASE WHEN EXCLUDED.down_since IS NULL THEN NULL "
            "      ELSE EXCLUDED.down_since END, "
            "   last_notified = CASE WHEN EXCLUDED.last_notified IS NULL THEN NULL "
            "      ELSE EXCLUDED.last_notified END, "
            "   updated_at = now()",
            service,
            down_since,
            last_notified,
        )

    # -- discord tickets --------------------------------------------------

    async def get_ticket_config(self, guild_id: int) -> Optional[dict]:
        return await self._fetchrow("SELECT * FROM ticket_config WHERE guild_id = $1", guild_id)

    async def set_ticket_config(self, guild_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(f"${i + 1}" for i in range(len(fields)))
        await self._execute(
            f"""
            INSERT INTO ticket_config (guild_id, {cols})
            VALUES (${len(fields) + 1}, {placeholders})
            ON CONFLICT (guild_id) DO UPDATE SET
                {", ".join(f"{k} = EXCLUDED.{k}" for k in fields)},
                updated_at = now()
            """,
            *fields.values(), guild_id,
        )

    async def all_ticket_configs(self) -> List[dict]:
        return await self._fetch("SELECT * FROM ticket_config WHERE enabled = TRUE")

    async def pending_ticket_deploys(self) -> List[dict]:
        return await self._fetch(
            "SELECT * FROM ticket_config WHERE panel_needs_deploy = TRUE ORDER BY updated_at"
        )

    async def clear_ticket_deploy(self, guild_id: int) -> None:
        await self._execute(
            "UPDATE ticket_config SET panel_needs_deploy = FALSE, updated_at = now() WHERE guild_id = $1",
            guild_id,
        )

    # -- verify system -----------------------------------------------------

    async def get_verify_config(self, guild_id: int) -> Optional[dict]:
        return await self._fetchrow("SELECT * FROM verify_config WHERE guild_id = $1", guild_id)

    async def set_verify_config(self, guild_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(f"${i + 1}" for i in range(len(fields)))
        await self._execute(
            f"""
            INSERT INTO verify_config (guild_id, {cols})
            VALUES (${len(fields) + 1}, {placeholders})
            ON CONFLICT (guild_id) DO UPDATE SET
                {", ".join(f"{k} = EXCLUDED.{k}" for k in fields)},
                updated_at = now()
            """,
            *fields.values(), guild_id,
        )

    async def all_verify_configs(self) -> List[dict]:
        return await self._fetch("SELECT * FROM verify_config WHERE enabled = TRUE")

    async def log_verify_event(self, guild_id: int, user_id: int, action: str) -> None:
        await self._execute(
            "INSERT INTO verify_events (guild_id, user_id, action) VALUES ($1, $2, $3)",
            guild_id, user_id, action,
        )

    async def verify_stat(self, guild_id: int, days: int = 30) -> int:
        row = await self._fetchrow(
            "SELECT COUNT(*) AS n FROM verify_events "
            "WHERE guild_id = $1 AND action = 'verified' AND created_at > now() - make_interval(days => $2)",
            guild_id, days,
        )
        return int(row["n"]) if row and row["n"] else 0

    async def verify_overview(self, recent_limit: int = 50) -> dict:
        async def _n(sql: str, *args: Any) -> int:
            row = await self._fetchrow(sql, *args)
            return int(row["n"]) if row and row["n"] else 0

        total = await _n("SELECT COUNT(*) AS n FROM verify_events WHERE action = 'verified'")
        today = await _n(
            "SELECT COUNT(*) AS n FROM verify_events WHERE action = 'verified' AND created_at::date = CURRENT_DATE"
        )
        last_7d = await _n(
            "SELECT COUNT(*) AS n FROM verify_events WHERE action = 'verified' AND created_at > now() - interval '7 days'"
        )
        last_30d = await _n(
            "SELECT COUNT(*) AS n FROM verify_events WHERE action = 'verified' AND created_at > now() - interval '30 days'"
        )
        locked = await _n("SELECT COUNT(*) AS n FROM verify_events WHERE action = 'lock'")
        per_guild = await self._fetch(
            "SELECT ve.guild_id, s.name AS guild_name, "
            "COUNT(*) FILTER (WHERE ve.action = 'verified') AS verified, "
            "COUNT(*) FILTER (WHERE ve.action = 'lock') AS locked "
            "FROM verify_events ve "
            "LEFT JOIN servers s ON s.guild_id = ve.guild_id "
            "GROUP BY ve.guild_id, s.name ORDER BY verified DESC, ve.guild_id"
        )
        recent = await self._fetch(
            "SELECT ve.id, ve.guild_id, s.name AS guild_name, ve.user_id, ve.action, ve.created_at "
            "FROM verify_events ve "
            "LEFT JOIN servers s ON s.guild_id = ve.guild_id "
            "ORDER BY ve.created_at DESC LIMIT $1",
            recent_limit,
        )
        return {
            "total": total,
            "today": today,
            "last_7d": last_7d,
            "last_30d": last_30d,
            "locked": locked,
            "per_guild": per_guild,
            "recent": recent,
        }

    # -- invites ---------------------------------------------------------

    async def invite_leaderboard(
        self, guild_id: Optional[int] = None, days: int = 30, limit: int = 20
    ) -> List[dict]:
        cond = "created_at > now() - make_interval(days => $1)"
        args: List[Any] = [days, limit]
        if guild_id:
            cond += " AND guild_id = $2"
            args = [days, guild_id, limit]
        return await self._fetch(
            f"SELECT inviter_id, COUNT(*) AS invites FROM invite_track WHERE {cond} "
            "GROUP BY inviter_id ORDER BY invites DESC LIMIT $%d" % len(args),
            *args,
        )

    async def invite_stats(self, guild_id: int, days: int = 30) -> dict:
        total = await self._fetchval(
            "SELECT COUNT(*) FROM invite_track WHERE guild_id = $1", guild_id
        )
        recent = await self._fetchval(
            "SELECT COUNT(*) FROM invite_track WHERE guild_id = $1 "
            "AND created_at > now() - make_interval(days => $2)",
            guild_id, days,
        )
        series = await self._fetch(
            "SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS date, "
            "COUNT(*) AS n FROM invite_track "
            "WHERE guild_id = $1 AND created_at > now() - interval '14 days' "
            "GROUP BY 1 ORDER BY 1",
            guild_id,
        )
        return {
            "total": int(total or 0),
            "recent": int(recent or 0),
            "series": series,
        }

    async def invite_global_stats(self) -> dict:
        total = await self._fetchval("SELECT COUNT(*) FROM invite_track")
        recent30 = await self._fetchval(
            "SELECT COUNT(*) FROM invite_track "
            "WHERE created_at > now() - interval '30 days'"
        )
        leaderboard = await self.invite_leaderboard(days=30)
        return {
            "total": int(total or 0),
            "recent30": int(recent30 or 0),
            "leaderboard": leaderboard,
        }

    # -- scheduled messages ----------------------------------------------

    async def list_scheduled_messages(self, guild_id: int) -> List[dict]:
        return await self._fetch(
            "SELECT * FROM scheduled_messages WHERE guild_id = $1 ORDER BY created_at DESC",
            guild_id,
        )

    async def create_scheduled_message(
        self,
        guild_id: int,
        channel_id: int,
        content: str,
        interval_minutes: Optional[int] = None,
        daily_hhmm: Optional[str] = None,
        run_at: Optional[Any] = None,
        created_by: Optional[int] = None,
    ) -> Optional[dict]:
        return await self._fetchrow(
            "INSERT INTO scheduled_messages "
            "(guild_id, channel_id, content, interval_minutes, daily_hhmm, run_at, created_by) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
            guild_id, channel_id, content, interval_minutes, daily_hhmm, run_at, created_by,
        )

    async def delete_scheduled_message(self, message_id: int, guild_id: int) -> bool:
        row = await self._execute(
            "DELETE FROM scheduled_messages WHERE id = $1 AND guild_id = $2",
            message_id, guild_id,
        )
        return row == "DELETE 1"

    # -- phishing --------------------------------------------------------

    async def get_phishing_domains(self, guild_id: int, kind: str = "block") -> List[str]:
        rows = await self._fetch(
            "SELECT domain FROM phishing_domains WHERE kind = $1 AND guild_id IN (0, $2)",
            kind, guild_id,
        )
        return [r["domain"] for r in rows]

    async def add_phishing_domain(
        self, guild_id: int, domain: str, kind: str = "block"
    ) -> bool:
        domain = domain.strip().lower().rstrip(".")
        if not domain:
            return False
        try:
            await self._execute(
                "INSERT INTO phishing_domains (guild_id, domain, kind) VALUES ($1, $2, $3) "
                "ON CONFLICT (guild_id, domain, kind) DO NOTHING",
                guild_id, domain, kind,
            )
            return True
        except Exception:
            return False

    async def remove_phishing_domain(
        self, guild_id: int, domain: str, kind: str = "block"
    ) -> bool:
        row = await self._execute(
            "DELETE FROM phishing_domains WHERE guild_id = $1 AND domain = $2 AND kind = $3",
            guild_id, domain.strip().lower(), kind,
        )
        return row == "DELETE 1"

    async def create_discord_ticket(self, guild_id: int, channel_id: int, creator_id: int) -> int:
        row = await self._fetchrow(
            "INSERT INTO discord_tickets (guild_id, channel_id, creator_id) "
            "VALUES ($1, $2, $3) RETURNING id",
            guild_id, channel_id, creator_id,
        )
        return int(row["id"])

    async def get_discord_ticket_by_channel(self, channel_id: int) -> Optional[dict]:
        return await self._fetchrow(
            "SELECT * FROM discord_tickets WHERE channel_id = $1 AND status <> 'closed'",
            channel_id,
        )

    async def get_discord_ticket(self, ticket_id: int) -> Optional[dict]:
        return await self._fetchrow("SELECT * FROM discord_tickets WHERE id = $1", ticket_id)

    async def open_discord_tickets(self, guild_id: int, creator_id: int) -> int:
        return int(
            await self._fetchval(
                "SELECT COUNT(*) FROM discord_tickets "
                "WHERE guild_id = $1 AND creator_id = $2 AND status = 'open'",
                guild_id, creator_id,
            )
        )

    async def claim_discord_ticket(self, ticket_id: int, claimed_by: int) -> None:
        await self._execute(
            "UPDATE discord_tickets SET status = 'claimed', claimed_by = $2 WHERE id = $1",
            ticket_id, claimed_by,
        )

    async def close_discord_ticket(self, ticket_id: int, closed_by: int, transcript_id: int) -> None:
        await self._execute(
            "UPDATE discord_tickets SET status = 'closed', closed_by = $2, "
            "transcript_id = $3, closed_at = now() WHERE id = $1",
            ticket_id, closed_by, transcript_id,
        )

    async def add_transcript(self, guild_id: int, ticket_id: int, channel_id: int, html: str) -> int:
        row = await self._fetchrow(
            "INSERT INTO ticket_transcripts (guild_id, ticket_id, channel_id, html) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            guild_id, ticket_id, channel_id, html,
        )
        return int(row["id"])

    async def get_transcript(self, transcript_id: int) -> Optional[dict]:
        return await self._fetchrow("SELECT * FROM ticket_transcripts WHERE id = $1", transcript_id)

    async def list_discord_tickets(self, guild_id: int) -> List[dict]:
        return await self._fetch(
            "SELECT * FROM discord_tickets WHERE guild_id = $1 ORDER BY created_at DESC",
            guild_id,
        )
