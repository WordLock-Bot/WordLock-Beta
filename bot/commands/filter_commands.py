"""Slash commands to manage the custom word list and the bypass per server."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

CATEGORIES = ["insult", "profanity", "slur", "sexual", "threat", "spam", "custom"]
ACTIONS = ["delete", "warn", "timeout", "log"]


def manage_guild():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            raise app_commands.NoPrivateMessage()
        server = await interaction.client.db.get_server(interaction.guild_id)
        if server and server.get("status") == "disabled":
            raise app_commands.CheckFailure("wordlock_disabled")
        member = interaction.user
        if member.id in interaction.client.owner_ids:
            return True
        if isinstance(member, discord.Member) and member.guild_permissions.manage_guild:
            return True
        raise app_commands.CheckFailure("You need the `Manage Server` permission.")

    return app_commands.check(predicate)


def _parse_bypass(json_value) -> list[int]:
    if not json_value:
        return []
    if isinstance(json_value, str):
        import json

        json_value = json.loads(json_value)
    return [int(v) for v in json_value]


class FilterCommands(commands.GroupCog, name="filter"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="add", description="Adds a word to the server filter")
    @manage_guild()
    @app_commands.choices(
        category=[app_commands.Choice(name=c, value=c) for c in CATEGORIES],
        action=[app_commands.Choice(name=a, value=a) for a in ACTIONS],
    )
    async def filter_add(
        self,
        interaction: discord.Interaction,
        word: str,
        category: app_commands.Choice[str] = "custom",
        severity: app_commands.Range[int, 1, 5] = 3,
        action: app_commands.Choice[str] = "delete",
    ) -> None:
        category = category.value if isinstance(category, app_commands.Choice) else category
        action = action.value if isinstance(action, app_commands.Choice) else action
        ok = await self.bot.db.add_custom_word(
            interaction.guild_id, word.lower().strip(), category, severity, action
        )
        await self.bot.filters.rebuild(interaction.guild_id)
        if not ok:
            await interaction.response.send_message(
                "The word could not be added.", ephemeral=True
            )
            return
        embed = discord.Embed(
            title="Filter word added",
            description=f"`{word}` (category: {category}, severity: {severity}, action: {action})",
            color=0x57F287,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="remove", description="Removes a word from the server filter")
    @manage_guild()
    async def filter_remove(
        self, interaction: discord.Interaction, word: str
    ) -> None:
        removed = await self.bot.db.remove_custom_word(interaction.guild_id, word.lower().strip())
        await self.bot.filters.rebuild(interaction.guild_id)
        if removed:
            await interaction.response.send_message(
                f"`{word}` was removed.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"`{word}` is not in the server filter.", ephemeral=True
            )

    @app_commands.command(name="list", description="Shows all active filters")
    @manage_guild()
    async def filter_list(self, interaction: discord.Interaction) -> None:
        engine = await self.bot.filters.get_or_load(interaction.guild_id)
        custom = await self.bot.db.get_custom_words(interaction.guild_id, enabled_only=False)
        server = await self.bot.db.get_server(interaction.guild_id) or {}
        default_lists = server.get("default_lists") or {"de": True, "en": True}
        if isinstance(default_lists, str):
            import json

            default_lists = json.loads(default_lists)

        active_langs = [l for l, a in default_lists.items() if a] or ["en"]
        std = [e for e in engine.entries if not e.custom]
        text = [
            f"**Standard lists:** {', '.join(sorted(active_langs)).upper()} "
            f"({len(std)} words)",
            f"**Custom words:** {len(custom)}",
        ]
        if custom:
            lines = [
                f"• `{c['word']}` — {c['category']} / {c['severity']}/5 / "
                f"{c['action']} {'✓' if c['enabled'] else '✗'}"
                for c in custom[:20]
            ]
            text.append("```\n" + "\n".join(lines) + "```")
        await interaction.response.send_message("\n".join(text), ephemeral=True)

    @app_commands.command(name="enable", description="Enables a custom word")
    @manage_guild()
    async def filter_enable(
        self, interaction: discord.Interaction, word: str
    ) -> None:
        await self.bot.db.set_custom_word_enabled(interaction.guild_id, word.lower().strip(), True)
        await self.bot.filters.rebuild(interaction.guild_id)
        await interaction.response.send_message(f"`{word}` is active again.", ephemeral=True)

    @app_commands.command(name="disable", description="Disables a custom word (keeps it)")
    @manage_guild()
    async def filter_disable(
        self, interaction: discord.Interaction, word: str
    ) -> None:
        await self.bot.db.set_custom_word_enabled(interaction.guild_id, word.lower().strip(), False)
        await self.bot.filters.rebuild(interaction.guild_id)
        await interaction.response.send_message(f"`{word}` was disabled.", ephemeral=True)

    # ------------------------------------------------------------------
    # Bypass management
    # ------------------------------------------------------------------

    @app_commands.command(
        name="bypass",
        description="Manage filter bypass (roles/users that are never filtered)",
    )
    @manage_guild()
    async def bypass(self, interaction: discord.Interaction) -> None:
        server = await self.bot.db.get_server(interaction.guild_id) or {}
        roles = _parse_bypass(server.get("bypass_roles"))
        users = _parse_bypass(server.get("bypass_users"))
        lines = []
        if roles:
            lines.append("**Bypass roles:** " + ", ".join(f"<@&{r}>" for r in roles))
        if users:
            lines.append("**Bypass users:** " + ", ".join(f"<@{u}>" for u in users))
        if not lines:
            lines.append("No bypass configured. Use `/filter bypass add`.")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="bypass-add", description="Adds a user or role to the bypass")
    @manage_guild()
    async def bypass_add(
        self, interaction: discord.Interaction, target: discord.Role | discord.User
    ) -> None:
        server = await self.bot.db.get_server(interaction.guild_id) or {}
        is_role = isinstance(target, discord.Role)
        key = "bypass_roles" if is_role else "bypass_users"
        items = _parse_bypass(server.get(key))
        if target.id in items:
            await interaction.response.send_message(
                "Already in the bypass.", ephemeral=True
            )
            return
        items.append(target.id)
        await self.bot.db.update_server(interaction.guild_id, **{key: items})
        kind = "role" if is_role else "user"
        await interaction.response.send_message(
            f"{kind.capitalize()} <@{target.id}> was added to the bypass.",
            ephemeral=True,
        )

    @app_commands.command(name="bypass-remove", description="Removes a user or role from the bypass")
    @manage_guild()
    async def bypass_remove(
        self, interaction: discord.Interaction, target: discord.Role | discord.User
    ) -> None:
        server = await self.bot.db.get_server(interaction.guild_id) or {}
        is_role = isinstance(target, discord.Role)
        key = "bypass_roles" if is_role else "bypass_users"
        items = _parse_bypass(server.get(key))
        if target.id not in items:
            await interaction.response.send_message(
                "Not in the bypass.", ephemeral=True
            )
            return
        items.remove(target.id)
        await self.bot.db.update_server(interaction.guild_id, **{key: items})
        await interaction.response.send_message(
            f"<@{target.id}> was removed from the bypass.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FilterCommands(bot))
