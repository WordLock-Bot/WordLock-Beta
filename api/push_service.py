"""Web Push (VAPID) delivery for WordLock security incidents.

The API polls for unprocessed incidents and sends a push notification to every
browser that subscribed via the dashboard (PWA on Android home screen).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from .database import Database

log = logging.getLogger("wordlock.api.push")

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:dev@wordlock.example")


def push_configured() -> bool:
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


async def send_incident_push(db: Database, incident: Dict[str, Any], guild_name: str) -> None:
    """Send one incident notification to all subscribed users."""
    if not push_configured():
        return
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        log.warning("pywebpush is not installed — push notifications disabled")
        return

    labels = {
        "command_flood": "Command flood",
        "mention_flood": "Mention flood",
        "channel_nuke": "Channel nuke attempt",
        "bot_banned": "Bot was banned",
        "bot_removed": "Bot was removed",
    }
    kind = incident.get("kind", "incident")
    if kind == "bot_removed":
        log.info("No push for incident kind 'bot_removed' (bot was removed normally)")
        return
    title = "🛡️ WordLock Sicherheitsalarm"
    body = (
        f"{guild_name}: {labels.get(kind, kind)}. "
        f"Bot wurde für diesen Server deaktiviert (Selbstschutz)."
    )
    payload = {
        "title": title,
        "body": body,
        "icon": "/icon-192.png",
        "url": "/admin/incidents",
    }

    subs = await db.all_push_subscriptions()
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": json.loads(sub["keys"]) if isinstance(sub["keys"], str) else sub["keys"],
                },
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
                timeout=10,
            )
        except WebPushException as exc:
            # 404/410 = subscription gone
            if getattr(exc.response, "status_code", None) in (404, 410):
                await db.remove_push_subscription(sub["user_id"], sub["endpoint"])
            else:
                log.debug("Push failed for %s: %s", sub["endpoint"], exc)
        except Exception:
            log.exception("Unexpected push error")


async def process_pending(db: Database, batch: int = 50) -> int:
    """Send pushes for all open, unpushed incidents. Returns count sent."""
    incidents = await db.unprocessed_incidents(batch)
    sent = 0
    for incident in incidents:
        server = await db.get_server(incident["guild_id"])
        guild_name = (server or {}).get("name") or str(incident["guild_id"])
        try:
            await send_incident_push(db, incident, guild_name)
        finally:
            await db.mark_incident_pushed(incident["id"])
            sent += 1
    return sent


async def send_test_push(db: Database, user_id: int) -> int:
    """Send a test notification to a user's own push subscriptions.

    Returns the number of subscriptions the notification was sent to.
    """
    subs = await db.push_subscriptions_for_user(user_id)
    if not subs:
        return 0
    if not push_configured():
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        log.warning("pywebpush is not installed — push notifications disabled")
        return 0

    payload = {
        "title": "✅ WordLock test notification",
        "body": "Push-Notifications funktionieren. 🎉",
        "icon": "/icon-192.png",
        "url": "/",
    }

    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": json.loads(sub["keys"]) if isinstance(sub["keys"], str) else sub["keys"],
                },
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
                timeout=10,
            )
            sent += 1
        except WebPushException as exc:
            if getattr(exc.response, "status_code", None) in (404, 410):
                await db.remove_push_subscription(user_id, sub["endpoint"])
            else:
                log.debug("Test push failed for %s: %s", sub["endpoint"], exc)
        except Exception:
            log.exception("Unexpected push error")
    return sent


async def send_test_push_all_admins(db: Database) -> int:
    """Send a test notification to every WordLock staff member's devices.

    Returns the number of subscriptions the notification was sent to.
    """
    subs = await db.admin_push_subscriptions()
    if not subs:
        return 0
    if not push_configured():
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        log.warning("pywebpush is not installed — push notifications disabled")
        return 0

    payload = {
        "title": "✅ WordLock Admin-Test",
        "body": "Test-Push an alle Admin-Geräte wurde zugestellt. 🎉",
        "icon": "/icon-192.png",
        "url": "/admin",
    }

    sent = 0
    for sub in subs:
        user_id = sub["user_id"]
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": json.loads(sub["keys"]) if isinstance(sub["keys"], str) else sub["keys"],
                },
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
                timeout=10,
            )
            sent += 1
        except WebPushException as exc:
            if getattr(exc.response, "status_code", None) in (404, 410):
                await db.remove_push_subscription(user_id, sub["endpoint"])
            else:
                log.debug("Admin test push failed for %s: %s", sub["endpoint"], exc)
        except Exception:
            log.exception("Unexpected push error")
    return sent
