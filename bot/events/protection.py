"""Active anti-spam / anti-nuke protection.

Unlike the self-protection in ``security.py`` (which disables the bot when it
is itself attacked), this module actively stops spam and nuke attempts by
regular users *and* bots/webhooks on servers that opted in. The affected
member is stopped (delete / warn / timeout / kick / ban), roles are stripped
and webhooks are removed to limit damage, and an incident is recorded so it
is pushed to the admins' dashboard.

The punishment is not reversible for deleted channels/roles (Discord does not
offer an API to restore them), so the focus is on stopping the perpetrator as
fast as possible and blocking further actions.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import re
from collections import deque
from typing import Any, Deque, Dict, Optional

import discord
from discord.ext import commands

from ..database import (
    DEFAULT_ANTI_NUKE_CONFIG,
    DEFAULT_ANTI_SPAM_CONFIG,
    merge_anti_config,
)
from ..version import __version__

log = logging.getLogger("wordlock.bot.protection")

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
EMOJI_RE = re.compile(
    r"<a?:\w+:\d+>|[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]"
)

INCIDENT_LABELS: Dict[str, str] = {
    "antispam_rate": "Message flood (rate limit)",
    "antispam_mentions": "Mention spam",
    "antispam_caps": "All-caps spam",
    "antispam_links": "Link spam",
    "antispam_emoji": "Emoji spam",
    "antispam_webhook": "Webhook/bot message flood",
    "antinuke_channels": "Mass channel create/delete (nuke attempt)",
    "antinuke_roles": "Mass role create/delete (nuke attempt)",
    "antinuke_ban": "Mass ban (nuke attempt)",
    "antinuke_kick": "Mass kick (nuke attempt)",
    "antinuke_webhooks": "Webhook creation flood (nuke attempt)",
}

PUNISH_COOLDOWN = 60.0  # seconds; avoid re-reporting the same offender repeatedly


def _is_bot_message(message: discord.Message) -> bool:
    return bool(message.author.bot or message.webhook_id)


class ProtectionEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> user_id -> deque of event timestamps
        self._rates: Dict[int, Dict[int, Deque[float]]] = {}
        self._mentions: Dict[int, Dict[int, Deque[float]]] = {}
        self._webhook_msgs: Dict[int, Deque[float]] = {}
        # guild_id -> deque of structural event timestamps
        self._channels: Dict[int, Deque[float]] = {}
        self._roles: Dict[int, Deque[float]] = {}
        self._bans: Dict[int, Deque[float]] = {}
        self._removals: Dict[int, Deque[float]] = {}
        self._webhook_creates: Dict[int, Deque[float]] = {}
        # guild_id -> user_id -> last punished timestamp
        self._last_punished: Dict[int, Dict[int, float]] = {}
        # guild_id -> kind -> last incident timestamp
        self._last_incident: Dict[int, Dict[str, float]] = {}

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    async def _server(self, guild_id: int) -> Optional[dict]:
        try:
            return await self.bot.db.get_server(guild_id)
        except Exception:
            return None

    @staticmethod
    def _spam_cfg(server: dict) -> dict:
        return merge_anti_config(server.get("anti_spam_config"), DEFAULT_ANTI_SPAM_CONFIG)

    @staticmethod
    def _nuke_cfg(server: dict) -> dict:
        return merge_anti_config(server.get("anti_nuke_config"), DEFAULT_ANTI_NUKE_CONFIG)

    @staticmethod
    def _bypassed(member: discord.Member, server: dict) -> bool:
        if server.get("bypass_privileged"):
            if member.id == member.guild.owner_id:
                return True
            if member.guild_permissions.administrator:
                return True
        try:
            users = server.get("bypass_users") or []
            if isinstance(users, str):
                import json

                users = json.loads(users)
            if member.id in {int(u) for u in users}:
                return True
            roles = server.get("bypass_roles") or []
            if isinstance(roles, str):
                import json

                roles = json.loads(roles)
            if {r.id for r in member.roles} & {int(r) for r in roles}:
                return True
        except Exception:
            log.exception("Bypass check failed for guild %s", member.guild.id)
        return False

    # ------------------------------------------------------------------
    # Counting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count(
        bucket: Dict[int, Deque[float]],
        guild_id: int,
        now: float,
        window: float,
        limit: int,
    ) -> bool:
        dq = bucket.setdefault(guild_id, deque(maxlen=limit + 20))
        dq.append(now)
        while dq and now - dq[0] > window:
            dq.popleft()
        return len(dq) >= limit

    @staticmethod
    def _count_user(
        bucket: Dict[int, Dict[int, Deque[float]]],
        guild_id: int,
        user_id: int,
        now: float,
        window: float,
        limit: int,
    ) -> bool:
        per_guild = bucket.setdefault(guild_id, {})
        dq = per_guild.setdefault(user_id, deque(maxlen=limit + 20))
        dq.append(now)
        while dq and now - dq[0] > window:
            dq.popleft()
        return len(dq) >= limit

    def _can_punish(self, guild_id: int, user_id: int, now: float) -> bool:
        last = self._last_punished.get(guild_id, {}).get(user_id)
        return last is None or now - last >= PUNISH_COOLDOWN

    def _mark_punished(self, guild_id: int, user_id: int, now: float) -> None:
        self._last_punished.setdefault(guild_id, {})[user_id] = now

    # ------------------------------------------------------------------
    # Enforcement ("Täter stoppen + Schaden begrenzen")
    # ------------------------------------------------------------------

    async def _enforce_member(
        self,
        guild: discord.Guild,
        member: discord.Member,
        action: str,
        reason: str,
        timeout_minutes: int = 60,
    ) -> str:
        """Apply a punishment to a member. Timeouts cannot be applied to bots,
        so a bot falls back to a kick for timeout/warn and to ban for ban."""
        executed = ""
        if action == "delete":
            return "delete"
        if action == "warn":
            await self.bot.db.add_warning(
                guild.id,
                member.id,
                reason=reason,
                moderator=self.bot.user.id if self.bot.user else None,
            )
            return "warn"
        if member.bot:
            if action == "ban":
                try:
                    await member.ban(reason=reason)
                    return "ban"
                except discord.HTTPException:
                    log.debug("Could not ban bot %s on guild %s", member.id, guild.id)
                    return ""
            action = "kick"
        if action == "kick":
            try:
                await member.kick(reason=reason)
                return "kick"
            except discord.HTTPException:
                log.debug("Could not kick %s on guild %s", member.id, guild.id)
                return ""
        if action == "ban":
            try:
                await member.ban(reason=reason)
                return "ban"
            except discord.HTTPException:
                log.debug("Could not ban %s on guild %s", member.id, guild.id)
                return ""
        # timeout
        if not guild.me.guild_permissions.moderate_members:
            log.debug("No moderate_members permission on guild %s", guild.id)
            return ""
        if member.top_role >= guild.me.top_role:
            log.debug("Cannot timeout %s: same/higher role", member.id)
            return ""
        try:
            await member.timeout(
                discord.utils.utcnow() + datetime.timedelta(minutes=timeout_minutes),
                reason=reason,
            )
            return "timeout"
        except discord.HTTPException:
            log.debug("Could not timeout %s on guild %s", member.id, guild.id)
            return ""

    async def _strip_roles(self, guild: discord.Guild, member: discord.Member) -> None:
        """Remove all assignable roles from the perpetrator to limit damage."""
        removable = [r for r in member.roles if r.is_assignable()]
        if not removable:
            return
        try:
            await member.edit(
                roles=[r for r in member.roles if r.managed],
                reason="WordLock: anti-nuke damage control",
            )
        except discord.HTTPException:
            log.debug("Could not strip roles from %s on guild %s", member.id, guild.id)

    async def _record_incident(
        self,
        guild: discord.Guild,
        kind: str,
        consequence: str,
        actor_id: Optional[int] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self.bot.db.add_incident(
            guild_id=guild.id,
            kind=kind,
            severity="critical",
            actor_id=actor_id,
            detail=detail or {},
            consequence=consequence,
        )
        await self.bot.db.add_log(
            "security",
            f"Incident {kind} on guild {guild.id}",
            "critical",
            guild_id=guild.id,
        )
        log.warning("Protection triggered on guild %s: %s", guild.id, kind)

    def _incident_cooled(self, guild_id: int, kind: str, now: float) -> bool:
        """True when an incident of this kind was recorded on this guild recently."""
        last = self._last_incident.get(guild_id, {}).get(kind)
        return last is not None and now - last < PUNISH_COOLDOWN

    def _mark_incident(self, guild_id: int, kind: str, now: float) -> None:
        self._last_incident.setdefault(guild_id, {})[kind] = now

    # ------------------------------------------------------------------
    # Anti-spam
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or not message.content:
            return
        if self.bot.user and message.author.id == self.bot.user.id:
            return
        server = await self._server(message.guild.id)
        if not server or server.get("status") != "active":
            return
        if not server.get("anti_spam_enabled"):
            return

        cfg = self._spam_cfg(server)
        now = asyncio.get_event_loop().time()
        author = message.author
        is_bot = _is_bot_message(message)

        # Webhook / bot message flood (counts all bots+webhooks together).
        if is_bot:
            if self._count(
                self._webhook_msgs,
                message.guild.id,
                now,
                cfg["webhook_window"],
                cfg["webhook_rate_limit"],
            ):
                await self._punish_spammer(
                    message, "antispam_webhook", cfg, now, bot=True
                )
            return

        member = message.guild.get_member(author.id)
        if member is None or self._bypassed(member, server):
            return

        # Plain message rate.
        if self._count_user(
            self._rates,
            message.guild.id,
            author.id,
            now,
            cfg["rate_window"],
            cfg["rate_limit"],
        ):
            await self._punish_spammer(message, "antispam_rate", cfg, now)
            return

        # Mention spam.
        mention_count = len(message.mentions) + len(message.role_mentions)
        if mention_count and self._count_user(
            self._mentions,
            message.guild.id,
            author.id,
            now,
            cfg["mention_window"],
            cfg["mention_limit"],
        ):
            await self._punish_spammer(message, "antispam_mentions", cfg, now)
            return

        # Caps spam.
        letters = [c for c in message.content if c.isalpha()]
        if letters and len(letters) >= cfg["caps_min_len"]:
            upper = sum(1 for c in letters if c.isupper())
            if upper / len(letters) >= cfg["caps_ratio"]:
                await self._punish_spammer(message, "antispam_caps", cfg, now)
                return

        # Link spam.
        if len(URL_RE.findall(message.content)) >= cfg["link_limit"]:
            await self._punish_spammer(message, "antispam_links", cfg, now)
            return

        # Emoji spam.
        if len(EMOJI_RE.findall(message.content)) >= cfg["emoji_limit"]:
            await self._punish_spammer(message, "antispam_emoji", cfg, now)

    async def _punish_spammer(
        self,
        message: discord.Message,
        kind: str,
        cfg: dict,
        now: float,
        bot: bool = False,
    ) -> None:
        if not self._can_punish(message.guild.id, message.author.id, now):
            return
        self._mark_punished(message.guild.id, message.author.id, now)

        # Always delete the offending message when possible.
        if message.guild.me.guild_permissions.manage_messages:
            try:
                await message.delete()
            except discord.HTTPException:
                pass

        action = cfg.get("action", "timeout")
        if bot and action in ("warn", "timeout"):
            action = "kick"

        member = message.guild.get_member(message.author.id)
        executed = action
        if member is not None and not bot:
            executed = await self._enforce_member(
                message.guild,
                member,
                action,
                f"WordLock anti-spam: {kind}",
                timeout_minutes=int(cfg.get("timeout_minutes", 60)),
            )
            if action == "timeout" and executed == "timeout":
                await self._strip_roles(message.guild, member)

        consequence = (
            f"WordLock removed the message and applied '{executed or action}' "
            f"to the perpetrator (anti-spam: {INCIDENT_LABELS.get(kind, kind)})."
        )
        await self._record_incident(
            message.guild,
            kind,
            consequence,
            actor_id=message.author.id,
            detail={"action": executed or action, "user_id": str(message.author.id)},
        )

    # ------------------------------------------------------------------
    # Anti-nuke
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        await self._nuke_counter(getattr(channel, "guild", None), self._channels,
                                 "antinuke_channels", "channel_limit", "channel_window")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        await self._nuke_counter(getattr(channel, "guild", None), self._channels,
                                 "antinuke_channels", "channel_limit", "channel_window")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        await self._nuke_counter(getattr(role, "guild", None), self._roles,
                                 "antinuke_roles", "role_limit", "role_window")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        await self._nuke_counter(getattr(role, "guild", None), self._roles,
                                 "antinuke_roles", "role_limit", "role_window")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        if self.bot.user and user.id == self.bot.user.id:
            return
        await self._nuke_counter(guild, self._bans, "antinuke_ban", "ban_limit", "ban_window")

    @commands.Cog.listener()
    async def on_member_remove(self, guild: discord.Guild, user: discord.User) -> None:
        if self.bot.user and user.id == self.bot.user.id:
            return
        # ``on_member_remove`` also fires on voluntary leaves. Only count it as
        # a kick when the audit log shows a recent member_kick entry for this user.
        if not await self._is_recent_kick(guild, user):
            return
        await self._nuke_counter(guild, self._removals, "antinuke_kick", "kick_limit", "kick_window")

    async def _is_recent_kick(self, guild: discord.Guild, user: discord.User) -> bool:
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                if entry.target and entry.target.id == user.id:
                    return True
        except (discord.HTTPException, discord.Forbidden):
            return False
        return False

    @commands.Cog.listener()
    async def on_guild_webhooks_update(self, guild: discord.Guild, channel: discord.abc.GuildChannel) -> None:
        await self._nuke_counter(guild, self._webhook_creates, "antinuke_webhooks",
                                 "webhook_limit", "webhook_window")

    async def _nuke_counter(
        self,
        guild: Optional[discord.Guild],
        bucket: Dict[int, Deque[float]],
        kind: str,
        limit_key: str,
        window_key: str,
    ) -> None:
        if guild is None:
            return
        server = await self._server(guild.id)
        if not server or server.get("status") != "active":
            return
        if not server.get("anti_nuke_enabled"):
            return
        cfg = self._nuke_cfg(server)
        now = asyncio.get_event_loop().time()
        if not self._count(guild.id, bucket, now, cfg[window_key], cfg[limit_key]):
            return
        if self._incident_cooled(guild.id, kind, now):
            return
        await self._handle_nuke(guild, kind, cfg, now)

    async def _handle_nuke(self, guild: discord.Guild, kind: str, cfg: dict, now: float) -> None:
        actor = await self._find_actor(guild, kind)
        action = cfg.get("action", "ban")
        executed = action

        if actor is not None:
            member = guild.get_member(actor.id)
            if member is not None and not self._bypassed(member, await self._server(guild.id) or {}):
                if self._can_punish(guild.id, actor.id, now):
                    self._mark_punished(guild.id, actor.id, now)
                    executed = await self._enforce_member(
                        guild, member, action, f"WordLock anti-nuke: {kind}"
                    )
                    if member.bot:
                        # Remove any webhooks the bot may have created to limit damage.
                        await self._cleanup_webhooks(guild)
                    else:
                        await self._strip_roles(guild, member)
                else:
                    executed = f"{action} (already punished)"
            else:
                await self._cleanup_webhooks(guild)
        else:
            # No actor found (no audit-log access): at least clean up webhooks.
            await self._cleanup_webhooks(guild)

        self._mark_incident(guild.id, kind, now)
        consequence = (
            f"WordLock stopped the nuke attempt and applied '{executed}' to the "
            f"perpetrator (anti-nuke: {INCIDENT_LABELS.get(kind, kind)}). "
            "Deleted channels/roles cannot be restored via the Discord API."
        )
        await self._record_incident(
            guild,
            kind,
            consequence,
            actor_id=actor.id if actor else None,
            detail={
                "action": executed,
                "actor_id": str(actor.id) if actor else "unknown (no audit-log access)",
            },
        )

    async def _find_actor(self, guild: discord.Guild, kind: str) -> Optional[discord.abc.User]:
        action_map = {
            "antinuke_channels": getattr(discord.AuditLogAction, "channel_delete", None),
            "antinuke_roles": getattr(discord.AuditLogAction, "role_delete", None),
            "antinuke_ban": getattr(discord.AuditLogAction, "ban", None),
            "antinuke_kick": getattr(discord.AuditLogAction, "kick", None),
            "antinuke_webhooks": getattr(discord.AuditLogAction, "webhook_create", None),
        }
        audit_action = action_map.get(kind)
        if audit_action is None:
            return None
        try:
            async for entry in guild.audit_logs(limit=1, action=audit_action):
                if entry.user and not (self.bot.user and entry.user.id == self.bot.user.id):
                    return entry.user
        except (discord.HTTPException, discord.Forbidden):
            return None
        return None

    async def _cleanup_webhooks(self, guild: discord.Guild) -> None:
        """Delete all webhooks to cut off a webhook-based nuke tool."""
        if not guild.me.guild_permissions.manage_webhooks:
            return
        try:
            for webhook in await guild.webhooks():
                try:
                    await webhook.delete(reason="WordLock: anti-nuke webhook cleanup")
                except discord.HTTPException:
                    pass
        except discord.HTTPException:
            log.debug("Could not list webhooks on guild %s", guild.id)
