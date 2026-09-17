"""Unit tests for the WordLock self-protection / anti-nuke detection.

Run with:  python -m unittest tests.test_security
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from bot.events.security import (
    CHANNEL_NUKE_LIMIT,
    CHANNEL_NUKE_WINDOW,
    COMMAND_FLOOD_LIMIT,
    COMMAND_FLOOD_WINDOW,
    MENTION_FLOOD_LIMIT,
    MENTION_FLOOD_WINDOW,
    SecurityEvents,
)


class FakeBot:
    owner_ids: set = set()


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.cog = SecurityEvents(FakeBot())
        self.gid = 12345

    def _now(self, base, i):
        return base + i

    def test_command_flood_triggers_at_limit(self):
        triggered = False
        for i in range(COMMAND_FLOOD_LIMIT):
            triggered = self.cog._count(
                self.cog._commands, self.gid, self._now(1000.0, i),
                COMMAND_FLOOD_WINDOW, COMMAND_FLOOD_LIMIT,
            )
        self.assertTrue(triggered)

    def test_command_flood_below_limit_ok(self):
        for i in range(COMMAND_FLOOD_LIMIT - 1):
            self.assertFalse(
                self.cog._count(
                    self.cog._commands, self.gid, self._now(1000.0, i),
                    COMMAND_FLOOD_WINDOW, COMMAND_FLOOD_LIMIT,
                )
            )

    def test_count_expires_after_window(self):
        for i in range(COMMAND_FLOOD_LIMIT - 1):
            self.cog._count(
                self.cog._commands, self.gid, self._now(1000.0, i),
                COMMAND_FLOOD_WINDOW, COMMAND_FLOOD_LIMIT,
            )
        self.assertFalse(
            self.cog._count(
                self.cog._commands, self.gid,
                1000.0 + COMMAND_FLOOD_WINDOW + 1,
                COMMAND_FLOOD_WINDOW, COMMAND_FLOOD_LIMIT,
            )
        )

    def test_mention_flood_uses_own_thresholds(self):
        triggered = False
        for i in range(MENTION_FLOOD_LIMIT):
            triggered = self.cog._count(
                self.cog._mentions, self.gid, self._now(2000.0, i),
                MENTION_FLOOD_WINDOW, MENTION_FLOOD_LIMIT,
            )
        self.assertTrue(triggered)

    def test_channel_nuke_uses_own_thresholds(self):
        triggered = False
        for i in range(CHANNEL_NUKE_LIMIT):
            triggered = self.cog._count(
                self.cog._channels, self.gid, self._now(3000.0, i),
                CHANNEL_NUKE_WINDOW, CHANNEL_NUKE_LIMIT,
            )
        self.assertTrue(triggered)

    def test_handle_incident_disables_server_and_logs(self):
        guild = MagicMock()
        guild.id = self.gid
        guild.name = "Test Server"
        self.cog.bot.db = AsyncMock()
        self.cog.bot.filters = AsyncMock()
        self.cog.bot.owner_ids = set()

        async def _server_disabled(_gid):
            return False

        self.cog._server_disabled = _server_disabled

        import asyncio

        asyncio.run(
            self.cog._handle_incident(
                guild, "command_flood", actor_id=42, detail={"commands": 5}
            )
        )
        self.cog.bot.db.update_server.assert_awaited_once_with(self.gid, status="disabled")
        self.cog.bot.db.add_incident.assert_awaited()
        kwargs = self.cog.bot.db.add_incident.await_args.kwargs
        self.assertEqual(kwargs["guild_id"], self.gid)
        self.assertEqual(kwargs["kind"], "command_flood")

    def test_handle_incident_skips_when_already_disabled(self):
        guild = MagicMock()
        guild.id = self.gid
        self.cog.bot.db = AsyncMock()

        async def _server_disabled(_gid):
            return True

        self.cog._server_disabled = _server_disabled

        import asyncio

        asyncio.run(self.cog._handle_incident(guild, "channel_nuke"))
        self.cog.bot.db.add_incident.assert_not_awaited()

    def test_reset_clears_buckets(self):
        for i in range(COMMAND_FLOOD_LIMIT):
            self.cog._count(
                self.cog._commands, self.gid, self._now(1000.0, i),
                COMMAND_FLOOD_WINDOW, COMMAND_FLOOD_LIMIT,
            )
        self.cog._reset(self.gid)
        self.assertNotIn(self.gid, self.cog._commands)


if __name__ == "__main__":
    unittest.main()
