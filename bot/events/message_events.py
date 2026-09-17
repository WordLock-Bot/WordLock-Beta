"""Message filtering events (on_message / on_message_edit)."""

from __future__ import annotations

import asyncio
import datetime
import logging

import discord
from discord.ext import commands

from ..phishing_checker import check as check_phishing
from ..version import __version__

log = logging.getLogger("wordlock.bot.events")

ACTION_LABELS = {
    "delete": "Message deleted",
    "warn": "Warning",
    "timeout": "Timeout",
    "log": "Logged only",
}

COLORS = {
    "insult": 0xED4245,
    "profanity": 0xED4245,
    "slur": 0xFF0000,
    "sexual": 0xEB459E,
    "threat": 0x992D22,
    "spam": 0xFEE75C,
    "custom": 0x5865F2,
}


class MessageEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._process(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.content != after.content:
            await self._process(after)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        inviter_id = await self._resolve_inviter(guild)
        await self.bot.db.upsert_server(
            guild_id=guild.id,
            name=guild.name,
            owner_id=guild.owner_id,
            member_count=guild.member_count,
            bot_version=self.bot.version,
            inviter_id=inviter_id,
        )
        await self.bot.db.record_guild_join(guild.id, guild.name)
        await self.bot.db.bump_stat("servers_joined", 1)
        await self._check_bot_permissions(guild)
        log.info("Joined guild %s (%s)", guild.name, guild.id)

    async def _resolve_inviter(self, guild: discord.Guild) -> Optional[int]:
        """Find the user who invited the bot via the guild audit log.

        Discord records a `bot_add` audit entry pointing at the bot user; the
        entry author is the inviter. Returns None if it cannot be determined
        (e.g. audit log access missing)."""
        try:
            if not self.bot.user:
                return None
            async for entry in guild.audit_logs(
                limit=5, action=discord.AuditLogAction.bot_add
            ):
                if entry.target and entry.target.id == self.bot.user.id:
                    if entry.user:
                        return entry.user.id
                    break
        except (discord.Forbidden, discord.HTTPException):
            log.debug("Could not read audit log for guild %s", guild.id)
        return None

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await self.bot.db.record_guild_leave(guild.id)
        await self.bot.db.delete_server(guild.id)
        await self.bot.filters.invalidate(guild.id)
        log.info("Left guild %s (%s)", guild.name, guild.id)

    async def _perms_loop(self) -> None:
        """Periodically re-check the bot's Administrator permission in every
        active guild so a later permission removal is also detected."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                for guild in self.bot.guilds:
                    try:
                        await self._check_bot_permissions(guild)
                    except Exception:
                        log.exception("Perm check failed for guild %s", guild.id)
            except Exception:
                log.exception("Perm loop iteration failed")
            await asyncio.sleep(600)

    async def _check_bot_permissions(self, guild: discord.Guild) -> None:
        """Verify the bot still has the Administrator permission.

        If it was removed (e.g. deselected at invite), flag the server in the
        database (shown as a warning in the dashboard) and post one notice in
        a guild channel. No DM is sent to admins. Only posts once per state
        change so it does not spam on the periodic check.
        """
        if guild.me is None:
            return
        has_admin = bool(guild.me.guild_permissions.administrator)
        server = await self.bot.db.get_server(guild.id)
        if not server:
            return
        previously_ok = bool(server.get("admin_ok", True))
        if has_admin == previously_ok:
            return
        await self.bot.db.update_server(guild.id, admin_ok=has_admin)
        if has_admin:
            log.info("Guild %s: Administrator permission restored", guild.id)
            return

        log.warning(
            "Guild %s: bot has no Administrator permission, flagging server",
            guild.id,
        )
        channel = self._notice_channel(guild)
        if channel is None:
            return
        lang = "de" if server.get("language") == "de" else "en"
        text = {
            "de": (
                "⚠️ **WordLock hat nicht die Administrator-Berechtigung!**\n"
                "Ohne diese Berechtigung kann der Filter Nachrichten nicht zuverlässig "
                "löschen, verwarnen oder zeitweilig stummschalten. Bitte den Bot mit "
                "der Administrator-Berechtigung neu einladen."
            ),
            "en": (
                "⚠️ **WordLock is missing the Administrator permission!**\n"
                "Without it the filter cannot reliably delete, warn or timeout messages. "
                "Please re-invite the bot with the Administrator permission."
            ),
        }[lang]
        try:
            await channel.send(text)
        except discord.HTTPException:
            log.debug("Could not post permission notice in %s", channel.id)

    def _notice_channel(self, guild: discord.Guild):
        if guild.system_channel is not None and guild.system_channel.permissions_for(
            guild.me
        ).send_messages:
            return guild.system_channel
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                return ch
        return None

    async def _process(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not message.guild:
            return
        if not message.content:
            log.warning(
                "Guild %s: empty content for author %s — if this is a real message, "
                "the Message Content Intent is OFF in the Discord Developer Portal "
                "(or the author is a webhook/bot).",
                message.guild.id,
                message.author.id,
            )
            return

        server = await self.bot.db.get_server(message.guild.id)
        if not server:
            log.debug("Guild %s: no server row, filtering skipped", message.guild.id)
            return
        if server.get("status") != "active":
            log.debug(
                "Guild %s: status=%r, filtering skipped",
                message.guild.id,
                server.get("status"),
            )
            return

        if await self._is_bypassed(message, server):
            return

        if await self._check_phishing(message, server):
            return

        try:
            engine = await self.bot.filters.get_or_load(message.guild.id)
        except Exception:
            log.exception("Filter build failed for guild %s", message.guild.id)
            return

        result = engine.check(message.content)
        if result is None:
            return

        _, _, _, entry = result
        mod_level = server.get("mod_level") or 3
        actions = self._resolve_actions(entry, server)
        # Words below the moderation level are only logged if no action was
        # explicitly configured (per-word override or server action settings).
        explicit = bool(entry.action) or any(
            server.get(k)
            for k in ("action_delete", "action_warn", "action_timeout", "action_log")
        )
        if entry.severity < mod_level and not explicit:
            actions = ["log"]

        log.info(
            "Guild %s: violation word=%r category=%s severity=%s mod_level=%s actions=%s "
            "perms_manage_messages=%s perms_moderate=%s",
            message.guild.id,
            entry.word,
            entry.category,
            entry.severity,
            mod_level,
            actions,
            bool(message.guild.me.guild_permissions.manage_messages),
            bool(message.guild.me.guild_permissions.moderate_members),
        )

        await self.bot.db.log_violation(
            guild_id=message.guild.id,
            user_id=message.author.id,
            message_text=message.content[:1500],
            matched_word=entry.word,
            category=entry.category,
            severity=entry.severity,
            action=",".join(actions) or "log",
        )

        executed: list[str] = []
        member = message.guild.get_member(message.author.id)
        for action in actions:
            if action == "delete" and message.guild.me.guild_permissions.manage_messages:
                try:
                    await message.delete()
                    executed.append("delete")
                except discord.HTTPException:
                    log.debug("Could not delete message %s", message.id)
            elif action == "warn":
                await self.bot.db.add_warning(
                    message.guild.id, message.author.id,
                    reason=f"Filter: {entry.word} ({entry.category})",
                    moderator=self.bot.user.id if self.bot.user else None,
                )
                executed.append("warn")
                await self._dm_warning(message.author, entry)
            elif action == "timeout" and member is not None:
                timeout_ok = (
                    message.guild.me.guild_permissions.moderate_members
                    and message.guild.me.top_role > member.top_role
                )
                if timeout_ok:
                    try:
                        minutes = server.get("timeout_minutes") or 60
                        await member.timeout(
                            discord.utils.utcnow()
                            + datetime.timedelta(minutes=minutes),
                            reason=f"WordLock: {entry.word} ({entry.category})",
                        )
                        executed.append("timeout")
                    except discord.HTTPException:
                        log.debug("Could not timeout %s", member.id)
            elif action == "log":
                executed.append("log")

        if server.get("log_channel_id") and (
            "log" in actions or server.get("action_log")
        ):
            await self._send_log_embed(message, entry, executed)

    def _resolve_actions(self, entry, server: dict) -> list[str]:
        """Per-word action override wins, server defaults otherwise.

        For standard (default-list) words without an explicit per-word
        override, the server's ``std_word_action`` is used as the default
        punishment (default: delete). If that is not configured, the granular
        server action toggles are used as a fallback.
        """
        if entry.action:
            return [entry.action]
        std_action = server.get("std_word_action")
        if std_action:
            actions = [std_action]
            if server.get("action_log"):
                actions.append("log")
            return actions
        actions: list[str] = []
        if server.get("action_delete"):
            actions.append("delete")
        if server.get("action_warn"):
            actions.append("warn")
        if server.get("action_timeout"):
            actions.append("timeout")
        if server.get("action_log") or not actions:
            actions.append("log")
        return actions

    async def _is_bypassed(self, message: discord.Message, server: dict) -> bool:
        """Server-side bypass.

        Owners and administrators are filtered by default. The only exception
        is the per-server "cheat" flag ``bypass_privileged`` (set in the admin
        panel for a specific server), which stops the filter from touching
        owners/admins on that server. Individual users and roles can still be
        whitelisted via ``bypass_users`` / ``bypass_roles``.
        """
        member = message.guild.get_member(message.author.id)
        if member is None:
            return False
        if server.get("bypass_privileged"):
            if member.id == message.guild.owner_id:
                log.info(
                    "Guild %s: message from server OWNER skipped "
                    "(bypass_privileged cheat enabled).",
                    message.guild.id,
                )
                return True
            if member.guild_permissions.administrator:
                log.info(
                    "Guild %s: message from ADMIN skipped "
                    "(bypass_privileged cheat enabled).",
                    message.guild.id,
                )
                return True
        try:
            bypass_users = server.get("bypass_users") or []
            if isinstance(bypass_users, str):
                import json

                bypass_users = json.loads(bypass_users)
            if message.author.id in {int(u) for u in bypass_users}:
                return True
            bypass_roles = server.get("bypass_roles") or []
            if isinstance(bypass_roles, str):
                import json

                bypass_roles = json.loads(bypass_roles)
            if {r.id for r in member.roles} & {int(r) for r in bypass_roles}:
                return True
        except Exception:
            log.exception("Bypass check failed for guild %s", message.guild.id)
        return False

    async def _dm_warning(self, author: discord.User, entry) -> None:
        try:
            embed = discord.Embed(
                title="WordLock",
                description=(
                    f"Your message on a server was filtered by WordLock. "
                    f"Detected: `{entry.word}` (category: {entry.category})."
                ),
                color=0xED4245,
            )
            await author.send(embed=embed)
        except (discord.HTTPException, discord.Forbidden):
            pass

    async def _check_phishing(
        self, message: discord.Message, server: dict
    ) -> bool:
        if not server.get("phishing_enabled") or not message.content:
            return False

        try:
            block = set(
                await self.bot.db.get_phishing_domains(message.guild.id, "block")
            )
            allow = set(
                await self.bot.db.get_phishing_domains(message.guild.id, "allow")
            )
            result = check_phishing(message.content, block, allow)
        except Exception:
            log.exception("Phishing check failed (guild %s)", message.guild.id)
            return False

        if result is None:
            return False

        action = server.get("phishing_action") or "delete"
        executed: list[str] = []
        member = message.guild.get_member(message.author.id)

        if action == "delete" and message.guild.me.guild_permissions.manage_messages:
            try:
                await message.delete()
                executed.append("delete")
            except discord.HTTPException:
                log.debug("Could not delete phishing message %s", message.id)
        elif action == "warn":
            try:
                await self.bot.db.add_warning(
                    message.guild.id,
                    message.author.id,
                    reason=f"Phishing: {result.domain}",
                    moderator=self.bot.user.id if self.bot.user else None,
                )
                executed.append("warn")
            except Exception:
                log.exception("Could not add phishing warning (guild %s)", message.guild.id)
            await self._dm_phishing_warning(message.author, result.domain)
        elif action == "timeout" and member is not None:
            timeout_ok = (
                message.guild.me.guild_permissions.moderate_members
                and message.guild.me.top_role > member.top_role
            )
            if timeout_ok:
                try:
                    minutes = server.get("timeout_minutes") or 60
                    await member.timeout(
                        discord.utils.utcnow() + datetime.timedelta(minutes=minutes),
                        reason=f"WordLock: Phishing ({result.domain})",
                    )
                    executed.append("timeout")
                except discord.HTTPException:
                    log.debug("Could not timeout %s due to phishing", member.id)
        elif action == "log":
            executed.append("log")

        try:
            await self.bot.db.log_violation(
                guild_id=message.guild.id,
                user_id=message.author.id,
                message_text=message.content[:1500],
                matched_word=result.domain,
                category="phishing",
                severity=5,
                action=",".join(executed) or "log",
            )
        except Exception:
            log.exception("Could not log phishing violation (guild %s)", message.guild.id)

        if server.get("log_channel_id"):
            await self._send_phishing_log(message, result, executed)

        log.info(
            "Guild %s: phishing blocked domain=%s reason=%r action=%s",
            message.guild.id,
            result.domain,
            result.reason,
            action,
        )
        return True

    async def _dm_phishing_warning(
        self, author: discord.User, domain: str
    ) -> None:
        try:
            embed = discord.Embed(
                title="WordLock",
                description=(
                    f"Deine Nachricht wurde von WordLock blockiert, weil sie einen "
                    f"verdächtigen Link enthielt.\nDetektierte Domain: `{domain}`"
                ),
                color=0xED4245,
            )
            await author.send(embed=embed)
        except (discord.HTTPException, discord.Forbidden):
            pass

    async def _send_phishing_log(
        self, message: discord.Message, result, executed: list[str]
    ) -> None:
        server = await self.bot.db.get_server(message.guild.id)
        if not server:
            return
        channel = message.guild.get_channel(server.get("log_channel_id"))
        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title="Phishing-Link blockiert",
            description=(
                f"**Domain:** `{result.domain}`\n"
                f"**Grund:** {result.reason}\n"
                f"**Aktion:** {', '.join(executed) or '—'}"
            ),
            color=0x992D22,
        )
        embed.set_author(
            name=str(message.author), icon_url=message.author.display_avatar.url
        )
        embed.add_field(
            name="Nachricht",
            value=(message.content[:1000] or "*kein Text*"),
            inline=False,
        )
        embed.set_footer(
            text=f"WordLock v{__version__} • Benutzer-ID: {message.author.id}"
        )
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            log.debug("Could not send phishing log embed in %s", channel.id)

    async def _send_log_embed(
        self, message: discord.Message, entry, executed: list[str]
    ) -> None:
        server = await self.bot.db.get_server(message.guild.id)
        if not server:
            return
        channel = message.guild.get_channel(server.get("log_channel_id"))
        if not isinstance(channel, discord.TextChannel):
            return

        color = COLORS.get(entry.category, 0x5865F2)
        embed = discord.Embed(
            title="Filter violation",
            description=f"**Word:** `{entry.word}`\n**Category:** {entry.category}\n"
            f"**Severity:** {entry.severity}/5\n**Actions:** {', '.join(executed) or '—'}",
            color=color,
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(
            name="Message",
            value=(message.content[:1000] or "*no text*"),
            inline=False,
        )
        embed.set_footer(text=f"WordLock v{__version__} • User ID: {message.author.id}")
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            log.debug("Could not send log embed in %s", channel.id)
