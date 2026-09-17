"""Geplante Nachrichten für WordLock."""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
import re
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("wordlock.scheduled_messages")

GREEN = 0x57F287
RED = 0xED4245

SCHED_TZ = os.environ.get("SCHED_TZ", "Europe/Berlin")

DAILY_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


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


class ScheduledMessages(commands.Cog, name="ScheduledMessages"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task: Optional[asyncio.Task] = None
        self._started = False

    async def cog_load(self) -> None:
        if not self._started:
            self._started = True
            self._task = self.bot.loop.create_task(self._scheduler_loop())

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    async def _scheduler_loop(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._process_due()
            except Exception:
                log.exception("Scheduler loop iteration failed")
            await asyncio.sleep(60)

    async def _process_due(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            rows = await self.bot.db.due_scheduled_messages(now)
        except Exception:
            log.exception("Could not load due scheduled messages")
            return
        for row in rows:
            try:
                await self._send(row, now)
            except Exception:
                log.exception("Could not send scheduled message %s", row["id"])

    async def _send(self, row: dict, now: datetime.datetime) -> None:
        guild = self.bot.get_guild(int(row["guild_id"]))
        if guild is None:
            await self.bot.db.update_scheduled_message(int(row["id"]), enabled=False)
            return

        server = await self.bot.db.get_server(guild.id)
        if not server or server.get("status") != "active":
            return

        channel = guild.get_channel(int(row["channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            await self.bot.db.update_scheduled_message(int(row["id"]), enabled=False)
            return
        perms = channel.permissions_for(guild.me)
        if not (perms.send_messages and perms.read_messages):
            await self.bot.db.update_scheduled_message(int(row["id"]), enabled=False)
            return

        await channel.send(row["content"])

        msg_id = int(row["id"])
        if row.get("interval_minutes"):
            run_at = now + datetime.timedelta(minutes=int(row["interval_minutes"]))
            await self.bot.db.update_scheduled_message(msg_id, run_at=run_at)
        elif row.get("daily_hhmm"):
            tz = self._tz()
            hour, minute = map(int, row["daily_hhmm"].split(":"))
            local_now = now.astimezone(tz)
            next_run = local_now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if next_run <= local_now:
                next_run += datetime.timedelta(days=1)
            await self.bot.db.update_scheduled_message(msg_id, run_at=next_run)
        else:
            await self.bot.db.update_scheduled_message(msg_id, enabled=False)

    def _tz(self) -> Any:
        try:
            return ZoneInfo(SCHED_TZ)
        except Exception:
            return datetime.timezone.utc

    def _utc_now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)

    # ------------------------------------------------------------------
    # Befehle
    # ------------------------------------------------------------------

    scheduled = app_commands.Group(
        name="scheduled", description="Scheduled messages on this server"
    )

    @scheduled.command(name="add", description="Schedules an automatic message")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        kanal="Channel where the message will be sent",
        text="Message text (max. 2000 characters)",
        intervall="Interval in minutes (e.g. 3600 = hourly)",
        taeglich_um="Daily at a specific time (HH:MM) – alternative to the interval",
    )
    async def scheduled_add(
        self,
        interaction: discord.Interaction,
        kanal: discord.TextChannel,
        text: str,
        intervall: int = 3600,
        taeglich_um: Optional[str] = None,
    ) -> None:
        text = text.strip()
        if not text or len(text) > 2000:
            await interaction.response.send_message(
                "The message text must be between 1 and 2000 characters long.",
                ephemeral=True,
            )
            return

        daily = None
        if taeglich_um:
            daily = self._parse_daily(taeglich_um)
            if daily is None:
                await interaction.response.send_message(
                    "`taeglich_um` must be a valid time in the format **HH:MM**.",
                    ephemeral=True,
                )
                return

        try:
            if daily:
                row = await self.bot.db.create_scheduled_message(
                    guild_id=interaction.guild_id,
                    channel_id=kanal.id,
                    content=text,
                    daily_hhmm=daily,
                    created_by=interaction.user.id,
                )
            elif intervall and intervall > 0:
                row = await self.bot.db.create_scheduled_message(
                    guild_id=interaction.guild_id,
                    channel_id=kanal.id,
                    content=text,
                    interval_minutes=intervall,
                    run_at=self._utc_now()
                    + datetime.timedelta(minutes=intervall),
                    created_by=interaction.user.id,
                )
            else:
                row = await self.bot.db.create_scheduled_message(
                    guild_id=interaction.guild_id,
                    channel_id=kanal.id,
                    content=text,
                    run_at=None,
                    created_by=interaction.user.id,
                )
        except Exception:
            log.exception("Could not create scheduled message (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "The message could not be scheduled.", ephemeral=True
            )
            return

        if row is None:
            await interaction.response.send_message(
                "The message could not be scheduled.", ephemeral=True
            )
            return

        summary = daily if daily else f"Every {intervall} minutes" if intervall and intervall > 0 else "Once"
        embed = discord.Embed(
            title="Message scheduled",
            description=(
                f"**ID:** {row['id']}\n"
                f"**Channel:** {kanal.mention}\n"
                f"**Schedule:** {summary}"
            ),
            color=GREEN,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @scheduled.command(name="list", description="Shows all scheduled messages")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    async def scheduled_list(self, interaction: discord.Interaction) -> None:
        try:
            rows = await self.bot.db.list_scheduled_messages(interaction.guild_id)
        except Exception:
            log.exception("Could not list scheduled messages (guild %s)", interaction.guild_id)
            await interaction.response.send_message(
                "The scheduled messages could not be loaded.", ephemeral=True
            )
            return

        embed = discord.Embed(title="Scheduled Messages", color=GREEN)
        if not rows:
            embed.description = "No scheduled messages."
        for row in rows[:25]:
            channel = interaction.guild.get_channel(int(row["channel_id"]))
            channel_text = channel.mention if isinstance(channel, discord.TextChannel) else "Unknown"
            content = row["content"] or ""
            preview = content[:60] + ("…" if len(content) > 60 else "")
            state = "✅" if row["enabled"] else "❌"
            embed.add_field(
                name=f"#{row['id']} – {state}",
                value=f"{channel_text}\n`{preview}`\n{self._schedule_text(row)}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @scheduled.command(name="remove", description="Removes a scheduled message")
    @manage_guild()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(id="ID of the scheduled message (see `/scheduled list`)")
    async def scheduled_remove(self, interaction: discord.Interaction, id: int) -> None:
        try:
            removed = await self.bot.db.delete_scheduled_message(id, interaction.guild_id)
        except Exception:
            log.exception("Could not delete scheduled message %s (guild %s)", id, interaction.guild_id)
            await interaction.response.send_message(
                "The message could not be removed.", ephemeral=True
            )
            return

        if removed:
            embed = discord.Embed(
                title="Message removed",
                description=f"The scheduled message **#{id}** was deleted.",
                color=GREEN,
            )
        else:
            embed = discord.Embed(
                title="Not found",
                description=f"No scheduled message with the ID **{id}** was found.",
                color=RED,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # Helfer
    # ------------------------------------------------------------------

    def _parse_daily(self, value: str) -> Optional[str]:
        match = DAILY_RE.match(value.strip())
        if not match:
            return None
        hour = int(match.group(1))
        minute = int(match.group(2))
        if hour > 23 or minute > 59:
            return None
        return f"{hour:02d}:{minute:02d}"

    def _schedule_text(self, row: dict) -> str:
        if row.get("daily_hhmm"):
            return f"Daily at {row['daily_hhmm']}"
        if row.get("interval_minutes"):
            return f"Every {row['interval_minutes']} minutes"
        return "Once"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ScheduledMessages(bot))