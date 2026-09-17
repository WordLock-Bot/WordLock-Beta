"""Public dashboard endpoints (Discord OAuth2 login + guild management)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from .. import auth
from ..database import (
    DEFAULT_ANTI_NUKE_CONFIG,
    DEFAULT_ANTI_SPAM_CONFIG,
    Database,
    merge_anti_config,
)

router = APIRouter(prefix="/api", tags=["dashboard"])

DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL", "http://localhost:3000"
)
WORD_ACTIONS = ["delete", "warn", "timeout", "log"]
WORD_CATEGORIES = ["insult", "profanity", "slur", "sexual", "threat", "spam", "custom"]


def get_db(request: Request) -> Database:
    return request.app.state.db


async def require_guild_admin(guild_id: int, request: Request):
    """Current user must have invited the bot to the guild (or be whitelisted
    or be an explicitly invited co-moderator).

    Only the user who invited WordLock to a guild (plus invited panel members
    and staff) may see/configure it in the dashboard.
    """
    user = await auth.current_user(request)
    db = get_db(request)
    if user["discord_id"] in auth._whitelist():
        return user
    server = await db.get_server(guild_id)
    if not server:
        raise HTTPException(status_code=404, detail="Guild not found")
    if server.get("inviter_id") == user["discord_id"]:
        return user
    # Invited co-moderator / viewer -> panel access for this guild.
    if await db.has_guild_invite(guild_id, user["discord_id"]):
        return user
    # Legacy servers without an inviter: fall back to the Discord admin check.
    if not server.get("inviter_id"):
        guilds = await auth.fetch_user_guilds(user.get("access_token") or "")
        for g in guilds:
            if int(g["id"]) == guild_id and (g.get("permissions") or 0) & auth.MANAGE_GUILD:
                return user
    raise HTTPException(status_code=403, detail="You are not an admin of this guild")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@router.get("/auth/login")
async def auth_login() -> dict:
    return {"url": auth.authorize_url()}


@router.get("/auth/invite")
async def auth_invite() -> dict:
    return {"url": auth.invite_url()}


@router.get("/auth/callback")
async def auth_callback(
    code: str = Query(...),
    state: Optional[str] = None,
    request: Request = None,
    response: Response = None,
):
    db = get_db(request)
    try:
        tokens = await auth.exchange_code(code)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Login failed, please try again")

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    discord_user = await auth.fetch_user(access_token)
    user = await db.upsert_user(
        discord_id=int(discord_user["id"]),
        username=discord_user.get("username", "unknown"),
        access_token=access_token,
        refresh_token=refresh_token,
    )
    token = auth.create_session_token(user["discord_id"])
    auth.set_session_cookie(response, token)
    response.status_code = 302
    response.headers["Location"] = f"{DASHBOARD_URL}/dashboard"
    return response


@router.get("/auth/logout")
async def auth_logout(response: Response) -> dict:
    auth.clear_session_cookie(response)
    return {"ok": True}


@router.get("/auth/me")
async def auth_me(request: Request):
    user = await auth.current_user(request)
    role = auth._effective_role(user)
    db = get_db(request)
    guilds = await auth.fetch_user_guilds(user.get("access_token") or "")
    known_rows = await db.all_servers()
    known = {int(r["guild_id"]): r for r in known_rows}
    admin_guilds = auth.admin_guilds_for(user, guilds, known)

    # Servers the user was explicitly invited to moderate via panel invites.
    invited_rows = await db.guild_invites_for_user(user["discord_id"])
    invited_ids = {int(r["guild_id"]): r["role"] for r in invited_rows}
    seen = {int(g["id"]) for g in admin_guilds}
    for gid in invited_ids:
        if gid in seen:
            continue
        known_g = known.get(gid)
        if known_g is None or known_g.get("status") == "removed":
            continue
        admin_guilds.append(
            {
                "id": str(gid),
                "name": known_g.get("name") or "unknown",
                "icon": known_g.get("icon"),
                "member_count": known_g.get("member_count", 0),
                "bot_in_server": True,
                "bot_status": known_g.get("status", "active"),
                "bot_has_admin": bool(known_g.get("admin_ok", True)),
            }
        )

    return {
        "id": str(user["discord_id"]),
        "username": user.get("username"),
        "avatar": user.get("avatar"),
        "role": role,
        "admin_guilds": admin_guilds,
        "maintenance": await db.maintenance_mode(),
    }


@router.get("/auth/guild-permissions")
async def guild_permissions(guild_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    return {"guild_id": guild_id, "can_manage": True}


# ---------------------------------------------------------------------------
# Privacy / GDPR data request
# ---------------------------------------------------------------------------


@router.get("/data-request")
async def data_request_summary(request: Request):
    """Show which personal data WordLock stores for the logged-in user."""
    user = await auth.current_user(request)
    db = get_db(request)
    uid = user["discord_id"]
    violations = int(
        await db._fetchval("SELECT COUNT(*) FROM violations WHERE user_id = $1", uid) or 0
    )
    warnings = int(
        await db._fetchval("SELECT COUNT(*) FROM warnings WHERE user_id = $1", uid) or 0
    )
    return {
        "user_id": str(uid),
        "username": user.get("username"),
        "violations": violations,
        "warnings": warnings,
        "role": auth._effective_role(user),
    }


@router.post("/data-request")
async def data_request_delete(request: Request, response: Response):
    """Delete all stored data for the logged-in user (GDPR / DSGVO)."""
    user = await auth.current_user(request)
    db = get_db(request)
    uid = user["discord_id"]

    def _deleted_count(tag: str) -> int:
        try:
            return int(tag.split()[-1])
        except (ValueError, IndexError):
            return 0

    violations_tag = await db._execute("DELETE FROM violations WHERE user_id = $1", uid)
    warnings_tag = await db._execute("DELETE FROM warnings WHERE user_id = $1", uid)
    await db._execute(
        "UPDATE users SET access_token = NULL, refresh_token = NULL "
        "WHERE discord_id = $1",
        uid,
    )
    auth.clear_session_cookie(response)
    return {
        "ok": True,
        "deleted_violations": _deleted_count(violations_tag),
        "deleted_warnings": _deleted_count(warnings_tag),
    }


# ---------------------------------------------------------------------------
# Guild configuration
# ---------------------------------------------------------------------------


@router.get("/guilds/{guild_id}")
async def get_guild_config(guild_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    server = await db.get_server(guild_id)
    if not server:
        raise HTTPException(status_code=404, detail="WordLock is not on this server")
    server["anti_spam_config"] = merge_anti_config(
        server.get("anti_spam_config"), DEFAULT_ANTI_SPAM_CONFIG
    )
    server["anti_nuke_config"] = merge_anti_config(
        server.get("anti_nuke_config"), DEFAULT_ANTI_NUKE_CONFIG
    )
    return server


@router.get("/guilds/{guild_id}/channels")
async def guild_channels(guild_id: int, request: Request):
    """List the guild's sendable text channels (for the announce/log channel picker)."""
    await require_guild_admin(guild_id, request)
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
        raise HTTPException(status_code=502, detail="Could not load channels")
    channels = [
        {"id": str(c["id"]), "name": c.get("name"), "type": c.get("type")}
        for c in resp.json()
        if c.get("type") in (0, 4, 5)
    ]
    return {"channels": channels}


