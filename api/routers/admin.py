"""Developer admin panel endpoints (protected by admin roles)."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .. import auth, profile_service
from ..database import (
    DEFAULT_ANTI_NUKE_CONFIG,
    DEFAULT_ANTI_SPAM_CONFIG,
    Database,
    merge_anti_config,
)
from ..version import __version__

router = APIRouter(prefix="/api/admin", tags=["admin"])

WORD_ACTIONS = ["delete", "warn", "timeout", "log"]

DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent.parent.parent / "data")))
ROLE_LEVELS = {"moderator": 1, "developer": 2, "owner": 3}


def get_db(request: Request) -> Database:
    return request.app.state.db


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get("/overview")
async def overview(request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    database = "connected"
    try:
        async with db._pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        database = "unreachable"

    bot = "offline"
    last_hb = await db.last_heartbeat()
    if last_hb:
        age = time.time() - last_hb
        bot = "online" if age < 120 else "offline"

    return {
        "servers": await db.server_count(),
        "active_servers": await db.active_server_count(),
        "active_users": await db.active_users(),
        "violations_today": await db.violations_today(),
        "violations_total": await db.violations_total(),
        "error_count": await db.error_count(),
        "version": __version__,
        "maintenance_mode": await db.maintenance_mode(),
        "open_tickets": await db.open_ticket_count(),
        "started_at": getattr(request.app.state, "started_at", None),
        "last_updates": await db.list_updates(5),
        "status": {
            "bot": bot,
            "api": "online",
            "database": database,
        },
    }


# ---------------------------------------------------------------------------
# Servers
# ---------------------------------------------------------------------------


@router.get("/servers")
async def servers(request: Request, _user=Depends(auth.require_admin)):
    return await get_db(request).all_servers()


@router.get("/history/servers")
async def guild_history(request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    await db.backfill_guild_history()
    return {
        "total": await db.guild_history_total(),
        "active": await db.guild_history_active(),
        "entries": await db.list_guild_history(),
    }


@router.get("/servers/{guild_id}")
async def server_detail(guild_id: int, request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    server = await db.get_server(guild_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    server["anti_spam_config"] = merge_anti_config(
        server.get("anti_spam_config"), DEFAULT_ANTI_SPAM_CONFIG
    )
    server["anti_nuke_config"] = merge_anti_config(
        server.get("anti_nuke_config"), DEFAULT_ANTI_NUKE_CONFIG
    )
    return {
        **server,
        "words": await db.get_custom_words(guild_id, enabled_only=False),
        "logs": await db.get_logs(guild_id=guild_id, limit=20),
        "violations": await db.violations_series(guild_id, 30),
        "top_words": await db.violations_top_words(guild_id, 10),
        "incidents": await db.list_incidents(guild_id=guild_id, limit=10),
        "violations_total": await db.violations_total(guild_id),
    }


@router.patch("/servers/{guild_id}")
async def server_action(
    guild_id: int, payload: dict, request: Request, _user=Depends(auth.require_admin)
):
    db = get_db(request)
    if not await db.get_server(guild_id):
        raise HTTPException(status_code=404, detail="Server not found")
    allowed = {
        "status",
        "maintenance",
        "bypass_privileged",
        "language",
        "mod_level",
        "log_channel_id",
        "timeout_minutes",
        "action_delete",
        "action_warn",
        "action_timeout",
        "action_log",
        "default_lists",
        "bypass_roles",
        "bypass_users",
        "std_word_action",
        "anti_spam_enabled",
        "anti_nuke_enabled",
        "anti_spam_config",
        "anti_nuke_config",
    }
    updates = {k: v for k, v in payload.items() if k in allowed}
    if "status" in updates and updates["status"] not in (
        "active",
        "disabled",
        "maintenance",
    ):
        raise HTTPException(status_code=400, detail="Invalid status")
    if "mod_level" in updates and updates["mod_level"] not in range(1, 6):
        raise HTTPException(status_code=400, detail="Invalid mod_level")
    if "anti_spam_config" in updates:
        updates["anti_spam_config"] = merge_anti_config(
            updates["anti_spam_config"], DEFAULT_ANTI_SPAM_CONFIG
        )
    if "anti_nuke_config" in updates:
        updates["anti_nuke_config"] = merge_anti_config(
            updates["anti_nuke_config"], DEFAULT_ANTI_NUKE_CONFIG
        )
    if updates:
        await db.update_server(guild_id, **updates)
        await db.add_log(
            "admin",
            f"Updated server {guild_id}: {', '.join(updates.keys())}",
            "info",
            guild_id=guild_id,
        )
    return await db.get_server(guild_id)


@router.get("/servers/{guild_id}/words")
async def admin_guild_words(guild_id: int, request: Request, _user=Depends(auth.require_admin)):
    return await get_db(request).get_custom_words(guild_id, enabled_only=False)


@router.post("/servers/{guild_id}/words")
async def admin_add_word(guild_id: int, payload: dict, request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    if not await db.get_server(guild_id):
        raise HTTPException(status_code=404, detail="Server not found")
    word = (payload.get("word") or "").strip().lower()
    if not word or len(word) > 100:
        raise HTTPException(status_code=400, detail="Invalid word")
    category = payload.get("category", "custom")
    severity = int(payload.get("severity", 3))
    action = payload.get("action", "delete")
    if severity not in range(1, 6):
        raise HTTPException(status_code=400, detail="Severity must be 1-5")
    if action not in WORD_ACTIONS:
        raise HTTPException(status_code=400, detail="Invalid action")
    ok = await db.add_custom_word(guild_id, word, category, severity, action)
    if not ok:
        raise HTTPException(status_code=400, detail="Could not add word")
    await db.add_log("admin", f"Added word '{word}' on server {guild_id}", "info", guild_id=guild_id)
    return {"ok": True, "word": word}


@router.delete("/servers/{guild_id}/words/{word}")
async def admin_delete_word(guild_id: int, word: str, request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    ok = await db.remove_custom_word(guild_id, word.lower())
    if not ok:
        raise HTTPException(status_code=404, detail="Word not found")
    await db.add_log("admin", f"Removed word '{word}' on server {guild_id}", "info", guild_id=guild_id)
    return {"ok": True}


@router.patch("/servers/{guild_id}/words/{word}/enabled")
async def admin_toggle_word(guild_id: int, word: str, payload: dict, request: Request, _user=Depends(auth.require_admin)):
    enabled = bool(payload.get("enabled"))
    await get_db(request).set_custom_word_enabled(guild_id, word.lower(), enabled)
    return {"ok": True, "enabled": enabled}


INVITE_TTL = timedelta(days=7)


async def _get_or_create_invite(db: Database, guild_id: int, server: dict) -> dict:
    """Return a valid stored invite, or generate + store a fresh one (7 days)."""
    stored = await db.get_invite(guild_id)
    if stored:
        expires = stored["expires_at"]
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if expires > datetime.now(timezone.utc):
            return {
                "url": stored["url"],
                "channel": None,
                "expires_at": stored["expires_at"],
            }
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="DISCORD_TOKEN not configured")
    headers = {"Authorization": f"Bot {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{auth.DISCORD_API}/guilds/{guild_id}/channels",
            headers=headers,
            timeout=15,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Could not load channels")
        channels = [c for c in resp.json() if c.get("type") in (0, 5)]
        if not channels:
            raise HTTPException(status_code=400, detail="No usable text channel found")
        preferred = str(server.get("log_channel_id") or "")
        channel = next(
            (c for c in channels if c["id"] == preferred), channels[0]
        )
        inv = await client.post(
            f"{auth.DISCORD_API}/channels/{channel['id']}/invites",
            headers=headers,
            json={
                "max_age": int(INVITE_TTL.total_seconds()),
                "max_uses": 0,
                "temporary": False,
            },
            timeout=15,
        )
        if inv.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Could not create invite: {inv.text[:200]}",
            )
        code = inv.json().get("code")
    url = f"https://discord.gg/{code}"
    expires_at = datetime.now(timezone.utc) + INVITE_TTL
    await db.save_invite(guild_id, code, url, int(channel["id"]), expires_at)
    await db.add_log(
        "admin",
        f"Invite generated for server {guild_id} ({server.get('name')})",
        "info",
    )
    return {"url": url, "channel": channel.get("name"), "expires_at": expires_at.isoformat()}


@router.get("/servers/{guild_id}/invite")
async def get_invite(guild_id: int, request: Request, _user=Depends(auth.require_developer)):
    """Return the current valid invite for a server (auto-renews when expired)."""
    db = get_db(request)
    server = await db.get_server(guild_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return await _get_or_create_invite(db, guild_id, server)


@router.post("/servers/{guild_id}/invite")
async def generate_invite(guild_id: int, request: Request, _user=Depends(auth.require_developer)):
    """(Re)generate a Discord invite link for a server (admin action)."""
    db = get_db(request)
    server = await db.get_server(guild_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    await db.delete_invite(guild_id)
    return await _get_or_create_invite(db, guild_id, server)


@router.get("/servers/{guild_id}/channels")
async def server_channels(guild_id: int, request: Request, _user=Depends(auth.require_admin)):
    """List the server's text channels via the Discord API (for broadcasting)."""
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="DISCORD_TOKEN not configured")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{auth.DISCORD_API}/guilds/{guild_id}/channels",
            headers={"Authorization": f"Bot {token}"},
            timeout=15,
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Discord API error {resp.status_code}: {resp.text[:200]}",
        )
    channels = [
        {
            "id": str(c["id"]),
            "name": c.get("name", ""),
            "type": c.get("type", 0),
        }
        for c in resp.json()
        if c.get("type") in (0, 5)
    ]
    return {"channels": channels}


