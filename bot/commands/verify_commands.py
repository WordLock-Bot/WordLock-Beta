"""Panel-basiertes Verifizierungssystem für WordLock."""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("wordlock.verify")

GREEN = 0x57F287
RED = 0xED4245
GREY = 0x2B2D31

DEFAULT_WELCOME = "✅ You have been successfully verified. Welcome, {mention}!"
DEFAULT_DM = "Welcome to {guild}! You are now verified as {user}."


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


def build_message(verify_role_id: Optional[int] = None) -> discord.Embed:
    rules = (
        "Read the rules of this server.\n"
        "Click the **🔓 Verify** button below to get access."
    )
    embed = discord.Embed(
        title="✅ Verification",
        description=rules,
        color=GREEN,
    )
    embed.set_footer(text="WordLock Verification")
    if verify_role_id:
        embed.add_field(
            name="Role after verification",
            value=f"<@&{verify_role_id}>",
            inline=False,
        )
    return embed


class VerifyButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        super().__init__(
            style=discord.ButtonStyle.success,
            label="🔓 Verify",
            custom_id=f"wordlock_verify_{guild_id}",
        )
        self.bot = bot
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("VerifyCommands")
        if cog is None:
            await interaction.response.send_message(
                "The verification system is not available.", ephemeral=True
            )
            return
        await cog.do_verify(interaction, self.guild_id)


class VerifyPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.add_item(VerifyButton(bot, guild_id))


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
        log.debug("Could not remove stale verify view", exc_info=True)


async def register_verify_views(bot: commands.Bot) -> None:
    try:
        configs = await bot.db.all_verify_configs()
    except Exception:
        log.exception("Could not load verify configs for view registration")
        return
    for cfg in configs:
        try:
            guild_id = int(cfg["guild_id"])
            views = getattr(bot, "verify_views", None)
            if views is not None and guild_id in views:
                continue
            view = VerifyPanelView(bot, guild_id)
            views[guild_id] = view
            message_id = (
                int(cfg["panel_message_id"]) if cfg.get("panel_message_id") else None
            )
            try:
                bot.add_view(view, message_id=message_id)
            except Exception:
                log.exception("Could not register verify view for guild %s", guild_id)
        except Exception:
            log.exception("Could not register verify views for guild %s", guild_id)


