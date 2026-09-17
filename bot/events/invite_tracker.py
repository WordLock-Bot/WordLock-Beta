"""Einladungs-Tracking für WordLock."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict

import discord
from discord.ext import commands

log = logging.getLogger("wordlock.invite_tracker")

REFRESH_INTERVAL = 300


class InviteTracker(commands.Cog, name="InviteTracker"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cache: Dict[int, Dict[str, int]] = {}

    async def cog_load(self) -> None:
        self.bot.loop.create_task(self._refresh_loop())

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    async def _cache_guild(self, guild: discord.Guild) -> None:
        try:
            invites = await guild.invites()
        except (discord.Forbidden, discord.HTTPException):
            self._cache[guild.id] = {}
            return
        self._cache[guild.id] = {i.code: (i.uses or 0) for i in invites}

    async def _refresh_loop(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                for guild in self.bot.guilds:
                    try:
                        await self._cache_guild(guild)
                    except Exception:
                        log.debug("Could not cache invites (guild %s)", guild.id, exc_info=True)
                    await asyncio.sleep(1)
            except Exception:
                log.exception("Invite refresh loop iteration failed")
            await asyncio.sleep(REFRESH_INTERVAL)

    # ------------------------------------------------------------------
    # Listener
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        try:
            await self._cache_guild(guild)
        except Exception:
            log.debug("Could not cache invites on join (guild %s)", guild.id, exc_info=True)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            try:
                await self._cache_guild(guild)
            except Exception:
                log.debug("Could not cache invites on ready (guild %s)", guild.id, exc_info=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        old = self._cache.get(member.guild.id)
        try:
            invites = await member.guild.invites()
        except (discord.Forbidden, discord.HTTPException):
            return

        current = {i.code: (i.uses or 0) for i in invites}
        self._cache[member.guild.id] = current
        if not old:
            return

        best = None
        best_delta = 0
        for invite in invites:
            old_uses = old.get(invite.code)
            if old_uses is None:
                continue
            delta = (invite.uses or 0) - old_uses
            if delta > best_delta:
                best_delta = delta
                best = invite

        if best is None or best.inviter is None:
            return

        try:
            await self.bot.db.record_invite(member.guild.id, best.inviter.id, member.id)
        except Exception:
            log.debug("Could not record invite (guild %s)", member.guild.id, exc_info=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InviteTracker(bot))