@router.get("/guilds/{guild_id}/ticket-config")
async def get_ticket_config(guild_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    row = await db.get_ticket_config(guild_id)
    if row is None:
        return {
            "guild_id": str(guild_id),
            "enabled": False,
            "panel_channel_id": None,
            "panel_message_id": None,
            "category_id": None,
            "welcome_message": "Hallo {mention}! Willkommen in deinem Ticket. Das Team kümmert sich gleich um dich.",
            "ticket_name_format": "ticket-{user}",
            "support_role_ids": [],
            "max_open": 1,
            "panel_needs_deploy": False,
        }
    return {
        "guild_id": str(row["guild_id"]),
        "enabled": bool(row.get("enabled")),
        "panel_channel_id": str(row["panel_channel_id"]) if row.get("panel_channel_id") else None,
        "panel_message_id": str(row["panel_message_id"]) if row.get("panel_message_id") else None,
        "category_id": str(row["category_id"]) if row.get("category_id") else None,
        "welcome_message": row.get("welcome_message") or "",
        "ticket_name_format": row.get("ticket_name_format") or "ticket-{user}",
        "support_role_ids": [str(r) for r in (row.get("support_role_ids") or [])],
        "max_open": row.get("max_open") or 1,
        "panel_needs_deploy": bool(row.get("panel_needs_deploy")),
    }


@router.put("/guilds/{guild_id}/ticket-config")
async def put_ticket_config(guild_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    body = await request.json()
    fields: dict = {}
    if "category_id" in body:
        val = body["category_id"]
        fields["category_id"] = int(val) if val else None
    if "panel_channel_id" in body:
        val = body["panel_channel_id"]
        fields["panel_channel_id"] = int(val) if val else None
    if "welcome_message" in body:
        msg = str(body["welcome_message"])[:2000]
        fields["welcome_message"] = msg
    if "ticket_name_format" in body:
        fmt = str(body["ticket_name_format"])[:200]
        fields["ticket_name_format"] = fmt
    if "support_role_ids" in body:
        ids = body["support_role_ids"]
        fields["support_role_ids"] = [int(r) for r in ids] if ids else []
    if "max_open" in body:
        val = int(body["max_open"])
        fields["max_open"] = max(1, min(10, val))
    if "enabled" in body:
        fields["enabled"] = bool(body["enabled"])
    if fields:
        fields["panel_needs_deploy"] = True
        await db.set_ticket_config(guild_id, **fields)
    return {"ok": True}


@router.get("/guilds/{guild_id}/roles")
async def guild_roles(guild_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="DISCORD_TOKEN not configured")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{auth.DISCORD_API}/guilds/{guild_id}/roles",
            headers={"Authorization": f"Bot {token}"},
            timeout=15,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Could not load roles")
    roles = [
        {
            "id": str(r["id"]),
            "name": r.get("name", ""),
            "color": r.get("color", 0),
            "managed": r.get("managed", False),
            "position": r.get("position", 0),
        }
        for r in resp.json()
        if not r.get("managed", False) and r.get("name", "@everyone") != "@everyone"
    ]
    roles.sort(key=lambda r: r["position"], reverse=True)
    return {"roles": roles}


async def require_guild_owner(guild_id: int, request: Request):
    """Only the user who actually invited the bot (or staff) may manage
    panel invites. Co-moderators invited to the panel cannot invite others."""
    user = await auth.current_user(request)
    db = get_db(request)
    if user["discord_id"] in auth._whitelist():
        return user
    server = await db.get_server(guild_id)
    if not server:
        raise HTTPException(status_code=404, detail="Guild not found")
    if server.get("inviter_id") == user["discord_id"]:
        return user
    raise HTTPException(status_code=403, detail="Only the server owner can manage panel members")


@router.get("/guilds/{guild_id}/panel-members")
async def guild_panel_members(guild_id: int, request: Request):
    """List all users invited to moderate this guild's panel."""
    await require_guild_admin(guild_id, request)
    rows = await get_db(request).list_guild_invites(guild_id)
    members = []
    for r in rows:
        members.append(
            {
                "discord_id": str(r["discord_id"]),
                "username": r.get("username"),
                "role": r["role"],
                "invited_by": str(r["invited_by"]),
                "created_at": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else r["created_at"],
                "pending": not bool(r.get("known")),
            }
        )
    inviter = await get_db(request).get_server(guild_id)
    return {
        "members": members,
        "inviter_id": str(inviter["inviter_id"]) if inviter and inviter.get("inviter_id") else None,
    }


@router.post("/guilds/{guild_id}/panel-members")
async def guild_panel_member_add(guild_id: int, payload: dict, request: Request):
    """Invite a Discord user (by ID) to moderate this guild's panel."""
    await require_guild_owner(guild_id, request)
    db = get_db(request)
    discord_id = payload.get("discord_id")
    role = str(payload.get("role") or "moderator").strip()
    if discord_id is None:
        raise HTTPException(status_code=400, detail="discord_id fehlt")
    try:
        discord_id = int(discord_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="discord_id muss eine Zahl sein")
    if role not in ("moderator", "viewer"):
        raise HTTPException(status_code=400, detail="role muss 'moderator' oder 'viewer' sein")
    user = await auth.current_user(request)
    row = await db.add_guild_invite(guild_id, discord_id, user["discord_id"], role)
    await db.add_log("panel_invite", f"Panel-Mitglied {discord_id} eingeladen (role={role})", "info", guild_id=guild_id)
    return {"ok": True, "member": {"discord_id": str(discord_id), "role": row["role"]}}


@router.delete("/guilds/{guild_id}/panel-members/{discord_id}")
async def guild_panel_member_remove(guild_id: int, discord_id: int, request: Request):
    """Remove a user's panel access for this guild."""
    await require_guild_owner(guild_id, request)
    if not await get_db(request).remove_guild_invite(guild_id, discord_id):
        raise HTTPException(status_code=404, detail="Mitglied nicht gefunden")
    return {"ok": True}


@router.get("/team")
async def public_team(request: Request):
    """Public team hierarchy for the landing page (#team)."""
    return await get_db(request).list_team_public()


@router.put("/guilds/{guild_id}")
async def update_guild_config(guild_id: int, payload: dict, request: Request):
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    allowed = {
        "language", "mod_level", "log_channel_id", "action_delete",
        "action_warn", "action_timeout", "action_log", "timeout_minutes",
        "default_lists", "bypass_roles", "bypass_users",
        "std_word_action",
        "anti_spam_enabled", "anti_nuke_enabled",
        "anti_spam_config", "anti_nuke_config",
        "welcome_channel_id", "welcome_message",
        "leave_channel_id", "leave_message",
        "phishing_enabled", "phishing_action", "phishing_config",
    }
    fields = {k: v for k, v in payload.items() if k in allowed}
    if not fields:
        raise HTTPException(status_code=400, detail="No valid fields provided")
    if "log_channel_id" in fields and fields["log_channel_id"]:
        fields["log_channel_id"] = int(fields["log_channel_id"])
    elif "log_channel_id" in fields:
        fields["log_channel_id"] = None
    if "timeout_minutes" in fields:
        fields["timeout_minutes"] = int(fields["timeout_minutes"] or 0)

    def _num(value, name: str, default: int) -> int:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return int(default)

    if "anti_spam_config" in fields:
        cfg = merge_anti_config(fields["anti_spam_config"], DEFAULT_ANTI_SPAM_CONFIG)
        if cfg["action"] not in ("delete", "warn", "timeout", "kick", "ban"):
            cfg["action"] = DEFAULT_ANTI_SPAM_CONFIG["action"]
        for k in ("rate_limit", "rate_window", "mention_limit", "mention_window",
                  "link_limit", "link_window", "emoji_limit", "emoji_window",
                  "webhook_rate_limit", "webhook_window"):
            cfg[k] = _num(cfg.get(k), k, DEFAULT_ANTI_SPAM_CONFIG[k])
        cfg["caps_ratio"] = min(1.0, max(0.0, float(cfg.get("caps_ratio", 0.8))))
        cfg["caps_min_len"] = max(1, int(cfg.get("caps_min_len", 8) or 8))
        fields["anti_spam_config"] = cfg
    if "anti_nuke_config" in fields:
        cfg = merge_anti_config(fields["anti_nuke_config"], DEFAULT_ANTI_NUKE_CONFIG)
        if cfg["action"] not in ("timeout", "kick", "ban"):
            cfg["action"] = DEFAULT_ANTI_NUKE_CONFIG["action"]
        for k in ("channel_limit", "channel_window", "role_limit", "role_window",
                  "kick_limit", "kick_window", "ban_limit", "ban_window",
                  "webhook_limit", "webhook_window"):
            cfg[k] = _num(cfg.get(k), k, DEFAULT_ANTI_NUKE_CONFIG[k])
        fields["anti_nuke_config"] = cfg
    for flag in ("anti_spam_enabled", "anti_nuke_enabled"):
        if flag in fields:
            fields[flag] = bool(fields[flag])

    for key in ("welcome_channel_id", "leave_channel_id"):
        if key in fields and fields[key]:
            fields[key] = int(fields[key])
        elif key in fields:
            fields[key] = None
    if "phishing_enabled" in fields:
        fields["phishing_enabled"] = bool(fields["phishing_enabled"])
    if "phishing_action" in fields:
        if fields["phishing_action"] not in ("delete", "warn", "timeout", "log"):
            raise HTTPException(status_code=400, detail="Ungültige Aktion")
    if "phishing_config" in fields:
        cfg = fields["phishing_config"]
        if not isinstance(cfg, dict):
            raise HTTPException(status_code=400, detail="phishing_config muss ein Objekt sein")
        sanitized = {}
        suspicious = cfg.get("suspicious_tlds")
        shorteners = cfg.get("shorteners")
        if suspicious is None:
            suspicious = []
        if shorteners is None:
            shorteners = []
        if not isinstance(suspicious, list) or not all(isinstance(x, str) for x in suspicious):
            raise HTTPException(status_code=400, detail="Ungültige suspicious_tlds")
        if not isinstance(shorteners, list) or not all(isinstance(x, str) for x in shorteners):
            raise HTTPException(status_code=400, detail="Ungültige shorteners")
        sanitized["suspicious_tlds"] = suspicious
        sanitized["shorteners"] = shorteners
        fields["phishing_config"] = sanitized

    await db.update_server(guild_id, **fields)
    return await db.get_server(guild_id)


@router.get("/guilds/{guild_id}/words")
async def get_guild_words(
    guild_id: int, request: Request, enabled_only: bool = Query(True)
):
    await require_guild_admin(guild_id, request)
    return await get_db(request).get_custom_words(guild_id, enabled_only)


@router.post("/guilds/{guild_id}/words")
async def add_guild_word(guild_id: int, payload: dict, request: Request):
    await require_guild_admin(guild_id, request)
    db = get_db(request)
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
    return {"ok": True, "word": word}


@router.delete("/guilds/{guild_id}/words/{word}")
async def remove_guild_word(guild_id: int, word: str, request: Request):
    await require_guild_admin(guild_id, request)
    ok = await get_db(request).remove_custom_word(guild_id, word.lower())
    if not ok:
        raise HTTPException(status_code=404, detail="Word not found")
    return {"ok": True}


@router.patch("/guilds/{guild_id}/words/{word}/enabled")
async def set_word_enabled(
    guild_id: int, word: str, payload: dict, request: Request
):
    await require_guild_admin(guild_id, request)
    enabled = bool(payload.get("enabled"))
    await get_db(request).set_custom_word_enabled(guild_id, word.lower(), enabled)
    return {"ok": True, "enabled": enabled}


@router.get("/guilds/{guild_id}/lists")
async def available_lists(guild_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    data_dir = Path(
        os.environ.get(
            "DATA_DIR",
            str(Path(__file__).resolve().parent.parent.parent / "data"),
        )
    )
    available = []
    for f in sorted(data_dir.glob("default_words_*.json")):
        lang = f.stem.replace("default_words_", "")
        with f.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        meta = data.get("meta", {})
        available.append(
            {
                "language": lang,
                "name": meta.get("name", lang),
                "version": meta.get("version", "?"),
                "words": len(data.get("words", [])),
            }
        )
    return {"available": available}


@router.get("/guilds/{guild_id}/standard-words")
async def standard_words(guild_id: int, request: Request, enabled_only: bool = Query(False)):
    """Standard list words for this guild, merged with per-guild overrides."""
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    server = await db.get_server(guild_id)
    default_lists = (server or {}).get("default_lists") or {"de": True, "en": True}
    if isinstance(default_lists, str):
        default_lists = json.loads(default_lists)
    languages = [lang for lang, active in default_lists.items() if active]

    data_dir = Path(
        os.environ.get(
            "DATA_DIR",
            str(Path(__file__).resolve().parent.parent.parent / "data"),
        )
    )
    entries: list[dict] = []
    for lang in languages:
        path = data_dir / f"default_words_{lang}.json"
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        for item in payload.get("words", []):
            entries.append(
                {
                    "word": item["word"],
                    "category": item.get("category", "profanity"),
                    "severity": item.get("severity", 3),
                    "language": lang,
                    "enabled": True,
                    "action": None,
                }
            )

    overrides = {o["word"]: o for o in await db.get_word_overrides(guild_id)}
    out = []
    for e in entries:
        ov = overrides.get(e["word"])
        if ov is not None:
            e["enabled"] = bool(ov["enabled"])
            e["action"] = ov.get("action")
        if enabled_only and not e["enabled"]:
            continue
        out.append(e)
    return out


@router.patch("/guilds/{guild_id}/standard-words/{word}")
async def patch_standard_word(guild_id: int, word: str, payload: dict, request: Request):
    """Enable/disable or change the action of a standard word for this guild."""
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    action = payload.get("action")
    enabled = bool(payload.get("enabled", True))
    if action is not None and action not in WORD_ACTIONS:
        raise HTTPException(status_code=400, detail="Invalid action")
    await db.set_word_override(guild_id, word.lower().strip(), action, enabled)
    return {"ok": True, "word": word.lower().strip(), "action": action, "enabled": enabled}


@router.delete("/guilds/{guild_id}/standard-words/{word}")
async def delete_standard_word(guild_id: int, word: str, request: Request):
    """Reset a standard word back to its default behavior for this guild."""
    await require_guild_admin(guild_id, request)
    ok = await get_db(request).remove_word_override(guild_id, word.lower())
    if not ok:
        raise HTTPException(status_code=404, detail="No override found")
    return {"ok": True}


@router.get("/guilds/{guild_id}/stats")
async def guild_stats(guild_id: int, request: Request, days: int = Query(30, le=90)):
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    server = await db.get_server(guild_id)
    today_series = await db.violations_series(guild_id, 1)
    return {
        "guild_id": guild_id,
        "guild_name": (server or {}).get("name", ""),
        "member_count": (server or {}).get("member_count", 0),
        "status": (server or {}).get("status", "unknown"),
        "violations_today": sum(int(r["value"]) for r in today_series),
        "violations_series": await db.violations_series(guild_id, days),
        "top_words": await db.violations_top_words(guild_id, 10),
        "actions": await db.action_counts(guild_id),
        "warning_count": int(
            (await db._fetchval(
                "SELECT COUNT(*) FROM warnings WHERE guild_id = $1", guild_id
            )) or 0
        ),
    }


@router.get("/guilds/{guild_id}/invites")
async def guild_invites(guild_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    return {
        "stats": await db.invite_stats(guild_id),
        "leaderboard": await db.invite_leaderboard(guild_id, 30),
    }


@router.get("/guilds/{guild_id}/scheduled")
async def list_scheduled(guild_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    return {"messages": await db.list_scheduled_messages(guild_id)}


@router.post("/guilds/{guild_id}/scheduled")
async def create_scheduled(guild_id: int, payload: dict, request: Request):
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    if not await db.get_server(guild_id):
        raise HTTPException(status_code=404, detail="WordLock ist auf diesem Server nicht aktiv")

    channel_id = payload.get("channel_id")
    if not isinstance(channel_id, int):
        raise HTTPException(status_code=400, detail="channel_id ist erforderlich")

    content = (payload.get("content") or "").strip()
    if not content or len(content) > 2000:
        raise HTTPException(status_code=400, detail="content muss 1-2000 Zeichen lang sein")

    interval_minutes = payload.get("interval_minutes")
    daily_hhmm = payload.get("daily_hhmm")
    if (interval_minutes is not None) and (daily_hhmm is not None):
        raise HTTPException(status_code=400, detail="Nur einer von interval_minutes oder daily_hhmm")

    run_at = None
    if interval_minutes is not None:
        if not isinstance(interval_minutes, int) or not 1 <= interval_minutes <= 10080:
            raise HTTPException(status_code=400, detail="interval_minutes muss 1-10080 sein")
        run_at = datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)
    elif daily_hhmm is not None:
        if not isinstance(daily_hhmm, str):
            raise HTTPException(status_code=400, detail="Ungültiges daily_hhmm")
        match = re.fullmatch(r"^(\d{1,2}):(\d{2})$", daily_hhmm)
        if not match:
            raise HTTPException(status_code=400, detail="daily_hhmm muss HH:MM sein")
        hour, minute = int(match.group(1)), int(match.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise HTTPException(status_code=400, detail="Ungültige Uhrzeit")
    else:
        raise HTTPException(
            status_code=400,
            detail="Einer von interval_minutes oder daily_hhmm ist erforderlich",
        )

    created = await db.create_scheduled_message(
        guild_id=guild_id,
        channel_id=channel_id,
        content=content,
        interval_minutes=interval_minutes,
        daily_hhmm=daily_hhmm,
        run_at=run_at,
    )
    return {"ok": True, "id": (created or {}).get("id")}


@router.delete("/guilds/{guild_id}/scheduled/{message_id}")
async def delete_scheduled(guild_id: int, message_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    db = get_db(request)
    ok = await db.delete_scheduled_message(message_id, guild_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Geplante Nachricht nicht gefunden")
    return {"ok": True}
