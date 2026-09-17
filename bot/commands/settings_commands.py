"""Slash commands to view and change server settings."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..events.security import guild_active

LANGUAGES = ["en", "de"]


def manage_guild() -> app_commands.Check:
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            raise app_commands.NoPrivateMessage()
        user = interaction.user
        if user.id in interaction.client.owner_ids:
            return True
        if isinstance(user, discord.Member) and user.guild_permissions.manage_guild:
            return True
        raise app_commands.CheckFailure(
            "You need the `Manage Guild` permission to use this command."
        )

    return app_commands.check(predicate)


class SettingsCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="settings", description="Shows the WordLock settings of this server")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @guild_active()
    async def settings(self, interaction: discord.Interaction) -> None:
        server = await self.bot.db.get_server(interaction.guild_id) or {}
        default_lists = server.get("default_lists") or {"de": True, "en": True}
        if isinstance(default_lists, str):
            import json

            default_lists = json.loads(default_lists)

        actions = [
            name
            for key, name in (
                ("action_delete", "🗑️ Delete"),
                ("action_warn", "⚠️ Warn"),
                ("action_timeout", "⏳ Timeout"),
                ("action_log", "📝 Log"),
            )
            if server.get(key)
        ]

        embed = discord.Embed(
            title="WordLock Settings",
            description=f"**Moderation level:** {server.get('mod_level', 3)}/5\n"
            f"**Language:** {server.get('language', 'en').upper()}\n"
            f"**Log channel:** {('#' + self._channel_name(interaction.guild, server.get('log_channel_id'))) if server.get('log_channel_id') else 'Not set'}\n"
            f"**Actions:** {', '.join(actions) or 'none'}\n"
            f"**Timeout duration:** {server.get('timeout_minutes', 60)} min\n"
            f"**Standard lists:** {', '.join(l.upper() for l, a in default_lists.items() if a) or 'none'}",
            color=0x5865F2,
        )
        embed.set_footer(text="Change with /settings set")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @staticmethod
    def _channel_name(guild: discord.Guild | None, channel_id) -> str:
        if not guild or not channel_id:
            return "?"
        ch = guild.get_channel(channel_id)
        return ch.name if ch else str(channel_id)

    @app_commands.command(name="settings-set", description="Changes a WordLock setting")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @guild_active()
    @app_commands.choices(
        option=[
            app_commands.Choice(name="Moderation level (1-5)", value="mod_level"),
            app_commands.Choice(name="Language", value="language"),
            app_commands.Choice(name="Timeout duration (minutes)", value="timeout_minutes"),
        ]
    )
    async def settings_set(
        self,
        interaction: discord.Interaction,
        option: app_commands.Choice[str],
        value: str,
    ) -> None:
        key = option.value
        guild_id = interaction.guild_id
        try:
            if key == "mod_level":
                v = int(value)
                if not 1 <= v <= 5:
                    raise ValueError
                await self.bot.db.update_server(guild_id, mod_level=v)
            elif key == "language":
                v = value.lower()
                if v not in LANGUAGES:
                    raise ValueError
                await self.bot.db.update_server(guild_id, language=v)
            elif key == "timeout_minutes":
                v = int(value)
                if v < 1 or v > 10080:
                    raise ValueError
                await self.bot.db.update_server(guild_id, timeout_minutes=v)
        except ValueError:
            await interaction.response.send_message(
                "Invalid value for this setting.", ephemeral=True
            )
            return
        await self.bot.filters.rebuild(guild_id)
        await interaction.response.send_message(
            f"✅ **{option.name}** set to `{value}`.", ephemeral=True
        )

    @app_commands.command(name="settings-logchannel", description="Sets the log channel")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @guild_active()
    async def settings_logchannel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        await self.bot.db.update_server(interaction.guild_id, log_channel_id=channel.id)
        await interaction.response.send_message(
            f"✅ Log channel set to {channel.mention}.", ephemeral=True
        )

    @app_commands.command(name="settings-actions", description="Toggles actions on/off")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @guild_active()
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Delete message", value="action_delete"),
            app_commands.Choice(name="Warn user", value="action_warn"),
            app_commands.Choice(name="Timeout", value="action_timeout"),
            app_commands.Choice(name="Log only", value="action_log"),
        ]
    )
    async def settings_actions(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        enabled: bool,
    ) -> None:
        await self.bot.db.update_server(interaction.guild_id, **{action.value: enabled})
        await interaction.response.send_message(
            f"✅ **{action.name}** is now {'enabled' if enabled else 'disabled'}.",
            ephemeral=True,
        )

    @app_commands.command(name="settings-lists", description="Enables/disables standard lists")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @guild_active()
    @app_commands.choices(
        language=[
            app_commands.Choice(name="German", value="de"),
            app_commands.Choice(name="English", value="en"),
        ]
    )
    async def settings_lists(
        self,
        interaction: discord.Interaction,
        language: app_commands.Choice[str],
        enabled: bool,
    ) -> None:
        server = await self.bot.db.get_server(interaction.guild_id) or {}
        default_lists = server.get("default_lists") or {"de": True, "en": True}
        if isinstance(default_lists, str):
            import json

            default_lists = json.loads(default_lists)
        default_lists[language.value] = enabled
        await self.bot.db.update_server(interaction.guild_id, default_lists=default_lists)
        await self.bot.filters.rebuild(interaction.guild_id)
        await interaction.response.send_message(
            f"✅ Standard list **{language.value.upper()}** is now "
            f"{'enabled' if enabled else 'disabled'}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SettingsCommands(bot))
