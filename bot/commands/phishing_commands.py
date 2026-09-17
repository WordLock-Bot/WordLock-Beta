"""Phishing-Link-Schutz für WordLock."""

from __future__ import annotations

import logging
from typing import Dict, List, Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("wordlock.phishing")

GREEN = 0x57F287
RED = 0xED4245

ACTION_CHOICES = [
    app_commands.Choice(name="Delete", value="delete"),
    app_commands.Choice(name="Warn", value="warn"),
    app_commands.Choice(name="Timeout", value="timeout"),
    app_commands.Choice(name="Log only", value="log"),
]

ACTION_LABELS = {
    "delete": "Delete",
    "warn": "Warn",
    "timeout": "Timeout",
    "log": "Log only",
}


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
        raise app_commands.CheckFailure("You need the **Manage Server** permission.")

    return app_commands.check(predicate)


class PhishingCommands(commands.Cog, name="PhishingCommands"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    phishing = app_commands.Group(
        name="phishing", description="Protection against phishing links on this server"
    )

    @phishing.command(name="setup", description="Enables phishing protection")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(aktion=ACTION_CHOICES)
    @app_commands.describe(aktion="Action to take when phishing links are detected")
    async def phishing_setup(
        self,
        interaction: discord.Interaction,
        aktion: Literal["delete", "warn", "timeout", "log"] = "delete",
    ) -> None:
        try:
            await self.bot.db.update_server(
                interaction.guild_id,
                phishing_enabled=True,
                phishing_action=aktion,
            )
        except Exception:
            log.exception("Could not enable phishing protection (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "Phishing protection could not be enabled.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Phishing protection enabled",
            description=f"Action: **{ACTION_LABELS.get(aktion, aktion)}**",
            color=GREEN,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @phishing.command(name="disable", description="Disables phishing protection")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    async def phishing_disable(self, interaction: discord.Interaction) -> None:
        try:
            await self.bot.db.update_server(interaction.guild_id, phishing_enabled=False)
        except Exception:
            log.exception("Could not disable phishing protection (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "Phishing protection could not be disabled.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Phishing protection disabled",
            description="Phishing protection is now disabled.",
            color=RED,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @phishing.command(name="action", description="Sets the action for phishing links")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(aktion=ACTION_CHOICES)
    @app_commands.describe(aktion="Action to take when phishing links are detected")
    async def phishing_action(
        self,
        interaction: discord.Interaction,
        aktion: Literal["delete", "warn", "timeout", "log"],
    ) -> None:
        try:
            await self.bot.db.update_server(interaction.guild_id, phishing_action=aktion)
        except Exception:
            log.exception("Could not set phishing action (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "The action could not be saved.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Action changed",
            description=f"New action: **{ACTION_LABELS.get(aktion, aktion)}**",
            color=GREEN,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @phishing.command(name="block", description="Adds a domain to the blocklist")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(domain="Domain to be blocked (e.g. example.com)")
    async def phishing_block(self, interaction: discord.Interaction, domain: str) -> None:
        domain = domain.strip().lower().rstrip(".")
        if not domain:
            await interaction.response.send_message(
                "Please provide a valid domain.", ephemeral=True
            )
            return
        try:
            await self.bot.db.add_phishing_domain(interaction.guild_id, domain, "block")
        except Exception:
            log.exception("Could not add phishing domain (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "The domain could not be added.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Domain blocked",
            description=f"`{domain}` was added to the blocklist.",
            color=GREEN,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @phishing.command(name="unblock", description="Removes a domain from the blocklist")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(domain="Domain that should no longer be blocked")
    async def phishing_unblock(self, interaction: discord.Interaction, domain: str) -> None:
        try:
            removed = await self.bot.db.remove_phishing_domain(
                interaction.guild_id, domain, "block"
            )
        except Exception:
            log.exception("Could not remove phishing domain (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "The domain could not be removed.", ephemeral=True
            )
            return

        if removed:
            embed = discord.Embed(
                title="Domain unblocked",
                description=f"`{domain.strip().lower()}` was removed from the blocklist.",
                color=GREEN,
            )
        else:
            embed = discord.Embed(
                title="Domain not found",
                description=f"`{domain.strip().lower()}` is not on the blocklist.",
                color=RED,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @phishing.command(name="view", description="Shows the phishing protection status")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    async def phishing_view(self, interaction: discord.Interaction) -> None:
        try:
            server = await self.bot.db.get_server(interaction.guild_id)
            block = await self.bot.db.get_phishing_domains(interaction.guild_id, "block")
            allow = await self.bot.db.get_phishing_domains(interaction.guild_id, "allow")
        except Exception:
            log.exception("Could not load phishing config (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "The configuration could not be loaded.", ephemeral=True
            )
            return

        enabled = bool(server.get("phishing_enabled"))
        action = server.get("phishing_action") or "delete"
        embed = discord.Embed(
            title="Phishing Protection",
            description=f"{'🟢 **Enabled**' if enabled else '🔴 **Disabled**'}",
            color=GREEN if enabled else RED,
        )
        embed.add_field(
            name="Action",
            value=ACTION_LABELS.get(action, action),
            inline=False,
        )
        embed.add_field(
            name="Blocked domains",
            value=", ".join(f"`{d}`" for d in block) or "None",
            inline=False,
        )
        embed.add_field(
            name="Allowed domains",
            value=", ".join(f"`{d}`" for d in allow) or "None",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PhishingCommands(bot))