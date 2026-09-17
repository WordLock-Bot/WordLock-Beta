"""Willkommens- und Verabschiedungsnachrichten für WordLock."""

from __future__ import annotations

import datetime
import logging
from typing import Dict, Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("wordlock.welcome")

GREEN = 0x57F287
RED = 0xED4245

TYPE_CHOICES = [
    app_commands.Choice(name="Willkommen", value="welcome"),
    app_commands.Choice(name="Verabschiedung", value="leave"),
]


def manage_guild() -> app_commands.Check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            raise app_commands.NoPrivateMessage()
        server = await interaction.client.db.get_server(interaction.guild_id)
        if server and server.get("status") == "disabled":
            raise app_commands.CheckFailure("wordlock_disabled")
        user = interaction.user
        if user.id in interaction.client.owner_ids:
            return True
        if isinstance(user, discord.Member) and user.guild_permissions.manage_guild:
            return True
        raise app_commands.CheckFailure("Du benötigst die Berechtigung **Server verwalten**.")

    return app_commands.check(predicate)


class WelcomeEvents(commands.Cog, name="WelcomeEvents"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # Listener
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self._send_greeting(member, "welcome")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self._send_greeting(member, "leave")

    # ------------------------------------------------------------------
    # Befehle
    # ------------------------------------------------------------------

    greeting = app_commands.Group(
        name="greeting", description="Willkommens- und Verabschiedungsnachrichten"
    )

    @greeting.command(name="setup", description="Legt die Willkommens- oder Verabschiedungsnachricht fest")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(typ=TYPE_CHOICES)
    @app_commands.describe(
        typ="Art der Nachricht (Willkommen oder Verabschiedung)",
        kanal="Kanal, in dem die Nachricht gesendet wird",
        nachricht="Nachrichtentext ({user}, {mention}, {guild}, {count}, {date}, {time})",
    )
    async def greeting_setup(
        self,
        interaction: discord.Interaction,
        typ: Literal["welcome", "leave"],
        kanal: discord.TextChannel,
        nachricht: str,
    ) -> None:
        key_channel = "welcome_channel_id" if typ == "welcome" else "leave_channel_id"
        key_message = "welcome_message" if typ == "welcome" else "leave_message"
        try:
            await self.bot.db.update_server(
                interaction.guild_id,
                **{key_channel: kanal.id, key_message: nachricht},
            )
        except Exception:
            log.exception("Could not save greeting config (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "Die Nachricht konnte nicht gespeichert werden.", ephemeral=True
            )
            return

        preview = self._render(nachricht, **self._fields(interaction.user))
        embed = discord.Embed(
            title="Willkommensnachricht gespeichert"
            if typ == "welcome"
            else "Verabschiedungsnachricht gespeichert",
            description=f"Kanal: {kanal.mention}\n\n**Vorschau:**\n{preview}",
            color=GREEN if typ == "welcome" else RED,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @greeting.command(name="test", description="Sendet die eingerichtete Nachricht jetzt als Test")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(typ=TYPE_CHOICES)
    @app_commands.describe(typ="Art der Nachricht (Willkommen oder Verabschiedung)")
    async def greeting_test(
        self,
        interaction: discord.Interaction,
        typ: Literal["welcome", "leave"],
    ) -> None:
        try:
            server = await self.bot.db.get_server(interaction.guild_id)
        except Exception:
            log.exception("Could not load server (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "Die Konfiguration konnte nicht geladen werden.", ephemeral=True
            )
            return
        if not server:
            await interaction.response.send_message(
                "Die Nachricht ist noch nicht eingerichtet. Nutze zuerst `/greeting setup`.",
                ephemeral=True,
            )
            return

        embed = self._build_embed(server, interaction.user, typ)
        if embed is None:
            await interaction.response.send_message(
                "Die Nachricht ist noch nicht eingerichtet. Nutze zuerst `/greeting setup`.",
                ephemeral=True,
            )
            return

        channel_id = server.get(
            "welcome_channel_id" if typ == "welcome" else "leave_channel_id"
        )
        channel = interaction.guild and interaction.guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Der konfigurierte Kanal wurde nicht gefunden.", ephemeral=True
            )
            return

        try:
            await channel.send(embed=embed)
        except Exception:
            log.exception("Could not send test greeting (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "Die Testnachricht konnte nicht gesendet werden.", ephemeral=True
            )
            return

        confirm = discord.Embed(
            title="Testnachricht gesendet",
            description=f"Die Nachricht wurde in {channel.mention} gesendet.",
            color=GREEN,
        )
        await interaction.response.send_message(embed=confirm, ephemeral=True)

    @greeting.command(name="disable", description="Deaktiviert die Willkommens- oder Verabschiedungsnachricht")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(typ=TYPE_CHOICES)
    @app_commands.describe(typ="Art der Nachricht (Willkommen oder Verabschiedung)")
    async def greeting_disable(
        self,
        interaction: discord.Interaction,
        typ: Literal["welcome", "leave"],
    ) -> None:
        key_channel = "welcome_channel_id" if typ == "welcome" else "leave_channel_id"
        try:
            await self.bot.db.update_server(interaction.guild_id, **{key_channel: None})
        except Exception:
            log.exception("Could not disable greeting (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "Die Nachricht konnte nicht deaktiviert werden.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Nachricht deaktiviert",
            description="Die Willkommensnachricht wurde deaktiviert."
            if typ == "welcome"
            else "Die Verabschiedungsnachricht wurde deaktiviert.",
            color=GREEN,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # Helfer
    # ------------------------------------------------------------------

    async def _send_greeting(self, member: discord.Member, kind: str) -> None:
        try:
            server = await self.bot.db.get_server(member.guild.id)
        except Exception:
            log.debug("Could not load server (guild %s)", member.guild.id, exc_info=True)
            return
        if not server:
            return

        embed = self._build_embed(server, member, kind)
        if embed is None:
            return

        channel_id = server.get(
            "welcome_channel_id" if kind == "welcome" else "leave_channel_id"
        )
        channel = member.guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            await channel.send(embed=embed)
        except Exception:
            log.debug("Could not send %s message (guild %s)", kind, member.guild.id, exc_info=True)

    def _build_embed(
        self, server: dict, user: discord.User, kind: str
    ) -> Optional[discord.Embed]:
        if kind == "welcome":
            message = server.get("welcome_message")
            title = "Willkommen"
            color = GREEN
        else:
            message = server.get("leave_message")
            title = "Auf Wiedersehen"
            color = RED
        if not message:
            return None
        embed = discord.Embed(
            title=title,
            description=self._render(message, **self._fields(user)),
            color=color,
        )
        embed.set_footer(text="WordLock")
        return embed

    def _fields(self, user: discord.User) -> Dict[str, str]:
        name = getattr(user, "display_name", None) or user.name
        guild = getattr(user, "guild", None)
        now = datetime.datetime.now()
        return {
            "user": name or "nutzer",
            "mention": user.mention,
            "guild": guild.name if guild else "",
            "count": str(getattr(guild, "member_count", 0) or 0),
            "date": now.strftime("%d.%m.%Y"),
            "time": now.strftime("%H:%M"),
        }

    def _render(self, text: str, **fields: str) -> str:
        for key, value in fields.items():
            text = text.replace("{" + key + "}", str(value))
        return text


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeEvents(bot))