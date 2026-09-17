"""WordLock Discord bot entry point."""

from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord.ext import commands

from .database import Database
from .filter_manager import FilterManager
from .version import __version__

log = logging.getLogger("wordlock.bot")

ACTIVITY_URL = os.environ.get("BOT_ACTIVITY_URL", "wordlockbot.vercel.app")


class WordLockBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.members = True

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.watching, name=ACTIVITY_URL
            ),
        )
        self.version = __version__
        self.db = Database()
        self.filters = FilterManager(self.db)
        self.owner_ids = {
            int(i) for i in os.environ.get("BOT_OWNER_IDS", "").split(",") if i.strip()
        }
        self.start_time: float | None = None
        self.ticket_views: dict = {}
        self.ticket_action_views: dict = {}
        self.verify_views: dict = {}

    async def setup_hook(self) -> None:
        await self.db.connect()
        from .commands.filter_commands import FilterCommands
        from .commands.settings_commands import SettingsCommands
        from .commands.ticket_commands import TicketCommands, register_ticket_views
        from .commands.verify_commands import VerifyCommands, register_verify_views
        from .events.message_events import MessageEvents
        from .events.protection import ProtectionEvents
        from .events.security import DISABLED_MSG, SecurityEvents

        await self.add_cog(FilterCommands(self))
        await self.add_cog(SettingsCommands(self))
        await self.add_cog(TicketCommands(self))
        await register_ticket_views(self)
        await self.add_cog(VerifyCommands(self))
        await register_verify_views(self)

        from .commands.phishing_commands import PhishingCommands
        from .commands.scheduled_messages import ScheduledMessages
        from .events.welcome_events import WelcomeEvents
        from .events.invite_tracker import InviteTracker

        await self.add_cog(WelcomeEvents(self))
        await self.add_cog(InviteTracker(self))
        await self.add_cog(PhishingCommands(self))
        await self.add_cog(ScheduledMessages(self))

        from .commands.webhooksay_commands import WebhookSayCommands

        await self.add_cog(WebhookSayCommands(self))

        message_events = MessageEvents(self)
        await self.add_cog(message_events)
        await self.add_cog(SecurityEvents(self))
        await self.add_cog(ProtectionEvents(self))

        @self.tree.error
        async def on_app_command_error(
            interaction: discord.Interaction,
            error: discord.app_commands.AppCommandError,
        ) -> None:
            if isinstance(error, discord.app_commands.CheckFailure):
                if not interaction.response.is_done():
                    try:
                        msg = (
                            DISABLED_MSG
                            if str(error) == "wordlock_disabled"
                            else (str(error) or "You don't have permission to use this command.")
                        )
                        await interaction.response.send_message(msg, ephemeral=True)
                    except Exception:
                        pass
                return
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        "An internal error occurred.", ephemeral=True
                    )
                except Exception:
                    pass
            log.exception("App command error in %s", interaction.command)

        self.loop.create_task(self._presence_loop())
        self.loop.create_task(self._heartbeat_loop())
        self.loop.create_task(self._announce_loop())
        self.loop.create_task(message_events._perms_loop())
        await self.tree.sync()
        log.info("Commands synced")

    async def _presence_loop(self) -> None:
        """Keep the activity set to ACTIVITY_URL at all times."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                await self.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.watching, name=ACTIVITY_URL
                    )
                )
            except Exception:
                log.exception("Could not update presence")
            await asyncio.sleep(600)

    async def _heartbeat_loop(self) -> None:
        """Report bot liveness to the API database."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                await self.db.update_heartbeat()
            except Exception:
                log.exception("Could not update heartbeat")
            await asyncio.sleep(30)

    async def _announce_loop(self) -> None:
        """Post new updates (announced in the admin panel) to every active server."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                await self._announce_pending_updates()
            except Exception:
                log.exception("Update announce loop failed")
            await asyncio.sleep(20)

    async def _announce_pending_updates(self) -> None:
        updates = await self.db.unannounced_updates()
        if not updates:
            return
        servers = await self.db.active_servers_for_announce()
        for update in updates:
            for server in servers:
                await self._announce_to_server(server, update)
                await asyncio.sleep(0.5)
            await self.db.mark_update_announced(update["id"])
            log.info("Announced update %s to %d servers", update["version"], len(servers))

    def _resolve_announce_channel(self, guild: discord.Guild, server: dict):
        """Pick the best channel for announcements.

        Priority: configured log channel (if it resolves to a text channel the
        bot can see) -> guild system channel -> first text channel the bot has
        permission to write to. Returns (channel, source) or (None, reason).
        """
        log_channel_id = server.get("log_channel_id")
        if log_channel_id:
            channel = self.get_channel(int(log_channel_id))
            if channel is not None and isinstance(channel, discord.TextChannel):
                return channel, "log_channel"
            log.warning(
                "Announce: configured log channel %s for guild %s is invalid/not visible, "
                "falling back",
                log_channel_id,
                guild.id,
            )
        if guild.system_channel is not None:
            return guild.system_channel, "system_channel"
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                return ch, "first_text_channel"
        return None, "no_sendable_channel"

    async def _announce_to_server(self, server: dict, update: dict) -> None:
        guild = self.get_guild(int(server["guild_id"]))
        if guild is None:
            log.warning(
                "Announce: bot is not in guild %s, skipping", server["guild_id"]
            )
            return
        channel, source = self._resolve_announce_channel(guild, server)
        if channel is None:
            log.warning(
                "Announce: no usable channel for guild %s (%s)",
                server["guild_id"],
                source,
            )
            return
        log.info(
            "Announce: sending to guild %s channel #%s (%s)",
            server["guild_id"],
            getattr(channel, "name", channel.id),
            source,
        )
        lang = "de" if server.get("language") == "de" else "en"
        is_release = update.get("kind") == "release"
        text = {
            "de": {
                "announce_title": f"📢 Ankündigung – WordLock Update {update['version']}",
                "release_title": f"🚀 WordLock {update['version']} ist jetzt verfügbar!",
                "changelog": "Änderungen",
                "maintenance": "⚠️ Wartungsmodus ist aktiv",
            },
            "en": {
                "announce_title": f"📢 Announcement – WordLock Update {update['version']}",
                "release_title": f"🚀 WordLock {update['version']} is now available!",
                "changelog": "Changes",
                "maintenance": "⚠️ Maintenance mode is active",
            },
        }[lang]
        embed = discord.Embed(
            title=text["release_title" if is_release else "announce_title"],
            description=update["title"],
            color=0x57F287 if is_release else 0x5865F2,
        )
        if update.get("changelog"):
            embed.add_field(name=text["changelog"], value=update["changelog"][:1024], inline=False)
        if update.get("maintenance_mode"):
            embed.add_field(name="", value=text["maintenance"], inline=False)
        embed.set_footer(text="Made by DevCoder")
        try:
            message = await channel.send(embed=embed)
            if getattr(channel, "is_news", lambda: False)():
                try:
                    await message.publish()
                    log.info(
                        "Announce: published in guild %s channel #%s",
                        server["guild_id"],
                        getattr(channel, "name", channel.id),
                    )
                except discord.Forbidden:
                    log.warning(
                        "Announce: no permission to publish in channel %s (need Manage Messages)",
                        getattr(channel, "id", None),
                    )
                except discord.HTTPException as exc:
                    log.warning(
                        "Announce: could not publish message in channel %s: %s",
                        getattr(channel, "id", None),
                        exc,
                    )
        except Exception:
            log.exception(
                "Could not announce update to server %s (channel %s)",
                server["guild_id"],
                getattr(channel, "id", None),
            )

    async def on_ready(self) -> None:
        self.start_time = asyncio.get_event_loop().time()
        log.info("Logged in as %s (v%s)", self.user, self.version)
        log.info(
            "DIAGNOSTIC: Message Content Intent = %s | in %d guild(s)",
            bool(self.intents.message_content),
            len(self.guilds),
        )
        log.info(
            "DIAGNOSTIC: filter is ACTIVE. Standard + custom words are matched. "
            "NOTE: server owners and admins are intentionally NEVER filtered — "
            "test with a normal member account."
        )
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name=ACTIVITY_URL
            )
        )
        for guild in self.guilds:
            try:
                server = await self.db.get_server(guild.id)
                inviter_id = None
                if server and server.get("inviter_id"):
                    inviter_id = server["inviter_id"]
                else:
                    inviter_id = await self._resolve_inviter(guild)
                await self.db.upsert_server(
                    guild_id=guild.id,
                    name=guild.name,
                    owner_id=guild.owner_id,
                    member_count=guild.member_count,
                    bot_version=self.version,
                    inviter_id=inviter_id,
                )
            except Exception:
                log.exception("Could not upsert guild %s", guild.id)

    async def _resolve_inviter(self, guild: discord.Guild) -> Optional[int]:
        """Find the user who invited the bot via the guild audit log."""
        try:
            if not self.user:
                return None
            async for entry in guild.audit_logs(
                limit=5, action=discord.AuditLogAction.bot_add
            ):
                if entry.target and entry.target.id == self.user.id:
                    if entry.user:
                        return entry.user.id
                    break
        except (discord.Forbidden, discord.HTTPException):
            log.debug("Could not read audit log for guild %s", guild.id)
        return None


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
    bot = WordLockBot()
    bot.run(token)


if __name__ == "__main__":
    main()
