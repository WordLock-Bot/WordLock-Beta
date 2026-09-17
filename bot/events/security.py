"""Self-protection / anti-nuke security for the bot.

If an attack, manipulation or nuke attempt is detected on a server, the bot
disables itself for that server (stops processing input), writes an incident,
sends the attempt + consequence to the log channel (and the bot owners via DM),
and waits for an admin to re-enable it from the dashboard.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Deque, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..version import __version__

log = logging.getLogger("wordlock.bot.security")

# Detection thresholds (per guild, per window).
COMMAND_FLOOD_LIMIT = 5       # slash commands within …
COMMAND_FLOOD_WINDOW = 10     # seconds
MENTION_FLOOD_LIMIT = 8       # mentions of the bot within …
MENTION_FLOOD_WINDOW = 10     # seconds
CHANNEL_NUKE_LIMIT = 6        # channel create/delete events within …
CHANNEL_NUKE_WINDOW = 15      # seconds

INCIDENT_LABELS: Dict[str, str] = {
    "command_flood": "Command flood (possible manipulation attempt)",
    "mention_flood": "Mention flood against the bot",
    "channel_nuke": "Mass channel creation/deletion (nuke attempt)",
    "bot_banned": "Bot was banned",
    "bot_removed": "Bot was removed from the server",
}

DISABLED_MSG = (
    "🛡️ WordLock is disabled for this server (self-protection). "
    "Please re-enable it in the dashboard."
)


def guild_active() -> app_commands.Check:
    """Global slash-command check: refuse input while the bot is disabled."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return True
        try:
            server = await interaction.client.db.get_server(interaction.guild_id)
        except Exception:
            return True
        if server and server.get("status") == "disabled":
            raise app_commands.CheckFailure("wordlock_disabled")
        return True

    return app_commands.check(predicate)


class SecurityEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._commands: Dict[int, Deque[float]] = {}
        self._mentions: Dict[int, Deque[float]] = {}
        self._channels: Dict[int, Deque[float]] = {}

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _count(
        self,
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

    def _reset(self, guild_id: int) -> None:
        self._commands.pop(guild_id, None)
        self._mentions.pop(guild_id, None)
        self._channels.pop(guild_id, None)

    async def _server_disabled(self, guild_id: int) -> bool:
        try:
            server = await self.bot.db.get_server(guild_id)
        except Exception:
            return False
        return bool(server and server.get("status") == "disabled")

    # ------------------------------------------------------------------
    # Incident handling
    # ------------------------------------------------------------------

    async def _handle_incident(
        self,
        guild: discord.Guild,
        kind: str,
        actor_id: Optional[int] = None,
        detail: Optional[Dict[str, Any]] = None,
        disable: bool = True,
    ) -> None:
        if await self._server_disabled(guild.id):
            self._reset(guild.id)
            return

        consequence = (
            "WordLock disabled itself for this server (self-protection). "
            "Message and command processing was stopped. "
            "An administrator must re-enable the bot via the dashboard."
        )

        if disable:
            await self.bot.db.update_server(guild.id, status="disabled")
            await self.bot.filters.invalidate(guild.id)

        await self.bot.db.add_incident(
            guild_id=guild.id,
            kind=kind,
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
        await self._send_alert(guild, kind, actor_id, detail or {}, consequence)
        self._reset(guild.id)
        log.warning("Self-protection triggered on guild %s: %s", guild.id, kind)

    async def _send_alert(
        self,
        guild: discord.Guild,
        kind: str,
        actor_id: Optional[int],
        detail: Dict[str, Any],
        consequence: str,
    ) -> None:
        embed = discord.Embed(
            title="⚠️ Security alert – Nuke/Manipulation attempt",
            description=(
                f"**What was attempted:** {INCIDENT_LABELS.get(kind, kind)}\n"
                f"**Server:** {guild.name} ({guild.id})"
            ),
            color=0xFF0000,
        )
        if actor_id:
            embed.add_field(name="Affected", value=f"User-ID: {actor_id}")
        for key, value in detail.items():
            embed.add_field(
                name=str(key).replace("_", " ").capitalize(),
                value=str(value)[:1000] or "—",
                inline=True,
            )
        embed.add_field(name="Consequence", value=consequence, inline=False)
        embed.set_footer(text=f"WordLock v{__version__} • Self-protection active")

        channel: Optional[discord.TextChannel] = None
        try:
            server = await self.bot.db.get_server(guild.id)
            if server:
                channel = guild.get_channel(server.get("log_channel_id"))
                if not isinstance(channel, discord.TextChannel):
                    channel = next(
                        (
                            c
                            for c in guild.text_channels
                            if c.permissions_for(guild.me).send_messages
                        ),
                        None,
                    )
            if isinstance(channel, discord.TextChannel):
                await channel.send(embed=embed)
        except Exception:
            log.exception("Could not send security alert to channel")

        for owner_id in self.bot.owner_ids:
            try:
                owner = await self.bot.fetch_user(owner_id)
                await owner.send(embed=embed)
            except Exception:
                log.debug("Could not DM owner %s", owner_id)

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild or not message.content:
            return
        if not self.bot.user:
            return
        is_mention = self.bot.user in message.mentions or message.content.startswith(
            self.bot.user.mention
        )
        if not is_mention:
            return
        now = asyncio.get_event_loop().time()
        if self._count(
            self._mentions, message.guild.id, now, MENTION_FLOOD_WINDOW, MENTION_FLOOD_LIMIT
        ):
            await self._handle_incident(
                message.guild,
                "mention_flood",
                actor_id=message.author.id,
                detail={"count": len(self._mentions[message.guild.id])},
            )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        await self._channel_event(channel)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        await self._channel_event(channel)

    async def _channel_event(self, channel: discord.abc.GuildChannel) -> None:
        guild = getattr(channel, "guild", None)
        if not guild:
            return
        now = asyncio.get_event_loop().time()
        if self._count(
            self._channels, guild.id, now, CHANNEL_NUKE_WINDOW, CHANNEL_NUKE_LIMIT
        ):
            await self._handle_incident(
                guild,
                "channel_nuke",
                detail={
                    "events": len(self._channels[guild.id]),
                    "window_seconds": CHANNEL_NUKE_WINDOW,
                },
            )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        if self.bot.user and user.id == self.bot.user.id:
            await self._handle_incident(guild, "bot_banned", actor_id=user.id, disable=False)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        # The bot is already gone; record the incident for the dashboard/owners.
        await self._handle_incident(guild, "bot_removed", disable=False)
        await self.bot.db.delete_server(guild.id)
        await self.bot.filters.invalidate(guild.id)
