"""Admin command to send messages as another bot via a temporary webhook.

Usage:
  /webhooksay <kanal> <name> <avatar>   - always opens a modal with the message text
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("wordlock.webhooksay")


def manage_guild():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            raise app_commands.NoPrivateMessage()
        member = interaction.user
        if member.id in interaction.client.owner_ids:
            return True
        if isinstance(member, discord.Member) and member.guild_permissions.manage_webhooks:
            return True
        if isinstance(member, discord.Member) and member.guild_permissions.manage_guild:
            return True
        raise app_commands.CheckFailure(
            "You need the `Manage Webhooks` (or `Manage Server`) permission."
        )

    return app_commands.check(predicate)


class WebhookSayModal(discord.ui.Modal, title="WebhookSay – Message"):
    text = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.paragraph,
        placeholder="Write the message you want to send here …",
        required=True,
        max_length=2000,
    )

    def __init__(self, channel: discord.TextChannel, name: str, avatar_url: str | None):
        super().__init__()
        self.channel = channel
        self.name = name or "WebhookSay"
        self.avatar_url = avatar_url

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await _send_as_webhook(
                self.channel,
                self.name,
                self.avatar_url,
                self.text.value,
                interaction.user,
            )
            await interaction.followup.send("✓ Message sent.", ephemeral=True)
        except Exception as exc:
            log.exception("webhooksay modal failed in %s", self.channel)
            await interaction.followup.send(
                f"Error while sending: {exc}", ephemeral=True
            )


async def _send_as_webhook(
    channel: discord.TextChannel,
    name: str,
    avatar_url: str | None,
    content: str,
    author: discord.User,
) -> None:
    """Create a temp webhook (name/avatar of the target bot), send, then delete it."""
    if not channel.guild.me.guild_permissions.manage_webhooks:
        raise app_commands.CheckFailure(
            "The bot needs the `Manage Webhooks` permission."
        )
    hook = await channel.create_webhook(
        name=f"WebhookSay: {name}" if name else "WebhookSay"
    )
    try:
        await hook.send(
            content,
            username=name or None,
            avatar_url=avatar_url or None,
        )
        log.info(
            "webhooksay by user %s (%s) -> channel %s as '%s'",
            author.id,
            author,
            channel,
            name,
        )
    finally:
        try:
            await hook.delete()
        except Exception:
            log.debug("Could not delete temp webhook", exc_info=True)


class WebhookSayCommands(commands.Cog):
    """Send a message as another bot via a temporary webhook (modal prompt)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="webhooksay",
        description="Send a message as another bot (opens a modal).",
    )
    @manage_guild()
    @app_commands.describe(
        kanal="Channel where the message should appear",
        name="Display name (e.g. the bot whose name you want to use)",
        avatar="URL to the bot's avatar image",
    )
    async def webhooksay(
        self,
        interaction: discord.Interaction,
        kanal: discord.TextChannel,
        name: str,
        avatar: str | None = None,
    ) -> None:
        modal = WebhookSayModal(kanal, name, avatar)
        await interaction.response.send_modal(modal)
