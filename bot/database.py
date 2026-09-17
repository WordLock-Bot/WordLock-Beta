"""PostgreSQL access for the WordLock bot (asyncpg)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import asyncpg

log = logging.getLogger("wordlock.db")

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


SCHEMA = """
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

CREATE INDEX IF NOT EXISTS idx_violations_guild ON violations (guild_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_created ON logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_custom_words_guild ON custom_words (guild_id);
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
    def __init__(self, dsn: Optional[str] = None):
        self._dsn = dsn or os.environ.get("DATABASE_URL")
        if not self._dsn:
            raise RuntimeError(
                "DATABASE_URL is not set. Refusing to fall back to default credentials."
            )
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)
        await self.execute(SCHEMA)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def execute(self, query: str, *args: Any) -> Any:
        return await self._pool.execute(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        return await self._pool.fetchrow(query, *args)

    async def fetch(self, query: str, *args: Any) -> List[asyncpg.Record]:
        return await self._pool.fetch(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self._pool.fetchval(query, *args)

    async def update_heartbeat(self) -> None:
        await self.execute(
            "INSERT INTO bot_heartbeat (id, last_seen) VALUES (1, now()) "
            "ON CONFLICT (id) DO UPDATE SET last_seen = now()"
        )

    # ------------------------------------------------------------------
    # Servers / config
    # ------------------------------------------------------------------

    async def upsert_server(
        self,
        guild_id: int,
        name: str = "",
        owner_id: Optional[int] = None,
        member_count: int = 0,
        bot_version: Optional[str] = None,
        inviter_id: Optional[int] = None,
    ) -> None:
        await self.execute(
            """
            INSERT INTO servers (guild_id, name, owner_id, member_count, bot_version, inviter_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (guild_id) DO UPDATE SET
                name = EXCLUDED.name,
                member_count = EXCLUDED.member_count,
                bot_version = COALESCE(EXCLUDED.bot_version, servers.bot_version),
                inviter_id = COALESCE(EXCLUDED.inviter_id, servers.inviter_id),
                status = CASE WHEN servers.status = 'removed' THEN 'active' ELSE servers.status END,
                updated_at = now()
            """,
            guild_id,
            name,
            owner_id,
            member_count,
            bot_version,
            inviter_id,
        )

    async def set_inviter(self, guild_id: int, inviter_id: int) -> None:
        await self.execute(
            "UPDATE servers SET inviter_id = $2, updated_at = now() WHERE guild_id = $1",
            guild_id,
            inviter_id,
        )

    async def get_server(self, guild_id: int) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow("SELECT * FROM servers WHERE guild_id = $1", guild_id)
        return dict(row) if row else None

    async def update_server(self, guild_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ${i + 1}" for i, k in enumerate(fields))
        values = [
            json.dumps(v) if isinstance(v, (dict, list)) else v for v in fields.values()
        ]
        await self.execute(
            f"UPDATE servers SET {cols}, updated_at = now() WHERE guild_id = ${len(fields) + 1}",
            *values,
            guild_id,
        )

    async def delete_server(self, guild_id: int) -> None:
        await self.execute("DELETE FROM servers WHERE guild_id = $1", guild_id)

    async def record_guild_join(self, guild_id: int, name: str) -> None:
        row = await self.fetchrow(
            "SELECT id FROM guild_history WHERE guild_id = $1 AND left_at IS NULL ORDER BY id DESC LIMIT 1",
            guild_id,
        )
        if row:
            await self.execute(
                "UPDATE guild_history SET name = $2, joined_at = now() WHERE id = $1",
                row["id"], name,
            )
        else:
            await self.execute(
                "INSERT INTO guild_history (guild_id, name, joined_at) VALUES ($1, $2, now())",
                guild_id, name,
            )

    async def record_guild_leave(self, guild_id: int) -> None:
        row = await self.fetchrow(
            "SELECT id FROM guild_history WHERE guild_id = $1 AND left_at IS NULL ORDER BY id DESC LIMIT 1",
            guild_id,
        )
        if row:
            await self.execute(
                "UPDATE guild_history SET left_at = now() WHERE id = $1",
                row["id"],
            )

    async def list_guild_history(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = await self.fetch(
            "SELECT * FROM guild_history ORDER BY id DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]

    async def guild_history_total(self) -> int:
        row = await self.fetchrow("SELECT COUNT(*) AS n FROM guild_history")
        return int(row["n"]) if row else 0

    async def all_servers(self) -> List[Dict[str, Any]]:
        rows = await self.fetch("SELECT * FROM servers ORDER BY created_at ASC")
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Custom words
    # ------------------------------------------------------------------

    async def add_custom_word(
        self, guild_id: int, word: str, category: str, severity: int, action: str
    ) -> bool:
        try:
            await self.execute(
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
        res = await self.execute(
            "DELETE FROM custom_words WHERE guild_id = $1 AND word = $2",
            guild_id,
            word,
        )
        return res.endswith(" 1")

    async def set_custom_word_enabled(self, guild_id: int, word: str, enabled: bool) -> None:
        await self.execute(
            "UPDATE custom_words SET enabled = $3 WHERE guild_id = $1 AND word = $2",
            guild_id,
            word,
            enabled,
        )

    async def get_custom_words(
        self, guild_id: int, enabled_only: bool = True
    ) -> List[Dict[str, Any]]:
        q = "SELECT * FROM custom_words WHERE guild_id = $1"
        if enabled_only:
            q += " AND enabled = TRUE"
        q += " ORDER BY created_at ASC"
        rows = await self.fetch(q, guild_id)
        return [dict(r) for r in rows]

    async def get_word_overrides(self, guild_id: int) -> List[Dict[str, Any]]:
        rows = await self.fetch(
            "SELECT * FROM standard_word_overrides WHERE guild_id = $1", guild_id
        )
        return [dict(r) for r in rows]

    async def set_word_override(
        self,
        guild_id: int,
        word: str,
        action: Optional[str],
        enabled: bool = True,
    ) -> None:
        await self.execute(
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
        res = await self.execute(
            "DELETE FROM standard_word_overrides WHERE guild_id = $1 AND word = $2",
            guild_id,
            word,
        )
        return res.endswith(" 1")

    # ------------------------------------------------------------------
    # Violations / warnings
    # ------------------------------------------------------------------

    async def log_violation(
        self,
        guild_id: int,
        user_id: int,
        message_text: str,
        matched_word: str,
        category: str,
        severity: int,
        action: str,
    ) -> None:
        await self.execute(
            """
            INSERT INTO violations (guild_id, user_id, message_text, matched_word, category, severity, action)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            guild_id,
            user_id,
            message_text,
            matched_word,
            category,
            severity,
            action,
        )
        await self.bump_stat("violations", 1)
        await self.bump_stat(f"action_{action}", 1)

    async def add_warning(
        self, guild_id: int, user_id: int, reason: str, moderator: Optional[int] = None
    ) -> None:
        await self.execute(
            "INSERT INTO warnings (guild_id, user_id, reason, moderator) VALUES ($1, $2, $3, $4)",
            guild_id,
            user_id,
            reason,
            moderator,
        )

    async def warning_count(self, guild_id: int, user_id: int) -> int:
        val = await self.fetchval(
            "SELECT COUNT(*) FROM warnings WHERE guild_id = $1 AND user_id = $2",
            guild_id,
            user_id,
        )
        return int(val or 0)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def bump_stat(self, name: str, amount: int = 1) -> None:
        await self.execute(
            """
            INSERT INTO global_stats (stat_name, day, value)
            VALUES ($1, CURRENT_DATE, $2)
            ON CONFLICT (stat_name, day) DO UPDATE SET value = global_stats.value + $2
            """,
            name,
            amount,
        )

    async def get_stats(
        self, name: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        rows = await self.fetch(
            """
            SELECT day, value FROM global_stats
            WHERE stat_name = $1 AND day >= CURRENT_DATE - $2::int
            ORDER BY day ASC
            """,
            name,
            days,
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Admin / logging
    # ------------------------------------------------------------------

    async def add_log(
        self,
        log_type: str,
        message: str,
        level: str = "info",
        guild_id: Optional[int] = None,
        stacktrace: Optional[str] = None,
    ) -> None:
        await self.execute(
            """
            INSERT INTO logs (type, level, guild_id, message, stacktrace)
            VALUES ($1, $2, $3, $4, $5)
            """,
            log_type,
            level,
            guild_id,
            message,
            stacktrace,
        )

    # ------------------------------------------------------------------
    # Security / incidents (self-protection)
    # ------------------------------------------------------------------

    async def add_incident(
        self,
        guild_id: int,
        kind: str,
        severity: str = "high",
        actor_id: Optional[int] = None,
        detail: Optional[Dict[str, Any]] = None,
        consequence: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = await self.fetchrow(
            """
            INSERT INTO incidents (guild_id, kind, severity, actor_id, detail, consequence)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            guild_id,
            kind,
            severity,
            actor_id,
            json.dumps(detail or {}),
            consequence,
        )
        await self.bump_stat("incidents", 1)
        return dict(row)

    async def open_incidents(self, guild_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if guild_id is not None:
            rows = await self.fetch(
                "SELECT * FROM incidents WHERE guild_id = $1 ORDER BY created_at DESC",
                guild_id,
            )
        else:
            rows = await self.fetch("SELECT * FROM incidents ORDER BY created_at DESC")
        return [dict(r) for r in rows]

    async def resolve_open_incidents(self, guild_id: int) -> None:
        await self.execute(
            "UPDATE incidents SET status = 'resolved', resolved_at = now() "
            "WHERE guild_id = $1 AND status = 'open'",
            guild_id,
        )

    # ------------------------------------------------------------------
    # Update announcements
    # ------------------------------------------------------------------

    async def unannounced_updates(self) -> List[Dict[str, Any]]:
        rows = await self.fetch(
            "SELECT * FROM updates WHERE announced = FALSE ORDER BY id ASC"
        )
        return [dict(r) for r in rows]

    async def mark_update_announced(self, update_id: int) -> None:
        await self.execute("UPDATE updates SET announced = TRUE WHERE id = $1", update_id)

    async def active_servers_for_announce(self) -> List[Dict[str, Any]]:
        rows = await self.fetch(
            "SELECT guild_id, language, log_channel_id "
            "FROM servers WHERE status = 'active'"
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Discord ticket panel system
    # ------------------------------------------------------------------

    async def get_ticket_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow("SELECT * FROM ticket_config WHERE guild_id = $1", guild_id)
        return dict(row) if row else None

    async def set_ticket_config(self, guild_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(f"${i + 1}" for i in range(len(fields)))
        values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in fields.values()]
        await self.execute(
            f"""
            INSERT INTO ticket_config (guild_id, {cols})
            VALUES (${len(fields) + 1}, {placeholders})
            ON CONFLICT (guild_id) DO UPDATE SET
                {", ".join(f"{k} = EXCLUDED.{k}" for k in fields)},
                updated_at = now()
            """,
            *values, guild_id,
        )

    async def all_ticket_configs(self) -> List[Dict[str, Any]]:
        rows = await self.fetch("SELECT * FROM ticket_config WHERE enabled = TRUE")
        return [dict(r) for r in rows]

    async def pending_ticket_deploys(self) -> List[Dict[str, Any]]:
        rows = await self.fetch(
            "SELECT * FROM ticket_config WHERE panel_needs_deploy = TRUE ORDER BY updated_at"
        )
        return [dict(r) for r in rows]

    async def clear_ticket_deploy(self, guild_id: int) -> None:
        await self.execute(
            "UPDATE ticket_config SET panel_needs_deploy = FALSE, updated_at = now() WHERE guild_id = $1",
            guild_id,
        )

    async def get_verify_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow("SELECT * FROM verify_config WHERE guild_id = $1", guild_id)
        return dict(row) if row else None

    async def set_verify_config(self, guild_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(f"${i + 1}" for i in range(len(fields)))
        values = list(fields.values()) + [guild_id]
        await self.execute(
            f"""
            INSERT INTO verify_config (guild_id, {cols})
            VALUES (${len(fields) + 1}, {placeholders})
            ON CONFLICT (guild_id) DO UPDATE SET
                {", ".join(f"{k} = EXCLUDED.{k}" for k in fields)},
                updated_at = now()
            """,
            *values,
        )

    async def all_verify_configs(self) -> List[Dict[str, Any]]:
        rows = await self.fetch("SELECT * FROM verify_config WHERE enabled = TRUE")
        return [dict(r) for r in rows]

    async def log_verify_event(self, guild_id: int, user_id: int, action: str) -> None:
        await self.execute(
            "INSERT INTO verify_events (guild_id, user_id, action) VALUES ($1, $2, $3)",
            guild_id, user_id, action,
        )

    # -- invites ---------------------------------------------------------

    async def record_invite(self, guild_id: int, inviter_id: int, invited_id: int) -> None:
        await self.execute(
            "INSERT INTO invite_track (guild_id, inviter_id, invited_id) VALUES ($1, $2, $3)",
            guild_id, inviter_id, invited_id,
        )

    # -- phishing --------------------------------------------------------

    async def get_phishing_domains(self, guild_id: int, kind: str = "block") -> List[str]:
        rows = await self.fetch(
            "SELECT domain FROM phishing_domains WHERE kind = $1 AND guild_id IN (0, $2)",
            kind, guild_id,
        )
        return [r["domain"] for r in rows]

    async def add_phishing_domain(
        self, guild_id: int, domain: str, kind: str = "block"
    ) -> None:
        domain = domain.strip().lower().rstrip(".")
        if not domain:
            return
        try:
            await self.execute(
                "INSERT INTO phishing_domains (guild_id, domain, kind) VALUES ($1, $2, $3) "
                "ON CONFLICT (guild_id, domain, kind) DO NOTHING",
                guild_id, domain, kind,
            )
        except Exception:
            log.debug("Could not add phishing domain", exc_info=True)

    async def remove_phishing_domain(
        self, guild_id: int, domain: str, kind: str = "block"
    ) -> bool:
        row = await self.execute(
            "DELETE FROM phishing_domains WHERE guild_id = $1 AND domain = $2 AND kind = $3",
            guild_id, domain.strip().lower(), kind,
        )
        return row == "DELETE 1"

    # -- scheduled messages ----------------------------------------------

    async def list_scheduled_messages(self, guild_id: int) -> List[Dict[str, Any]]:
        rows = await self.fetch(
            "SELECT * FROM scheduled_messages WHERE guild_id = $1 ORDER BY created_at DESC",
            guild_id,
        )
        return [dict(r) for r in rows]

    async def create_scheduled_message(
        self,
        guild_id: int,
        channel_id: int,
        content: str,
        interval_minutes: Optional[int] = None,
        daily_hhmm: Optional[str] = None,
        run_at: Optional[Any] = None,
        created_by: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow(
            "INSERT INTO scheduled_messages "
            "(guild_id, channel_id, content, interval_minutes, daily_hhmm, run_at, created_by) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
            guild_id, channel_id, content, interval_minutes, daily_hhmm, run_at, created_by,
        )
        return dict(row) if row else None

    async def delete_scheduled_message(self, message_id: int, guild_id: int) -> bool:
        row = await self.execute(
            "DELETE FROM scheduled_messages WHERE id = $1 AND guild_id = $2",
            message_id, guild_id,
        )
        return row == "DELETE 1"

    async def update_scheduled_message(self, message_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ${i + 1}" for i, k in enumerate(fields))
        await self.execute(
            f"UPDATE scheduled_messages SET {cols} WHERE id = ${len(fields) + 1}",
            *fields.values(), message_id,
        )

    async def due_scheduled_messages(self, now: Any) -> List[Dict[str, Any]]:
        rows = await self.fetch(
            "SELECT * FROM scheduled_messages "
            "WHERE enabled = TRUE AND run_at IS NOT NULL AND run_at <= $1 "
            "ORDER BY run_at ASC LIMIT 20",
            now,
        )
        return [dict(r) for r in rows]

    async def create_discord_ticket(
        self, guild_id: int, channel_id: int, creator_id: int
    ) -> int:
        row = await self.fetchrow(
            "INSERT INTO discord_tickets (guild_id, channel_id, creator_id) "
            "VALUES ($1, $2, $3) RETURNING id",
            guild_id, channel_id, creator_id,
        )
        return int(row["id"])

    async def get_discord_ticket_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow(
            "SELECT * FROM discord_tickets WHERE channel_id = $1 AND status <> 'closed'",
            channel_id,
        )
        return dict(row) if row else None

    async def get_discord_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow("SELECT * FROM discord_tickets WHERE id = $1", ticket_id)
        return dict(row) if row else None

    async def open_discord_tickets(self, guild_id: int, creator_id: int) -> int:
        row = await self.fetchrow(
            "SELECT COUNT(*) AS n FROM discord_tickets "
            "WHERE guild_id = $1 AND creator_id = $2 AND status = 'open'",
            guild_id, creator_id,
        )
        return int(row["n"])

    async def claim_discord_ticket(self, ticket_id: int, claimed_by: int) -> bool:
        status = await self.execute(
            "UPDATE discord_tickets SET status = 'claimed', claimed_by = $2 "
            "WHERE id = $1 AND claimed_by IS NULL",
            ticket_id, claimed_by,
        )
        try:
            rows = int(status.split()[-1])
        except (ValueError, AttributeError):
            rows = 0
        return rows > 0

    async def close_discord_ticket(self, ticket_id: int, closed_by: int, transcript_id: int) -> None:
        await self.execute(
            "UPDATE discord_tickets SET status = 'closed', closed_by = $2, "
            "transcript_id = $3, closed_at = now() WHERE id = $1",
            ticket_id, closed_by, transcript_id,
        )

    async def add_transcript(
        self, guild_id: int, ticket_id: int, channel_id: int, html: str
    ) -> int:
        row = await self.fetchrow(
            "INSERT INTO ticket_transcripts (guild_id, ticket_id, channel_id, html) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            guild_id, ticket_id, channel_id, html,
        )
        return int(row["id"])

    async def get_transcript(self, transcript_id: int) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow(
            "SELECT * FROM ticket_transcripts WHERE id = $1", transcript_id
        )
        return dict(row) if row else None

    async def list_discord_tickets(self, guild_id: int) -> List[Dict[str, Any]]:
        rows = await self.fetch(
            "SELECT * FROM discord_tickets WHERE guild_id = $1 ORDER BY created_at DESC",
            guild_id,
        )
        return [dict(r) for r in rows]