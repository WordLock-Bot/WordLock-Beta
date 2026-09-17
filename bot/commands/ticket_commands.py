"""Panel-basiertes Ticket-System für WordLock (TicketTool-Stil)."""

from __future__ import annotations

import asyncio
import datetime
import html as html_lib
import io
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("wordlock.tickets")

BLURPLE = 0x5865F2
GREEN = 0x57F287
RED = 0xED4245
YELLOW = 0xFEE75C
GREY = 0x2B2D31

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://wordlockbot.vercel.app")

DEFAULT_WELCOME = "Hello {mention}! Welcome to your ticket. The team will take care of you shortly."
DEFAULT_NAME_FORMAT = "ticket-{user}"
DEFAULT_MAX_OPEN = 1

TRANSCRIPT_LIMIT = 200
CHANNEL_DELETE_DELAY = 10

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: #36393f; color: #dcddde; margin: 0; }}
.header {{ background: #2f3136; padding: 20px 24px; border-bottom: 3px solid #5865f2; }}
.header h1 {{ margin: 0; font-size: 20px; color: #ffffff; }}
.header .meta {{ font-size: 13px; color: #b9bbbe; margin-top: 4px; }}
.chatlog {{ max-width: 840px; margin: 0 auto; padding: 24px 16px; }}
.msg {{ display: flex; gap: 12px; padding: 8px 2px; }}
.msg:hover {{ background: #2f3136; border-radius: 6px; }}
.avatar {{ width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0; }}
.content {{ flex: 1; min-width: 0; }}
.author {{ font-size: 15px; font-weight: 700; }}
.time {{ font-size: 11px; color: #96989d; margin-left: 8px; }}
.text {{ font-size: 14px; line-height: 1.45; word-wrap: break-word; white-space: pre-wrap; }}
.attachment {{ max-width: 340px; max-height: 340px; border-radius: 8px; margin-top: 6px; display: block; }}
.embed {{ border-left: 4px solid #5865f2; background: #2f3136; border-radius: 4px; padding: 10px 12px; margin-top: 6px; }}
.embed-title {{ font-weight: 700; color: #ffffff; }}
.embed-desc {{ font-size: 13px; color: #dcddde; }}
.embed-field {{ font-size: 12px; color: #b9bbbe; margin-top: 4px; }}
a {{ color: #00a8fc; }}
</style>
</head>
<body>
  <div class="header">
    <h1>{title}</h1>
    <div class="meta">{guild} · {channel} · {created}</div>
  </div>
  <div class="chatlog">
{messages}
  </div>
</body>
</html>
"""


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


# ----------------------------------------------------------------------
# Persistent Views
# ----------------------------------------------------------------------


class TicketOpenButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        super().__init__(
            style=discord.ButtonStyle.success,
            label="🎫 Create ticket",
            custom_id=f"wordlock_ticket_open_{guild_id}",
        )
        self.bot = bot
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("TicketCommands")
        if cog is None:
            await interaction.response.send_message(
                "The ticket system is not available.", ephemeral=True
            )
            return
        await cog._handle_open(interaction, self.guild_id)


class TicketPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.add_item(TicketOpenButton(bot, guild_id))


class TicketClaimButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label="📥 Claim",
            custom_id=f"wordlock_ticket_claim_{guild_id}",
        )
        self.bot = bot
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("TicketCommands")
        if cog is None:
            await interaction.response.send_message(
                "The ticket system is not available.", ephemeral=True
            )
            return
        await cog._handle_claim(interaction, self.guild_id)


class TicketCloseButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="🔒 Close",
            custom_id=f"wordlock_ticket_close_{guild_id}",
        )
        self.bot = bot
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("TicketCommands")
        if cog is None:
            await interaction.response.send_message(
                "The ticket system is not available.", ephemeral=True
            )
            return
        await cog._handle_close_request(interaction, self.guild_id)


class TicketActionsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.add_item(TicketClaimButton(bot, guild_id))
        self.add_item(TicketCloseButton(bot, guild_id))


class TicketConfirmCloseButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, guild_id: int, ticket_id: int) -> None:
        super().__init__(
            style=discord.ButtonStyle.success,
            label="✅ Yes, close",
            custom_id=f"wordlock_ticket_confirm_close_{guild_id}",
        )
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_id = ticket_id

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("TicketCommands")
        if cog is None:
            await interaction.response.send_message(
                "The ticket system is not available.", ephemeral=True
            )
            return
        await cog._handle_confirm_close(
            interaction, self.guild_id, self.ticket_id, self.view
        )


class TicketCancelCloseButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, guild_id: int, ticket_id: int) -> None:
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="❌ Cancel",
            custom_id=f"wordlock_ticket_cancel_close_{guild_id}",
        )
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_id = ticket_id

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        try:
            view.stop()
        except Exception:
            pass
        try:
            if interaction.message is not None:
                await interaction.message.edit(view=None)
        except Exception:
            log.debug("Could not clear close prompt buttons", exc_info=True)
        try:
            await interaction.response.send_message(
                "Closing has been cancelled.", ephemeral=True
            )
        except Exception:
            log.debug("Could not send cancel close response", exc_info=True)


class TicketCloseConfirmView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int, ticket_id: int) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_id = ticket_id
        self.add_item(TicketConfirmCloseButton(bot, guild_id, ticket_id))
        self.add_item(TicketCancelCloseButton(bot, guild_id, ticket_id))


# ----------------------------------------------------------------------
# View-Registrierung
# ----------------------------------------------------------------------


def _get_view_store(bot: commands.Bot):
    connection = getattr(bot, "_connection", None)
    if connection is None:
        return None
    return getattr(connection, "_view_store", None)


def _unregister_view(bot: commands.Bot, view: discord.ui.View) -> None:
    store = _get_view_store(bot)
    if store is None:
        return
    try:
        store.remove_view(view)
    except Exception:
        log.debug("Could not remove stale ticket view", exc_info=True)


async def register_ticket_views(bot: commands.Bot) -> None:
    try:
        configs = await bot.db.all_ticket_configs()
    except Exception:
        log.exception("Could not load ticket configs for view registration")
        return
    for cfg in configs:
        try:
            guild_id = int(cfg["guild_id"])
            panel_views = getattr(bot, "ticket_views", None)
            action_views = getattr(bot, "ticket_action_views", None)
            if panel_views is not None and not panel_views.get(guild_id):
                view = TicketPanelView(bot, guild_id)
                panel_views[guild_id] = view
                message_id = (
                    int(cfg["panel_message_id"]) if cfg.get("panel_message_id") else None
                )
                try:
                    bot.add_view(view, message_id=message_id)
                except Exception:
                    log.exception(
                        "Could not register panel view for guild %s", guild_id
                    )
            if action_views is not None and not action_views.get(guild_id):
                view = TicketActionsView(bot, guild_id)
                action_views[guild_id] = view
                try:
                    bot.add_view(view)
                except Exception:
                    log.exception(
                        "Could not register actions view for guild %s", guild_id
                    )
        except Exception:
            log.exception("Could not register ticket views for guild %s", guild_id)


# ----------------------------------------------------------------------
# Cog
# ----------------------------------------------------------------------


class TicketCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._web_deploy_task: Optional[asyncio.Task] = None

    async def cog_load(self) -> None:
        try:
            await register_ticket_views(self.bot)
        except Exception:
            log.exception("Could not register ticket views in cog_load")
        if self._web_deploy_task is None:
            self._web_deploy_task = self.bot.loop.create_task(self._web_deploy_loop())

    ticket = app_commands.Group(name="ticket", description="Ticket system for this server")

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    @ticket.command(name="setup", description="Sets up the ticket system (panel in this channel)")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        kategorie="Category where ticket channels are created",
        willkommens_nachricht="Welcome message in the ticket ({mention}, {user}, {id}, {ticket}, {guild}, {date}, {time})",
        ticket_name_format="Channel name format for tickets (e.g. ticket-{user})",
        support_rolle="Support team role (claim and close tickets)",
        max_offen="Maximum number of simultaneously open tickets per user",
    )
    async def ticket_setup(
        self,
        interaction: discord.Interaction,
        kategorie: discord.CategoryChannel,
        willkommens_nachricht: Optional[str] = None,
        ticket_name_format: Optional[str] = None,
        support_rolle: Optional[discord.Role] = None,
        max_offen: Optional[int] = None,
    ) -> None:
        embed = discord.Embed(
            title="WordLock Support",
            description="Click the button below to create a support ticket.",
            color=BLURPLE,
        )
        embed.set_footer(text="WordLock Ticket System")

        try:
            message, panel_channel, _ = await self._deploy_panel(
                interaction, interaction.guild_id, embed
            )
        except RuntimeError:
            await interaction.response.send_message(
                "The panel can only be set up in a text channel.",
                ephemeral=True,
            )
            return
        except Exception:
            log.exception("Could not deploy ticket panel (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "The panel could not be created.", ephemeral=True
            )
            return

        welcome = willkommens_nachricht or DEFAULT_WELCOME
        name_format = ticket_name_format or DEFAULT_NAME_FORMAT
        max_open = max_offen or DEFAULT_MAX_OPEN
        support_ids = [support_rolle.id] if support_rolle else []

        try:
            await self.bot.db.set_ticket_config(
                interaction.guild_id,
                panel_channel_id=panel_channel.id,
                panel_message_id=message.id,
                category_id=kategorie.id,
                welcome_message=welcome,
                ticket_name_format=name_format,
                support_role_ids=support_ids,
                max_open=max_open,
                enabled=True,
            )
        except Exception:
            log.exception("Could not save ticket config (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "The configuration could not be saved.", ephemeral=True
            )
            return

        self._register_guild_panel_view(interaction.guild_id, message.id)
        self._register_guild_actions_view(interaction.guild_id)

        support_text = support_rolle.mention if support_rolle else "None"
        confirm = discord.Embed(
            title="Ticket system set up",
            description=(
                f"Panel channel: {panel_channel.mention}\n"
                f"Category: {kategorie.mention}\n"
                f"Support role: {support_text}\n"
                f"Name format: `{name_format}`\n"
                f"Max. open tickets: {max_open}"
            ),
            color=BLURPLE,
        )
        await interaction.response.send_message(embed=confirm, ephemeral=True)

    @ticket.command(name="disable", description="Disables the ticket system")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_disable(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        try:
            config = await self.bot.db.get_ticket_config(guild_id)
        except Exception:
            log.exception("Could not load ticket config (guild %s)", guild_id)
            await interaction.response.send_message(
                "The configuration could not be loaded.", ephemeral=True
            )
            return

        if config is None or not config.get("enabled"):
            await interaction.response.send_message(
                "The ticket system is already disabled or not set up.",
                ephemeral=True,
            )
            return

        try:
            await self.bot.db.set_ticket_config(guild_id, enabled=False)
        except Exception:
            log.exception("Could not disable ticket config (guild %s)", guild_id)
            await interaction.response.send_message(
                "The ticket system could not be disabled.", ephemeral=True
            )
            return

        await self._disable_panel_message(config)

        embed = discord.Embed(
            title="Ticket system disabled",
            description="The panel has been removed. Use `/ticket setup` to re-enable it.",
            color=RED,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ticket.command(name="panel", description="Re-sends the ticket panel")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_panel(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        try:
            config = await self.bot.db.get_ticket_config(guild_id)
        except Exception:
            log.exception("Could not load ticket config (guild %s)", guild_id)
            await interaction.response.send_message(
                "The configuration could not be loaded.", ephemeral=True
            )
            return

        if config is None or not config.get("enabled"):
            await interaction.response.send_message(
                "The ticket system is not set up. Use `/ticket setup` first.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="WordLock Support",
            description="Click the button below to create a support ticket.",
            color=BLURPLE,
        )
        embed.set_footer(text="WordLock Ticket System")

        try:
            message, panel_channel, _ = await self._deploy_panel(
                interaction, guild_id, embed
            )
        except RuntimeError:
            await interaction.response.send_message(
                "The panel can only be sent in a text channel.", ephemeral=True
            )
            return
        except Exception:
            log.exception("Could not redeploy ticket panel (guild %s)", guild_id)
            await interaction.response.send_message(
                "The panel could not be sent.", ephemeral=True
            )
            return

        try:
            await self.bot.db.set_ticket_config(
                guild_id,
                panel_channel_id=panel_channel.id,
                panel_message_id=message.id,
            )
        except Exception:
            log.exception("Could not update panel ids (guild %s)", guild_id)

        self._register_guild_panel_view(guild_id, message.id)

        embed = discord.Embed(
            title="Panel re-sent",
            description=f"The panel was placed in {panel_channel.mention}.",
            color=GREEN,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ticket.command(name="config", description="Shows the current ticket configuration")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_config(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        try:
            config = await self.bot.db.get_ticket_config(guild_id)
        except Exception:
            log.exception("Could not load ticket config (guild %s)", guild_id)
            await interaction.response.send_message(
                "The configuration could not be loaded.", ephemeral=True
            )
            return

        if config is None:
            await interaction.response.send_message(
                "The ticket system is not set up. Use `/ticket setup`.",
                ephemeral=True,
            )
            return

        enabled = bool(config.get("enabled"))
        support_ids = self._parse_role_ids(config.get("support_role_ids"))
        role_text = ", ".join(f"<@&{r}>" for r in support_ids) or "None"

        panel_channel = self.bot.get_channel(
            int(config["panel_channel_id"])
        ) if config.get("panel_channel_id") else None
        category = self.bot.get_channel(
            int(config["category_id"])
        ) if config.get("category_id") else None

        embed = discord.Embed(
            title="Ticket Configuration",
            description=f"{'🟢 **Enabled**' if enabled else '🔴 **Disabled**'}",
            color=BLURPLE,
        )
        embed.add_field(
            name="Panel channel",
            value=panel_channel.mention if panel_channel else "Unknown",
            inline=False,
        )
        embed.add_field(
            name="Category",
            value=category.mention if category else "Unknown",
            inline=False,
        )
        welcome = (config.get("welcome_message") or DEFAULT_WELCOME)
        embed.add_field(name="Welcome message", value=f"```{welcome[:80]}{'…' if len(welcome) > 80 else ''}```", inline=False)
        embed.add_field(
            name="Name format", value=f"`{config.get('ticket_name_format') or DEFAULT_NAME_FORMAT}`", inline=True
        )
        embed.add_field(
            name="Max. open per user",
            value=str(config.get("max_open") or DEFAULT_MAX_OPEN),
            inline=True,
        )
        embed.add_field(name="Support role(s)", value=role_text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # Button-Logik
    # ------------------------------------------------------------------

    async def _handle_open(
        self, interaction: discord.Interaction, guild_id: int
    ) -> None:
        if interaction.guild is None:
            return
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        try:
            config = await self.bot.db.get_ticket_config(guild_id)
        except Exception:
            log.exception("Could not load ticket config (guild %s)", guild_id)
            await interaction.followup.send(
                "The ticket system could not be loaded.", ephemeral=True
            )
            return

        if config is None or not config.get("enabled"):
            await interaction.followup.send(
                "The ticket system is disabled.", ephemeral=True
            )
            return

        guild = interaction.guild
        member = interaction.user

        if await self._is_support(guild, member, config):
            await interaction.followup.send(
                "You are on the support team and cannot create a ticket.",
                ephemeral=True,
            )
            return

        try:
            open_count = await self.bot.db.open_discord_tickets(guild_id, member.id)
        except Exception:
            log.exception("Could not count open tickets (guild %s)", guild_id)
            await interaction.followup.send(
                "Your open tickets could not be checked.", ephemeral=True
            )
            return

        max_open = int(config.get("max_open") or DEFAULT_MAX_OPEN)
        if open_count >= max_open:
            await interaction.followup.send(
                f"You have already reached the maximum of **{max_open}** "
                "open tickets.",
                ephemeral=True,
            )
            return

        category = guild.get_channel(int(config.get("category_id") or 0))
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                "The configured category was not found.", ephemeral=True
            )
            return

        channel_name = self._channel_name(config, member)
        overwrites = self._ticket_overwrites(guild, member, config)

        try:
            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                reason="Ticket opened",
                sync_permissions=False,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to create the ticket channel.",
                ephemeral=True,
            )
            return
        except Exception:
            log.exception("Could not create ticket channel (guild %s)", guild_id)
            await interaction.followup.send(
                "The ticket channel could not be created.", ephemeral=True
            )
            return

        try:
            ticket_id = await self.bot.db.create_discord_ticket(
                guild_id, channel.id, member.id
            )
        except Exception:
            log.exception("Could not persist ticket (channel %s)", channel.id)
            try:
                await channel.delete(reason="Ticket database error")
            except Exception:
                log.debug("Could not delete ticket channel after DB error", exc_info=True)
            await interaction.followup.send(
                "The ticket could not be saved.", ephemeral=True
            )
            return

        welcome_text = self._render(
            config.get("welcome_message") or DEFAULT_WELCOME,
            **self._fields(member, guild, ticket_id),
        )
        embed = discord.Embed(
            title=f"Ticket #{ticket_id}", description=welcome_text, color=BLURPLE
        )
        embed.set_footer(text="WordLock Ticket System")

        try:
            await channel.send(embed=embed, view=TicketActionsView(self.bot, guild_id))
        except Exception:
            log.exception("Could not send welcome embed (channel %s)", channel.id)

        try:
            await interaction.followup.send(
                f"Ticket created: {channel.mention}", ephemeral=True
            )
        except Exception:
            log.debug("Could not send ticket confirmation", exc_info=True)

    async def _handle_claim(
        self, interaction: discord.Interaction, guild_id: int
    ) -> None:
        guild = interaction.guild
        if guild is None:
            return
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        try:
            config = await self.bot.db.get_ticket_config(guild_id)
            ticket = await self.bot.db.get_discord_ticket_by_channel(
                interaction.channel_id
            )
        except Exception:
            log.exception("Could not load ticket data (guild %s)", guild_id)
            await interaction.followup.send(
                "The ticket could not be loaded.", ephemeral=True
            )
            return

        if config is None or not config.get("enabled"):
            await interaction.followup.send(
                "The ticket system is disabled.", ephemeral=True
            )
            return

        if ticket is None:
            await interaction.followup.send(
                "No active ticket was found in this channel.", ephemeral=True
            )
            return

        if not await self._is_support(guild, interaction.user, config):
            await interaction.followup.send(
                "You don't have permission to claim tickets.", ephemeral=True
            )
            return

        claimed_by = ticket.get("claimed_by")
        if claimed_by:
            if int(claimed_by) == interaction.user.id:
                await interaction.followup.send(
                    "You are already working on this ticket.", ephemeral=True
                )
                return
            claimed_member = guild.get_member(int(claimed_by))
            name = claimed_member.display_name if claimed_member else f"<@{claimed_by}>"
            await interaction.followup.send(
                f"This ticket is already being handled by **{name}**.",
                ephemeral=True,
            )
            return

        ok = await self._claim_ticket(
            interaction.channel, int(ticket["id"]), interaction.user
        )
        if ok:
            await interaction.followup.send(
                "Ticket claimed successfully.", ephemeral=True
            )

    async def _handle_close_request(
        self, interaction: discord.Interaction, guild_id: int
    ) -> None:
        if interaction.guild is None or not isinstance(
            interaction.channel, discord.TextChannel
        ):
            await interaction.response.send_message(
                "Not a valid channel for a ticket.", ephemeral=True
            )
            return

        try:
            ticket = await self.bot.db.get_discord_ticket_by_channel(
                interaction.channel.id
            )
        except Exception:
            log.exception("Could not load ticket for close (guild %s)", guild_id)
            await interaction.response.send_message(
                "The ticket could not be loaded.", ephemeral=True
            )
            return

        if ticket is None:
            await interaction.response.send_message(
                "No active ticket was found in this channel.", ephemeral=True
            )
            return

        ticket_id = int(ticket["id"])
        embed = discord.Embed(
            title=f"Close ticket #{ticket_id}?",
            description=(
                "Are you sure you want to close this ticket?\n"
                "The channel will be deleted and a transcript will be created."
            ),
            color=YELLOW,
        )
        view = TicketCloseConfirmView(self.bot, guild_id, ticket_id)
        await interaction.response.send_message(embed=embed, view=view)

    async def _handle_confirm_close(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        ticket_id: int,
        view: discord.ui.View,
    ) -> None:
        try:
            view.stop()
        except Exception:
            pass

        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        try:
            if interaction.message is not None:
                await interaction.message.edit(view=None)
        except Exception:
            log.debug("Could not clear close prompt buttons", exc_info=True)

        guild = interaction.guild
        channel = interaction.channel
        if guild is None or not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Not a valid channel.", ephemeral=True)
            return

        try:
            ticket = await self.bot.db.get_discord_ticket(ticket_id)
        except Exception:
            log.exception("Could not load ticket %s", ticket_id)
            await interaction.followup.send(
                "Error loading the ticket.", ephemeral=True
            )
            return

        if ticket is None:
            await interaction.followup.send(
                "The ticket was not found.", ephemeral=True
            )
            return

        try:
            config = await self.bot.db.get_ticket_config(guild_id)
        except Exception:
            config = None

        is_creator = int(ticket["creator_id"]) == interaction.user.id
        support = False
        if config:
            try:
                support = await self._is_support(guild, interaction.user, config)
            except Exception:
                support = False

        if not (is_creator or support):
            await interaction.followup.send(
                "You don't have permission to close this ticket.",
                ephemeral=True,
            )
            return

        try:
            messages = [
                m
                async for m in channel.history(
                    limit=TRANSCRIPT_LIMIT, oldest_first=True
                )
            ]
        except Exception:
            log.exception("Could not fetch ticket history (channel %s)", channel.id)
            messages = []

        html = self._build_transcript(guild, ticket_id, channel, messages)

        try:
            transcript_id = await self.bot.db.add_transcript(
                guild_id, ticket_id, channel.id, html
            )
            await self.bot.db.close_discord_ticket(
                ticket_id, interaction.user.id, transcript_id
            )
        except Exception:
            log.exception("Could not save ticket transcript (ticket %s)", ticket_id)
            await interaction.followup.send(
                "The ticket could not be closed.", ephemeral=True
            )
            return

        await self._edit_welcome_closed(channel, ticket_id)
        await self._send_transcript_dm(guild, ticket, transcript_id, html)

        closing_embed = discord.Embed(
            title=f"Ticket #{ticket_id}",
            description="Ticket is being closed.",
            color=RED,
        )
        try:
            await channel.send(embed=closing_embed)
        except Exception:
            log.debug("Could not send closing embed", exc_info=True)

        async def _delete_channel() -> None:
            await asyncio.sleep(CHANNEL_DELETE_DELAY)
            try:
                await channel.delete(reason="Ticket closed")
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                log.debug("Could not delete ticket channel %s", channel.id, exc_info=True)

        self.bot.loop.create_task(_delete_channel())

        await interaction.followup.send("Ticket is being closed.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        try:
            ticket = await self.bot.db.get_discord_ticket_by_channel(message.channel.id)
        except Exception:
            return

        if not ticket or ticket.get("status") != "open":
            return

        try:
            config = await self.bot.db.get_ticket_config(message.guild.id)
        except Exception:
            return

        if not config or not config.get("enabled"):
            return

        if await self._is_support(message.guild, message.author, config):
            await self._claim_ticket(
                message.channel, int(ticket["id"]), message.author
            )

    # ------------------------------------------------------------------
    # Helfer
    # ------------------------------------------------------------------

    def _render(self, text: str, **fields: str) -> str:
        for key, value in fields.items():
            text = text.replace("{" + key + "}", str(value))
        return text

    def _fields(
        self,
        user: Optional[discord.User] = None,
        guild: Optional[discord.Guild] = None,
        ticket_id: Optional[int] = None,
    ) -> Dict[str, str]:
        now = datetime.datetime.now()
        user_name = (user.global_name or user.name) if user else ""
        return {
            "user": user_name or "user",
            "mention": user.mention if user else "",
            "id": str(user.id) if user else "",
            "ticket": str(ticket_id or ""),
            "guild": guild.name if guild else "",
            "date": now.strftime("%d.%m.%Y"),
            "time": now.strftime("%H:%M"),
            "count": str(ticket_id or ""),
        }

    def _sanitize(self, text: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9\-]+", "-", (text or "").lower())
        clean = re.sub(r"-{2,}", "-", clean).strip("-")
        return clean or "ticket"

    def _channel_name(self, config: Dict[str, Any], member: discord.Member) -> str:
        fmt = config.get("ticket_name_format") or DEFAULT_NAME_FORMAT
        rendered = self._render(fmt, **self._fields(member, None, None))
        return (self._sanitize(rendered) or "ticket")[:100]

    def _parse_role_ids(self, value: Any) -> List[int]:
        if not value:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                return []
        try:
            return [int(v) for v in value]
        except (TypeError, ValueError):
            return []

    async def _is_support(
        self, guild: discord.Guild, user: discord.User, config: Dict[str, Any]
    ) -> bool:
        if isinstance(user, discord.Member):
            if user.guild_permissions.manage_guild or user.guild_permissions.administrator:
                return True
            support_ids = self._parse_role_ids(config.get("support_role_ids"))
            member_roles = {r.id for r in user.roles}
            if any(rid in member_roles for rid in support_ids):
                return True
        return False

    def _ticket_overwrites(
        self, guild: discord.Guild, member: discord.Member, config: Dict[str, Any]
    ) -> Dict[Any, discord.PermissionOverwrite]:
        overwrites: Dict[Any, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
        }
        if guild.me is not None:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                manage_permissions=True,
                embed_links=True,
                attach_files=True,
            )
        for rid in self._parse_role_ids(config.get("support_role_ids")):
            role = guild.get_role(rid)
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                )
        return overwrites

    async def _claim_ticket(
        self,
        channel: discord.abc.Messageable,
        ticket_id: int,
        member: discord.Member,
    ) -> bool:
        try:
            claimed = await self.bot.db.claim_discord_ticket(ticket_id, member.id)
        except Exception:
            log.exception("Could not claim ticket %s", ticket_id)
            return False
        if not claimed:
            return False

        if isinstance(channel, discord.TextChannel):
            welcome = await self._find_welcome_message(channel, ticket_id)
            embed = discord.Embed(
                title=f"Ticket #{ticket_id}",
                description=f"This ticket is being handled by **{member.display_name}**.",
                color=BLURPLE,
            )
            if welcome is not None:
                actions = TicketActionsView(self.bot, channel.guild.id)
                claim_button = next(
                    (
                        child
                        for child in actions.children
                        if isinstance(child, TicketClaimButton)
                    ),
                    None,
                )
                if claim_button is not None:
                    claim_button.disabled = True
                try:
                    await welcome.edit(embed=embed, view=actions)
                except Exception:
                    log.debug("Could not edit welcome embed after claim", exc_info=True)
            try:
                await channel.send(
                    embed=discord.Embed(
                        description=f"{member.mention} is handling this ticket.",
                        color=BLURPLE,
                    )
                )
            except Exception:
                log.debug("Could not send claim embed", exc_info=True)
        return True

    async def _find_welcome_message(
        self, channel: discord.TextChannel, ticket_id: int
    ) -> Optional[discord.Message]:
        title = f"Ticket #{ticket_id}"
        try:
            async for msg in channel.history(limit=25):
                if msg.author.id == self.bot.user.id and msg.embeds:
                    if msg.embeds[0].title == title:
                        return msg
        except Exception:
            log.debug("Could not search history for welcome message", exc_info=True)
        return None

    async def _edit_welcome_closed(
        self, channel: discord.TextChannel, ticket_id: int
    ) -> None:
        msg = await self._find_welcome_message(channel, ticket_id)
        if msg is None or not msg.embeds:
            return
        try:
            embed = msg.embeds[0]
            embed.title = f"~~Ticket #{ticket_id}~~"
            embed.description = "Ticket closed."
            await msg.edit(embed=embed, view=None)
        except Exception:
            log.debug("Could not update welcome embed on close", exc_info=True)

    async def _send_transcript_dm(
        self,
        guild: discord.Guild,
        ticket: Dict[str, Any],
        transcript_id: int,
        html: str,
    ) -> None:
        creator = self.bot.get_user(int(ticket["creator_id"]))
        if creator is None:
            try:
                creator = await self.bot.fetch_user(int(ticket["creator_id"]))
            except Exception:
                log.debug("Could not resolve ticket creator", exc_info=True)
                creator = None
        if creator is None:
            return

        embed = discord.Embed(
            title=f"Ticket #{ticket['id']}",
            description=(
                f"Your ticket in **{guild.name}** has been closed.\n\n"
                f"You can find the full transcript here:\n"
                f"{DASHBOARD_URL}/server/{guild.id}/tickets/transcripts/{transcript_id}"
            ),
            color=BLURPLE,
        )
        file = discord.File(io.BytesIO(html.encode("utf-8")), filename="transcript.html")
        try:
            await creator.send(embed=embed, file=file)
        except Exception:
            log.exception("Could not send transcript DM to %s", creator.id)

    # ------------------------------------------------------------------
    # Panel-Verwaltung
    # ------------------------------------------------------------------

    def _register_guild_panel_view(self, guild_id: int, message_id: int) -> None:
        old = self.bot.ticket_views.pop(guild_id, None)
        if old is not None:
            _unregister_view(self.bot, old)
        view = TicketPanelView(self.bot, guild_id)
        self.bot.ticket_views[guild_id] = view
        try:
            self.bot.add_view(view, message_id=message_id)
        except Exception:
            log.exception("Could not register panel view (guild %s)", guild_id)

    def _register_guild_actions_view(self, guild_id: int) -> None:
        old = self.bot.ticket_action_views.pop(guild_id, None)
        if old is not None:
            _unregister_view(self.bot, old)
        view = TicketActionsView(self.bot, guild_id)
        self.bot.ticket_action_views[guild_id] = view
        try:
            self.bot.add_view(view)
        except Exception:
            log.exception("Could not register actions view (guild %s)", guild_id)

    async def _deploy_panel(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        embed: discord.Embed,
    ) -> Any:
        config = await self.bot.db.get_ticket_config(guild_id)
        if config and config.get("panel_channel_id") and config.get("panel_message_id"):
            try:
                channel = self.bot.get_channel(int(config["panel_channel_id"]))
                if isinstance(channel, discord.TextChannel):
                    message = await channel.fetch_message(
                        int(config["panel_message_id"])
                    )
                    view = TicketPanelView(self.bot, guild_id)
                    await message.edit(embed=embed, view=view, attachments=[])
                    return message, channel, True
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                log.debug("Existing ticket panel could not be edited", exc_info=True)
            except Exception:
                log.exception("Unexpected error editing ticket panel")

        channel = interaction.channel
        if channel is None or not isinstance(channel, discord.TextChannel):
            raise RuntimeError("no_text_channel")
        view = TicketPanelView(self.bot, guild_id)
        message = await channel.send(embed=embed, view=view)
        return message, channel, False

    async def _disable_panel_message(self, config: Dict[str, Any]) -> None:
        if not config.get("panel_channel_id") or not config.get("panel_message_id"):
            return
        channel = self.bot.get_channel(int(config["panel_channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(int(config["panel_message_id"]))
            embed = discord.Embed(
                title="WordLock Support",
                description="The ticket system is **disabled**.",
                color=GREY,
            )
            embed.set_footer(text="WordLock Ticket System")
            await message.edit(embed=embed, view=None)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            log.debug("Ticket panel could not be edited", exc_info=True)
        except Exception:
            log.exception("Could not disable ticket panel message")

    # ------------------------------------------------------------------
    # Web-Deploy-Loop
    # ------------------------------------------------------------------

    @staticmethod
    def _panel_embed() -> discord.Embed:
        embed = discord.Embed(
            title="WordLock Support",
            description="Click the button below to create a support ticket.",
            color=BLURPLE,
        )
        embed.set_footer(text="WordLock Ticket System")
        return embed

    async def _web_deploy_loop(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                pending = await self.bot.db.pending_ticket_deploys()
                for cfg in pending:
                    guild_id = int(cfg["guild_id"])
                    channel_id = cfg.get("panel_channel_id")
                    if not channel_id:
                        await self.bot.db.clear_ticket_deploy(guild_id)
                        continue
                    guild = self.bot.get_guild(guild_id)
                    if guild is None:
                        continue
                    channel = guild.get_channel(int(channel_id))
                    if channel is None or not isinstance(channel, discord.TextChannel):
                        continue
                    embed = self._panel_embed()
                    view = TicketPanelView(self.bot, guild_id)
                    try:
                        message = await channel.send(embed=embed, view=view)
                        self._register_guild_panel_view(guild_id, message.id)
                        self._register_guild_actions_view(guild_id)
                        await self.bot.db.set_ticket_config(
                            guild_id,
                            panel_channel_id=channel.id,
                            panel_message_id=message.id,
                            enabled=True,
                            panel_needs_deploy=False,
                        )
                    except Exception:
                        log.exception("Web-deploy failed for guild %s", guild_id)
            except Exception:
                log.exception("Web-deploy loop iteration failed")
            await asyncio.sleep(10)

    # ------------------------------------------------------------------
    # Transkript
    # ------------------------------------------------------------------

    def _esc(self, text: Any) -> str:
        return html_lib.escape(str(text or ""), quote=True)

    def _author_color(self, author: Any) -> str:
        colour = getattr(author, "colour", None)
        rgb = getattr(colour, "to_rgb", None)
        if rgb is None:
            return "#ffffff"
        r, g, b = rgb()
        if (r, g, b) == (0, 0, 0):
            return "#ffffff"
        return "#{:02x}{:02x}{:02x}".format(r, g, b)

    def _build_transcript(
        self,
        guild: discord.Guild,
        ticket_id: int,
        channel: discord.TextChannel,
        messages: List[discord.Message],
    ) -> str:
        parts: List[str] = []
        for msg in messages:
            if msg.type not in (
                discord.MessageType.default,
                discord.MessageType.reply,
            ):
                continue

            content = msg.content or ""
            attachments_html = ""
            for att in msg.attachments:
                if att.content_type and att.content_type.startswith("image/"):
                    attachments_html += (
                        f'<img class="attachment" src="{self._esc(att.url)}" alt="">'
                    )
                else:
                    attachments_html += (
                        f'<div class="text"><a href="{self._esc(att.url)}">'
                        f"{self._esc(att.filename)}</a></div>"
                    )

            embeds_html = ""
            for emb in msg.embeds:
                title = emb.title or emb.author.name or ""
                desc = emb.description or ""
                fields_html = ""
                for field in emb.fields[:4]:
                    fields_html += (
                        f"<div class='embed-field'><b>{self._esc(field.name)}</b>: "
                        f"{self._esc(field.value)}</div>"
                    )
                if title or desc or fields_html:
                    embeds_html += (
                        f'<div class="embed">'
                        f'<div class="embed-title">{self._esc(title)}</div>'
                        f'<div class="embed-desc">{self._esc(desc)}</div>'
                        f"{fields_html}</div>"
                    )

            if not content and not attachments_html and not embeds_html:
                continue

            color = self._author_color(msg.author)
            parts.append(
                '<div class="msg">'
                f'<img class="avatar" src="{self._esc(msg.author.display_avatar.url)}" alt="">'
                '<div class="content">'
                f'<span class="author" style="color: {color}">{self._esc(msg.author.display_name)}</span>'
                f'<span class="time">{msg.created_at.strftime("%d.%m.%Y %H:%M")}</span>'
                f'<div class="text">{self._esc(content)}</div>'
                f"{attachments_html}"
                f"{embeds_html}"
                "</div></div>"
            )

        created = (
            messages[0].created_at.strftime("%d.%m.%Y %H:%M") if messages else "–"
        )
        return HTML_TEMPLATE.format(
            title=self._esc(f"Ticket #{ticket_id} · {channel.name}"),
            guild=self._esc(guild.name),
            channel=self._esc(channel.name),
            created=created,
            messages="\n".join(parts),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketCommands(bot))