@router.post("/servers/{guild_id}/announce")
async def server_announce(
    guild_id: int, payload: dict, request: Request, _user=Depends(auth.require_admin)
):
    """Send a message to a server channel as the bot (admin broadcast)."""
    db = get_db(request)
    server = await db.get_server(guild_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    channel_id = payload.get("channel_id")
    if not channel_id:
        channel_id = server.get("log_channel_id")
    if not channel_id:
        raise HTTPException(status_code=400, detail="No channel selected")
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="DISCORD_TOKEN not configured")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{auth.DISCORD_API}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            json={"content": message[:2000]},
            timeout=15,
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Discord API error {resp.status_code}: {resp.text[:200]}",
        )
    await db.add_log(
        "admin",
        f"Broadcast to server {guild_id} (channel {channel_id})",
        "info",
        guild_id=guild_id,
    )
    return {"ok": True}


@router.post("/servers/{guild_id}/kick")
async def remove_bot(guild_id: int, request: Request, _user=Depends(auth.require_developer)):
    """Make the bot leave a guild immediately (admin action)."""
    db = get_db(request)
    server = await db.get_server(guild_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="DISCORD_TOKEN not configured")
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{auth.DISCORD_API}/guilds/{guild_id}",
            headers={"Authorization": f"Bot {token}"},
            timeout=15,
        )
    if resp.status_code not in (204, 404):
        raise HTTPException(
            status_code=502,
            detail=f"Discord API error {resp.status_code}: {resp.text[:200]}",
        )
    await db.delete_server(guild_id)
    await db.add_log("admin", f"Bot removed from server {guild_id}", "info")
    return {"ok": True, "guild_id": guild_id}


