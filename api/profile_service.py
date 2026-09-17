"""Bot profile picture updates against the Discord API.

Discord bots have exactly ONE global avatar. A change made by any server
admin therefore overrides the bot's avatar for all servers (last write wins).
Bot admins can override or reset it from the admin panel.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from .database import Database

DISCORD_API = "https://discord.com/api"

DATA_URI_RE = re.compile(r"^data:image/(png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=\s]+$")

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # Discord avatar limit


def bot_token() -> str:
    token = os.environ.get("DISCORD_TOKEN", "")
    if not token:
        raise HTTPException(
            status_code=500,
            detail="DISCORD_TOKEN is not set on the API server",
        )
    return token


def _validate_image(data: str) -> None:
    if not isinstance(data, str) or not DATA_URI_RE.match(data):
        raise HTTPException(
            status_code=400,
            detail="avatar must be a base64 image data URI (PNG/JPG/GIF/WebP)",
        )
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="avatar is too large (max 8 MB)")


async def set_avatar(avatar: Optional[str]) -> None:
    """Push the new bot avatar to Discord (None clears it)."""
    headers = {"Authorization": f"Bot {bot_token()}"}
    payload = {"icon": avatar if avatar else None}
    if avatar:
        _validate_image(avatar)
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{DISCORD_API}/applications/@me", headers=headers, json=payload
        )
    if resp.status_code == 401:
        raise HTTPException(status_code=500, detail="Discord bot token is invalid")
    if resp.status_code == 429:
        raise HTTPException(
            status_code=429,
            detail="Discord rate limit: das Profilbild kann nur mehrmals pro "
            "Stunde geändert werden. Bitte warte etwas.",
        )
    if resp.status_code not in (200, 204):
        raise HTTPException(
            status_code=400,
            detail=f"Discord hat das Bild abgelehnt ({resp.status_code}). "
            "Format oder Größe sind evtl. ungültig.",
        )


async def apply_and_store(
    db: Database,
    avatar: Optional[str],
    actor_id: int,
    guild_id: Optional[int] = None,
) -> dict:
    """Apply the avatar to Discord, store it and log the change."""
    await set_avatar(avatar)
    stored = await db.save_bot_profile({"avatar": avatar}, actor_id)
    preview = (avatar or "")[:80] + "..." if avatar else None
    await db.add_profile_history("avatar", actor_id, guild_id, preview)
    await db.add_log(
        "profile",
        f"Bot avatar changed by {actor_id}",
        "info",
        guild_id=guild_id,
    )
    return stored
