"""Discord OAuth2 login + JWT session handling for the WordLock API."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException, Request, Response

DISCORD_API = "https://discord.com/api"
CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
_JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not _JWT_SECRET or _JWT_SECRET in ("dev-secret-change-me", "change_me_to_a_long_random_string"):
    raise RuntimeError(
        "JWT_SECRET is not set or is the insecure default. "
        "Generate a strong secret with: openssl rand -hex 32"
    )
JWT_SECRET = _JWT_SECRET
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "720"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"

MANAGE_GUILD = 1 << 5  # Discord permission bit for "Manage Server"

ADMINISTRATOR = 1 << 3  # Discord permission bit for "Administrator"

BOT_PERMISSIONS = ADMINISTRATOR  # Admin: covers delete/timeout/kick/ban + role hierarchy

ROLE_LEVELS = {"moderator": 1, "developer": 2, "owner": 3}


def _whitelist() -> set[int]:
    return {int(i) for i in os.environ.get("ADMIN_WHITELIST_IDS", "").split(",") if i.strip()}


def authorize_url() -> str:
    return (
        f"{DISCORD_API}/oauth2/authorize"
        f"?client_id={CLIENT_ID}&response_type=code"
        f"&scope=identify%20guilds&redirect_uri={quote(REDIRECT_URI, safe='')}"
        f"&prompt=consent"
    )


def invite_url() -> str:
    """URL to invite the bot to a server (uses the real client ID)."""
    return (
        f"{DISCORD_API}/oauth2/authorize"
        f"?client_id={CLIENT_ID}&response_type=code"
        f"&scope=bot%20applications.commands"
        f"&permissions={BOT_PERMISSIONS}"
    )


async def exchange_code(code: str) -> Dict[str, Any]:
    """Exchange an authorization code for Discord tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "scope": "identify guilds",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="OAuth code exchange failed")
        return resp.json()


async def fetch_user(access_token: str) -> Dict[str, Any]:
    if not access_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        return resp.json()


async def fetch_user_guilds(access_token: str) -> list[Dict[str, Any]]:
    if not access_token:
        return []
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            return []
        return resp.json()


def create_session_token(discord_id: int) -> str:
    import time

    import jwt

    payload = {
        "sub": str(discord_id),
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_session_token(token: str) -> Optional[int]:
    import jwt

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return int(payload["sub"])
    except jwt.PyJWTError:
        return None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "wordlock_session",
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=JWT_EXPIRE_MINUTES * 60,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie("wordlock_session")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_db(request: Request):
    return request.app.state.db


async def current_user(request: Request):
    """Resolve the logged-in Discord user (or raise 401)."""
    token = request.cookies.get("wordlock_session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    discord_id = decode_session_token(token)
    if discord_id is None:
        raise HTTPException(status_code=401, detail="Session expired")
    db = request.app.state.db
    user = await db.get_user(discord_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def _effective_role(user: dict, db) -> str:
    role = user.get("role") or "user"
    if discord_id := user.get("discord_id"):
        if discord_id in _whitelist():
            if ROLE_LEVELS.get(role, 0) < ROLE_LEVELS["owner"]:
                return "owner"
        # Panel access granted through the team management (Stammbaum).
        if ROLE_LEVELS.get(role, 0) < ROLE_LEVELS["moderator"]:
            if await db.team_panel_access(discord_id):
                return "moderator"
    return role


async def require_admin(request: Request):
    user = await current_user(request)
    db = request.app.state.db
    role = await _effective_role(user, db)
    if ROLE_LEVELS.get(role, 0) < ROLE_LEVELS["moderator"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    user["role"] = role
    return user


async def require_developer(request: Request):
    user = await current_user(request)
    db = request.app.state.db
    role = await _effective_role(user, db)
    if ROLE_LEVELS.get(role, 0) < ROLE_LEVELS["developer"]:
        raise HTTPException(status_code=403, detail="Developer access required")
    user["role"] = role
    return user


async def require_owner(request: Request):
    user = await current_user(request)
    db = request.app.state.db
    role = await _effective_role(user, db)
    if role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    user["role"] = role
    return user


def admin_guilds_for(user: dict, guilds: list[dict], known: dict[int, dict]) -> list[dict]:
    """Filter guilds where the user can manage, enriched with bot status.

    Only guilds that the current user invited the bot to are included (the
    bot's inviter_id must match the user's Discord ID). This applies to every
    user including owners/staff - all servers are visible in the admin panel
    instead. Guilds without the bot are only included if the user could
    invite it (manage permission present).

    Legacy servers without a recorded inviter (inviter_id is NULL) stay
    visible to every manager, so access is not lost after this feature lands.
    """
    out = []
    for g in guilds:
        if (g.get("permissions") or 0) & MANAGE_GUILD:
            gid = int(g["id"])
            known_g = known.get(gid)
            bot_present = known_g is not None and known_g.get("status") != "removed"
            inviter_id = known_g.get("inviter_id") if bot_present else None
            if (
                bot_present
                and inviter_id is not None
                and inviter_id != user["discord_id"]
            ):
                # Bot is here but someone else invited it - do not expose it.
                continue
            out.append(
                {
                    "id": str(gid),
                    "name": g.get("name"),
                    "icon": g.get("icon"),
                    "member_count": known_g.get("member_count", 0) if bot_present else 0,
                    "bot_in_server": bot_present,
                    "bot_status": (known_g or {}).get("status", "invite"),
                    "bot_has_admin": bool((known_g or {}).get("admin_ok", True)),
                }
            )
    return out