@router.post("/servers/{guild_id}/force-remove")
async def force_remove(guild_id: int, request: Request, _user=Depends(auth.require_developer)):
    """Delete a server and ALL its data - as if the bot was never invited.

    Does not call Discord; it only wipes the database entries (server config,
    custom words, overrides, violations, incidents, logs, invites).
    """
    db = get_db(request)
    if not await db.get_server(guild_id):
        raise HTTPException(status_code=404, detail="Server not found")
    await db.force_remove_server(guild_id)
    await db.add_log(
        "admin", f"Server {guild_id} force-removed (all data deleted)", "info"
    )
    return {"ok": True, "guild_id": guild_id}


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


@router.get("/stats")
async def stats(
    request: Request,
    days: int = Query(30, le=90),
    _user=Depends(auth.require_admin),
):
    db = get_db(request)
    return {
        "violations_series": await db.violations_series(days=days),
        "server_growth": await db.server_growth(days),
        "action_counts": await db.action_counts(),
        "top_words": await db.violations_top_words(limit=15),
        "per_guild": await db.guild_violation_counts(),
        "servers": await db.server_count(),
        "active_users": await db.active_users(),
        "violations_total": await db.violations_total(),
    }


@router.get("/verify")
async def verify_stats(request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    overview = await db.verify_overview()
    total = await db._fetchval("SELECT COUNT(*) FROM verify_events")
    return {**overview, "total": int(total or 0)}


@router.get("/invites")
async def invite_stats(request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    lb = await db.invite_leaderboard(days=30)
    total = await db._fetchval("SELECT COUNT(*) FROM invite_track")
    return {"leaderboard": lb, "total": int(total or 0)}


@router.get("/security")
async def security_overview(request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    staff = await db._fetch(
        "SELECT discord_id, role FROM users WHERE role IN ('owner','developer','moderator') ORDER BY role, discord_id"
    )
    whitelist = [int(i) for i in os.environ.get("ADMIN_WHITELIST_IDS", "").split(",") if i.strip()]
    role = auth._effective_role(_user)
    return {
        "staff": staff,
        "whitelist_ids": whitelist if role != "moderator" else [],
        "maintenance_mode": await db.maintenance_mode(),
        "push_subscribers": int((await db._fetchval("SELECT COUNT(*) FROM push_subscriptions")) or 0),
        "incidents": await db._fetch(
            "SELECT id, guild_id, kind, severity, status, created_at FROM incidents ORDER BY created_at DESC LIMIT 15"
        ),
    }


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


@router.get("/logs")
async def logs(
    request: Request,
    level: Optional[str] = None,
    log_type: Optional[str] = None,
    limit: int = Query(200, le=1000),
    _user=Depends(auth.require_developer),
):
    return await get_db(request).get_logs(level, log_type, limit)


# ---------------------------------------------------------------------------
# Updates / release management
# ---------------------------------------------------------------------------


@router.get("/updates")
async def list_updates(request: Request, _user=Depends(auth.require_developer)):
    return await get_db(request).list_updates(50)


@router.post("/updates")
async def create_update(payload: dict, request: Request, _user=Depends(auth.require_developer)):
    db = get_db(request)
    version = (payload.get("version") or "").strip()
    title = (payload.get("title") or "").strip()
    if not version or not title:
        raise HTTPException(status_code=400, detail="version and title are required")
    return await db.add_update(
        version=version,
        title=title,
        changelog=payload.get("changelog"),
        maintenance_mode=bool(payload.get("maintenance_mode")),
    )


@router.post("/updates/release")
async def release_update(payload: dict, request: Request, _user=Depends(auth.require_developer)):
    """Publish a new version. Optionally pings a deploy webhook that redeploys
    all bot instances (e.g. Vercel/CI pipeline)."""
    db = get_db(request)
    version = (payload.get("version") or "").strip()
    title = (payload.get("title") or "").strip()
    if not version or not title:
        raise HTTPException(status_code=400, detail="version and title are required")
    row = await db.add_update(
        version=version,
        title=title,
        changelog=payload.get("changelog"),
        maintenance_mode=bool(payload.get("maintenance_mode")),
        kind="release",
    )
    deploy_url = os.environ.get("DEPLOY_WEBHOOK_URL")
    deploy_result = "not_configured"
    if deploy_url:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    deploy_url,
                    json={"version": version, "title": title},
                    timeout=10,
                )
                deploy_result = f"http_{r.status_code}"
        except httpx.HTTPError:
            deploy_result = "failed"
    await db.add_log(
        "updates", f"Released {version}: {title}", "info"
    )
    return {**row, "deploy": deploy_result}


# ---------------------------------------------------------------------------
# Word lists (global, developer managed)
# ---------------------------------------------------------------------------


@router.get("/lists")
async def list_languages(request: Request, _user=Depends(auth.require_developer)):
    result = []
    for f in sorted(DATA_DIR.glob("default_words_*.json")):
        with f.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        meta = data.get("meta", {})
        result.append(
            {
                "language": meta.get("language"),
                "name": meta.get("name"),
                "version": meta.get("version"),
                "word_count": len(data.get("words", [])),
            }
        )
    return result


@router.get("/lists/{language}")
async def get_language_list(language: str, request: Request, _user=Depends(auth.require_developer)):
    path = DATA_DIR / f"default_words_{language}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Language not found")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@router.put("/lists/{language}")
async def update_language_list(
    language: str, payload: dict, request: Request, _user=Depends(auth.require_developer)
):
    words = payload.get("words")
    if not isinstance(words, list):
        raise HTTPException(status_code=400, detail="words must be a list")
    for w in words:
        if not w.get("word") or not w.get("category"):
            raise HTTPException(status_code=400, detail="Each word needs word + category")
    path = DATA_DIR / f"default_words_{language}.json"
    meta = payload.get("meta") or {}
    version = meta.get("version", "1.0.0")
    doc = {
        "meta": {
            "language": language,
            "name": meta.get("name", f"{language} list"),
            "version": version,
            "description": meta.get("description", ""),
        },
        "words": words,
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    db = get_db(request)
    await db.add_log(
        "wordlists",
        f"Updated {language} word list (v{version}, {len(words)} words)",
        "info",
    )
    return {"ok": True, "word_count": len(words), "version": version}


# ---------------------------------------------------------------------------
# Developers / roles
# ---------------------------------------------------------------------------


@router.get("/users")
async def list_developers(request: Request, _user=Depends(auth.require_developer)):
    return await get_db(request).list_developers()


@router.patch("/users/{discord_id}")
async def set_role(
    discord_id: int, payload: dict, request: Request, _user=Depends(auth.require_owner)
):
    db = get_db(request)
    role = payload.get("role")
    if role not in ROLE_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = await db.get_user(discord_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.set_user_role(discord_id, role)
    await db.add_log("admin", f"Set role {role} for user {discord_id}", "info")
    return {"ok": True, "role": role}


# ---------------------------------------------------------------------------
# Team (public landing page hierarchy)
# ---------------------------------------------------------------------------


@router.get("/team")
async def list_team(request: Request, _user=Depends(auth.require_developer)):
    return await get_db(request).list_team()


@router.post("/team")
async def add_team_member(payload: dict, request: Request, _user=Depends(auth.require_developer)):
    db = get_db(request)
    name = (payload.get("name") or "").strip()
    role = (payload.get("role") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    sort_order = int(payload.get("sort_order") or 0)
    discord_id = payload.get("discord_id")
    if discord_id:
        discord_id = int(discord_id)
    panel_access = bool(payload.get("panel_access"))
    member = await db.add_team_member(
        name, role, payload.get("parent_id"), sort_order,
        discord_id=discord_id, panel_access=panel_access,
    )
    await db.add_log("admin", f"Added team member {name}", "info")
    return member


@router.put("/team/{member_id}")
async def update_team_member(
    member_id: int, payload: dict, request: Request, _user=Depends(auth.require_developer)
):
    db = get_db(request)
    fields = {
        k: v for k, v in payload.items()
        if k in {"name", "role", "parent_id", "sort_order", "discord_id", "panel_access"}
    }
    if "name" in fields:
        fields["name"] = (fields["name"] or "").strip()
        if not fields["name"]:
            raise HTTPException(status_code=400, detail="name is required")
    if "sort_order" in fields:
        fields["sort_order"] = int(fields["sort_order"] or 0)
    if "discord_id" in fields:
        fields["discord_id"] = int(fields["discord_id"]) if fields["discord_id"] else None
    if "panel_access" in fields:
        fields["panel_access"] = bool(fields["panel_access"])
    if fields.get("parent_id") == member_id:
        raise HTTPException(status_code=400, detail="Member cannot be its own parent")
    if not fields:
        raise HTTPException(status_code=400, detail="No valid fields provided")
    member = await db.update_team_member(member_id, **fields)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.delete("/team/{member_id}")
async def delete_team_member(
    member_id: int, request: Request, _user=Depends(auth.require_developer)
):
    db = get_db(request)
    if not await db.delete_team_member(member_id):
        raise HTTPException(status_code=404, detail="Member not found")
    await db.add_log("admin", f"Removed team member {member_id}", "info")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Bot avatar (moderation / override / reset)
# ---------------------------------------------------------------------------


@router.get("/profile")
async def admin_profile(request: Request, _user=Depends(auth.require_developer)):
    """Current bot profile + change history (for moderation)."""
    db = get_db(request)
    return {
        "profile": await db.get_bot_profile(),
        "history": await db.get_profile_history(50),
    }


@router.post("/profile/apply")
async def admin_profile_apply(payload: dict, request: Request, _user=Depends(auth.require_owner)):
    """Bot admin overrides the bot avatar (e.g. after an offensive upload)."""
    db = get_db(request)
    avatar = payload.get("avatar")
    if not avatar:
        raise HTTPException(status_code=400, detail="avatar is required")
    stored = await profile_service.apply_and_store(db, avatar, _user["discord_id"])
    return {"ok": True, "avatar": stored.get("avatar")}


@router.post("/profile/reset")
async def admin_profile_reset(request: Request, _user=Depends(auth.require_owner)):
    """Reset the bot avatar back to the WordLock default (no picture)."""
    db = get_db(request)
    stored = await profile_service.apply_and_store(db, None, _user["discord_id"])
    return {"ok": True, "avatar": stored.get("avatar")}


# ---------------------------------------------------------------------------
# Downtime monitor (API/backend + bot) — state + mute for current outage
# ---------------------------------------------------------------------------


@router.get("/monitor")
async def monitor_status(request: Request, _user=Depends(auth.require_admin)):
    """Current downtime-monitor state (backend/bot reachability + mute)."""
    db = get_db(request)
    settings = await db.get_monitor_settings()
    now = time.time()

    api_ok = True
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://localhost:8000/api/health")
            api_ok = resp.status_code == 200
    except Exception:
        api_ok = False

    last_hb = await db.last_heartbeat()
    bot_ok = bool(last_hb and (now - last_hb) < 120)

    down_since = settings.get("down_since")
    return {
        "muted": settings.get("muted", False),
        "down_since": down_since.isoformat() if down_since else None,
        "last_notified": settings.get("last_notified").isoformat()
        if settings.get("last_notified")
        else None,
        "api_ok": api_ok,
        "bot_ok": bot_ok,
        "down": not (api_ok and bot_ok),
    }


@router.post("/monitor/mute")
async def monitor_mute(payload: dict, request: Request, _user=Depends(auth.require_admin)):
    """Mute/unmute downtime push notifications for the current outage."""
    db = get_db(request)
    muted = bool(payload.get("muted"))
    await db.set_monitor_muted(muted)
    return {"ok": True, "muted": muted}


# ---------------------------------------------------------------------------
# Database maintenance (owner only)
# ---------------------------------------------------------------------------


@router.post("/db/reset")
async def reset_database(request: Request, _user=Depends(auth.require_owner)):
    """Completely wipe the database (all data) and recreate the schema.

    Destructive: deletes servers, words, violations, users, logs, incidents,
    stats, push subscriptions - everything. The admin role is restored via the
    ADMIN_WHITELIST_IDS env, so the owner stays logged in.
    """
    db = get_db(request)
    await db.reset_database()
    await db.add_log("admin", "Database reset (all data wiped)", "critical")
    return {"ok": True}


# -- Tickets ---------------------------------------------------------------


@router.get("/tickets")
async def admin_list_tickets(
    request: Request,
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    _user=Depends(auth.require_admin),
):
    db = get_db(request)
    tickets = await db.list_tickets(status=status, ticket_type=type, search=search)
    return {"tickets": tickets, "total": len(tickets)}


@router.get("/tickets/{ticket_id}")
async def admin_get_ticket(
    request: Request,
    ticket_id: int,
    _user=Depends(auth.require_admin),
):
    db = get_db(request)
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    messages = await db.list_ticket_messages(ticket_id)
    return {"ticket": ticket, "messages": messages}


@router.put("/tickets/{ticket_id}")
async def admin_update_ticket(
    request: Request,
    ticket_id: int,
    _user=Depends(auth.require_admin),
):
    db = get_db(request)
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    body = await request.json()
    fields = {}
    for key in ("status", "assigned_to"):
        if key in body:
            fields[key] = body[key]
    if fields:
        await db.update_ticket(ticket_id, **fields)
    return {"ok": True}


@router.post("/tickets/{ticket_id}/reply")
async def admin_reply_ticket(
    request: Request,
    ticket_id: int,
    _user=Depends(auth.require_admin),
):
    db = get_db(request)
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    body = await request.json()
    reply = body.get("reply", "").strip()
    if not reply:
        raise HTTPException(400, "Reply is required")
    username = _user.get("username", "admin")
    await db.reply_ticket(ticket_id, reply, username)
    await db.update_ticket(ticket_id, status="answered")
    return {"ok": True}


@router.delete("/tickets/{ticket_id}")
async def admin_delete_ticket(
    request: Request,
    ticket_id: int,
    _user=Depends(auth.require_owner),
):
    db = get_db(request)
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    await db.delete_ticket(ticket_id)
    return {"ok": True}