class VerifyCommands(commands.Cog, name="VerifyCommands"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.verify_views: dict = {}

    async def cog_load(self) -> None:
        try:
            await register_verify_views(self.bot)
        except Exception:
            log.exception("Could not register verify views in cog_load")

    verify_panel = app_commands.Group(
        name="verify-panel", description="Verification system for this server"
    )

    @verify_panel.command(name="setup", description="Sets up the verification panel")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        rolle="Role granted after verification",
        unverified_rolle="Lock role that new members receive on join",
        log_kanal="Channel for verification logs",
        willkommens_nachricht="Welcome message in the channel ({mention}, {user}, {id}, {guild}, {date}, {time})",
        dm_nachricht="Private message after verification ({user}, {guild}, {id}, {date}, {time})",
        bestehende_member_sperren="Also lock all existing members without the role (default: on)",
    )
    async def verify_panel_setup(
        self,
        interaction: discord.Interaction,
        rolle: discord.Role,
        unverified_rolle: discord.Role,
        log_kanal: Optional[discord.TextChannel] = None,
        willkommens_nachricht: Optional[str] = None,
        dm_nachricht: Optional[str] = None,
        bestehende_member_sperren: bool = True,
    ) -> None:
        guild_id = interaction.guild_id
        welcome = willkommens_nachricht or DEFAULT_WELCOME
        dm = dm_nachricht or DEFAULT_DM

        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        try:
            message, panel_channel = await self._deploy_panel(
                interaction, guild_id, rolle.id
            )
        except RuntimeError:
            await interaction.followup.send(
                "The panel can only be set up in a text channel.",
                ephemeral=True,
            )
            return
        except Exception:
            log.exception("Could not deploy verify panel (guild %s)", guild_id)
            await interaction.followup.send(
                "The panel could not be created.", ephemeral=True
            )
            return

        try:
            await self.bot.db.set_verify_config(
                guild_id,
                panel_channel_id=panel_channel.id,
                panel_message_id=message.id,
                verify_role_id=rolle.id,
                unverified_role_id=unverified_rolle.id,
                log_channel_id=log_kanal.id if log_kanal else None,
                welcome_message=welcome,
                dm_message=dm,
                enabled=True,
            )
        except Exception:
            log.exception("Could not save verify config (guild %s)", guild_id)
            await interaction.followup.send(
                "The configuration could not be saved.", ephemeral=True
            )
            return

        self._register_guild_panel_view(guild_id, message.id)

        locked = 0
        if bestehende_member_sperren:
            try:
                locked = await self._auto_lock_existing(interaction.guild, {
                    "verify_role_id": rolle.id,
                    "unverified_role_id": unverified_rolle.id,
                })
            except Exception:
                log.exception("Auto-lock failed (guild %s)", guild_id)

        log_text = log_kanal.mention if log_kanal else "None"
        confirm = discord.Embed(
            title="Verify panel set up",
            description=(
                f"Role: {rolle.mention}\n"
                f"Lock role: {unverified_rolle.mention}\n"
                f"Log channel: {log_text}\n"
                f"Existing members locked: **{locked}**"
            ),
            color=GREEN,
        )
        await interaction.followup.send(embed=confirm, ephemeral=True)

    @verify_panel.command(name="panel", description="Sends the verification panel again")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    async def verify_panel_resend(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        try:
            config = await self.bot.db.get_verify_config(guild_id)
        except Exception:
            log.exception("Could not load verify config (guild %s)", guild_id)
            await interaction.response.send_message(
                "The configuration could not be loaded.", ephemeral=True
            )
            return

        if config is None or not config.get("enabled"):
            await interaction.response.send_message(
                "The verification system is not set up. Use `/verify-panel setup` first.",
                ephemeral=True,
            )
            return

        try:
            message, panel_channel = await self._deploy_panel(
                interaction, guild_id, config.get("verify_role_id")
            )
        except RuntimeError:
            await interaction.response.send_message(
                "The panel can only be sent in a text channel.", ephemeral=True
            )
            return
        except Exception:
            log.exception("Could not redeploy verify panel (guild %s)", guild_id)
            await interaction.response.send_message(
                "The panel could not be sent.", ephemeral=True
            )
            return

        try:
            await self.bot.db.set_verify_config(
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

    @verify_panel.command(name="disable", description="Disables the verification system")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    async def verify_panel_disable(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        try:
            config = await self.bot.db.get_verify_config(guild_id)
        except Exception:
            log.exception("Could not load verify config (guild %s)", guild_id)
            await interaction.response.send_message(
                "The configuration could not be loaded.", ephemeral=True
            )
            return

        if config is None or not config.get("enabled"):
            await interaction.response.send_message(
                "The verification system is already disabled or not set up.",
                ephemeral=True,
            )
            return

        try:
            await self.bot.db.set_verify_config(guild_id, enabled=False)
        except Exception:
            log.exception("Could not disable verify config (guild %s)", guild_id)
            await interaction.response.send_message(
                "The verification system could not be disabled.",
                ephemeral=True,
            )
            return

        await self._disable_panel_message(config)

        embed = discord.Embed(
            title="Verification disabled",
            description="Verification has been disabled. Use `/verify-panel setup` to re-enable it.",
            color=RED,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @verify_panel.command(name="lock-all", description="Locks all existing members without the role")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    async def verify_panel_lock_all(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        try:
            config = await self.bot.db.get_verify_config(guild_id)
        except Exception:
            log.exception("Could not load verify config (guild %s)", guild_id)
            await interaction.followup.send(
                "The configuration could not be loaded.", ephemeral=True
            )
            return

        if config is None or not config.get("enabled"):
            await interaction.followup.send(
                "The verification system is not set up. Use `/verify-panel setup` first.",
                ephemeral=True,
            )
            return

        try:
            locked = await self._auto_lock_existing(interaction.guild, config)
        except Exception:
            log.exception("lock-all failed (guild %s)", guild_id)
            await interaction.followup.send(
                "The locking could not be completed.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Existing members locked",
            description=f"**{locked}** members received the lock role.",
            color=GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @verify_panel.command(name="config", description="Shows the current verification configuration")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    async def verify_panel_config(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        try:
            config = await self.bot.db.get_verify_config(guild_id)
        except Exception:
            log.exception("Could not load verify config (guild %s)", guild_id)
            await interaction.response.send_message(
                "The configuration could not be loaded.", ephemeral=True
            )
            return

        if config is None:
            await interaction.response.send_message(
                "The verification system is not set up. Use `/verify-panel setup`.",
                ephemeral=True,
            )
            return

        enabled = bool(config.get("enabled"))

        panel_channel = (
            self.bot.get_channel(int(config["panel_channel_id"]))
            if config.get("panel_channel_id")
            else None
        )
        guild = interaction.guild
        verify_role = (
            guild.get_role(int(config["verify_role_id"]))
            if config.get("verify_role_id")
            else None
        )
        unverified_role = (
            guild.get_role(int(config["unverified_role_id"]))
            if config.get("unverified_role_id")
            else None
        )
        log_channel = (
            self.bot.get_channel(int(config["log_channel_id"]))
            if config.get("log_channel_id")
            else None
        )

        embed = discord.Embed(
            title="Verify Configuration",
            description=f"{'🟢 **Enabled**' if enabled else '🔴 **Disabled**'}",
            color=GREEN,
        )
        embed.add_field(
            name="Panel channel",
            value=panel_channel.mention if panel_channel else "Unknown",
            inline=False,
        )
        embed.add_field(
            name="Role",
            value=verify_role.mention if verify_role else "Unknown",
            inline=False,
        )
        embed.add_field(
            name="Lock role",
            value=unverified_role.mention if unverified_role else "Unknown",
            inline=False,
        )
        embed.add_field(
            name="Log channel",
            value=log_channel.mention if log_channel else "None",
            inline=False,
        )
        welcome = config.get("welcome_message") or DEFAULT_WELCOME
        embed.add_field(
            name="Welcome message",
            value=f"```{welcome[:80]}{'…' if len(welcome) > 80 else ''}```",
            inline=False,
        )
        dm = config.get("dm_message") or DEFAULT_DM
        embed.add_field(
            name="DM message",
            value=f"```{dm[:80]}{'…' if len(dm) > 80 else ''}```",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # Button-Logik
    # ------------------------------------------------------------------

    async def do_verify(
        self, interaction: discord.Interaction, guild_id: int
    ) -> None:
        if interaction.guild is None:
            return
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        try:
            config = await self.bot.db.get_verify_config(guild_id)
        except Exception:
            log.exception("Could not load verify config (guild %s)", guild_id)
            await interaction.followup.send(
                "The verification system could not be loaded.", ephemeral=True
            )
            return

        if config is None or not config.get("enabled"):
            await interaction.followup.send(
                "Verification is disabled.", ephemeral=True
            )
            return

        guild = interaction.guild
        member = interaction.user

        verify_role_id = config.get("verify_role_id")
        verify_role = guild.get_role(int(verify_role_id)) if verify_role_id else None
        if verify_role is not None and verify_role in member.roles:
            await interaction.followup.send(
                "You are already verified!", ephemeral=True
            )
            return

        if verify_role is None:
            await interaction.followup.send(
                "The configured role was not found.", ephemeral=True
            )
            return

        try:
            await member.add_roles(verify_role, reason="Verified")
        except discord.Forbidden:
            await interaction.followup.send(
                "The bot does not have permission to assign roles.", ephemeral=True
            )
            return
        except Exception:
            log.exception("Could not add verify role (guild %s)", guild_id)
            await interaction.followup.send(
                "The role could not be assigned.", ephemeral=True
            )
            return

        unverified_id = config.get("unverified_role_id")
        if unverified_id:
            unverified_role = guild.get_role(int(unverified_id))
            if unverified_role is not None and unverified_role in member.roles:
                try:
                    await member.remove_roles(unverified_role, reason="Verified")
                except discord.Forbidden:
                    log.debug("Could not remove unverified role from %s", member.id)
                except Exception:
                    log.debug("Could not remove unverified role from %s", member.id, exc_info=True)

        try:
            await self.bot.db.log_verify_event(guild_id, member.id, "verified")
        except Exception:
            log.exception("Could not log verify event (guild %s)", guild_id)

        await self._send_verify_log(guild, member)

        await self._send_verify_dm(guild, member, config)

        role_text = verify_role.mention
        await interaction.followup.send(
            f"✅ You have been verified! Your role: {role_text}",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        try:
            cfg = await self.bot.db.get_verify_config(member.guild.id)
        except Exception:
            return
        if not cfg or not cfg.get("enabled"):
            return
        unverified_id = cfg.get("unverified_role_id")
        if not unverified_id:
            return
        role = member.guild.get_role(int(unverified_id))
        if role and role not in member.roles:
            try:
                await member.add_roles(role, reason="Unverified Lock")
                try:
                    await self.bot.db.log_verify_event(member.guild.id, member.id, "lock")
                except Exception:
                    log.debug("Could not log verify lock (guild %s)", member.guild.id)
            except discord.Forbidden:
                pass
            except Exception:
                log.debug("Could not lock new member %s", member.id, exc_info=True)

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
        in_dm: bool = False,
    ) -> Dict[str, str]:
        now = datetime.datetime.now()
        user_name = (user.global_name or user.name) if user else ""
        mention = user.mention if (user and not in_dm) else user_name
        return {
            "user": user_name or "user",
            "mention": mention,
            "id": str(user.id) if user else "",
            "guild": guild.name if guild else "",
            "date": now.strftime("%d.%m.%Y"),
            "time": now.strftime("%H:%M"),
        }

    async def _send_verify_log(
        self, guild: discord.Guild, member: discord.Member
    ) -> None:
        try:
            config = await self.bot.db.get_verify_config(guild.id)
        except Exception:
            return
        if not config or not config.get("log_channel_id"):
            return
        channel = guild.get_channel(int(config["log_channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return
        embed = discord.Embed(
            title="✅ Verified",
            description=f"{member.mention} has been verified.",
            color=GREEN,
        )
        embed.set_footer(text=f"ID: {member.id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            log.debug("Could not send verify log (guild %s)", guild.id, exc_info=True)

    async def _send_verify_dm(
        self,
        guild: discord.Guild,
        member: discord.Member,
        config: Dict[str, Any],
    ) -> None:
        dm_msg = config.get("dm_message")
        if not dm_msg:
            return
        if not member.dm_channel and not await self._can_dm(member):
            return
        text = self._render(
            dm_msg, **self._fields(member, guild, in_dm=True)
        )
        try:
            await member.send(text)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            log.debug("Could not send verify DM to %s", member.id)
        except Exception:
            log.debug("Could not send verify DM to %s", member.id, exc_info=True)

    async def _can_dm(self, member: discord.Member) -> bool:
        try:
            return (await member.create_dm()) is not None
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Auto-Lock
    # ------------------------------------------------------------------

    async def _auto_lock_existing(
        self, guild: discord.Guild, config: Dict[str, Any]
    ) -> int:
        if not guild.chunked:
            try:
                await guild.chunk()
            except Exception:
                log.debug("Could not chunk guild %s", guild.id)
        unverified_id = config.get("unverified_role_id")
        verify_id = config.get("verify_role_id")
        role = guild.get_role(int(unverified_id)) if unverified_id else None
        verify_role = guild.get_role(int(verify_id)) if verify_id else None
        if role is None:
            return 0
        count = 0
        for member in guild.members:
            if member.bot:
                continue
            if verify_role is not None and verify_role in member.roles:
                continue
            if role in member.roles:
                continue
            try:
                await member.add_roles(role, reason="Unverified Lock")
                count += 1
                try:
                    await self.bot.db.log_verify_event(guild.id, member.id, "lock")
                except Exception:
                    pass
                if count % 5 == 0:
                    await asyncio.sleep(1)
            except discord.Forbidden:
                continue
            except Exception:
                log.debug("Could not lock member %s", member.id, exc_info=True)
        return count

    # ------------------------------------------------------------------
    # Panel-Verwaltung
    # ------------------------------------------------------------------

    def _register_guild_panel_view(self, guild_id: int, message_id: int) -> None:
        old = self.bot.verify_views.pop(guild_id, None)
        if old is not None:
            _unregister_view(self.bot, old)
        view = VerifyPanelView(self.bot, guild_id)
        self.bot.verify_views[guild_id] = view
        try:
            self.bot.add_view(view, message_id=message_id)
        except Exception:
            log.exception("Could not register verify panel view (guild %s)", guild_id)

    async def _deploy_panel(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        verify_role_id: Optional[int],
    ) -> Any:
        config = await self.bot.db.get_verify_config(guild_id)
        embed = build_message(verify_role_id)
        if config and config.get("panel_channel_id") and config.get("panel_message_id"):
            try:
                channel = self.bot.get_channel(int(config["panel_channel_id"]))
                if isinstance(channel, discord.TextChannel):
                    message = await channel.fetch_message(
                        int(config["panel_message_id"])
                    )
                    view = VerifyPanelView(self.bot, guild_id)
                    await message.edit(embed=embed, view=view, attachments=[])
                    return message, channel
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                log.debug("Existing verify panel could not be edited", exc_info=True)
            except Exception:
                log.exception("Unexpected error editing verify panel")

        channel = interaction.channel
        if channel is None or not isinstance(channel, discord.TextChannel):
            raise RuntimeError("no_text_channel")
        view = VerifyPanelView(self.bot, guild_id)
        message = await channel.send(embed=embed, view=view)
        return message, channel

    async def _disable_panel_message(self, config: Dict[str, Any]) -> None:
        if not config.get("panel_channel_id") or not config.get("panel_message_id"):
            return
        channel = self.bot.get_channel(int(config["panel_channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(int(config["panel_message_id"]))
            embed = discord.Embed(
                title="🔴 Verification disabled",
                description="The verification system has been disabled.",
                color=GREY,
            )
            embed.set_footer(text="WordLock Verification")
            await message.edit(embed=embed, view=None)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            log.debug("Verify panel could not be edited", exc_info=True)
        except Exception:
            log.exception("Could not disable verify panel message")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VerifyCommands(bot))
