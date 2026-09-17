"""External webhooks for the WordLock bot.

Currently: bot avatar changes via a secret-protected webhook
(``AVATAR_WEBHOOK_SECRET``). Useful to sync the bot's profile picture from
external tools / CI / automations.
"""

from __future__ import annotations

import base64
import ipaddress
import os
import socket
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from .. import profile_service
from ..database import Database

router = APIRouter(prefix="/api/webhook", tags=["webhook"])

MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_MIME = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}


def _is_private_host(hostname: str) -> bool:
    """Resolve a hostname and block private/reserved/link-local IP ranges (SSRF guard)."""
    if not hostname:
        return True
    try:
        addrs = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True
    for family, _, _, _, sockaddr in addrs:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return True
    return False


def _validate_image_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="image_url must be http(s)")
    if parsed.hostname is None:
        raise HTTPException(status_code=400, detail="image_url has no hostname")
    if _is_private_host(parsed.hostname):
        raise HTTPException(status_code=400, detail="image_url points to a private network")
    return url


def _check_secret(secret: str) -> None:
    expected = os.environ.get("AVATAR_WEBHOOK_SECRET", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Webhook secret is not configured")
    if secret != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


@router.post("/avatar")
async def webhook_avatar(
    payload: dict,
    request: Request,
    x_webhook_secret: str = Header(default="", alias="X-Webhook-Secret"),
):
    _check_secret(x_webhook_secret)

    avatar: str | None = payload.get("avatar")
    image_url: str | None = payload.get("image_url")

    if not avatar and image_url:
        try:
            image_url = _validate_image_url(image_url)
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type not in ALLOWED_MIME:
                raise HTTPException(
                    status_code=400,
                    detail=f"image_url returned unsupported type: {content_type}",
                )
            if len(resp.content) > MAX_IMAGE_BYTES:
                raise HTTPException(status_code=400, detail="image_url is too large (max 8 MB)")
            b64 = base64.b64encode(resp.content).decode("ascii")
            avatar = f"data:{content_type};base64,{b64}"
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=502, detail="Could not fetch image_url")

    if not avatar:
        raise HTTPException(status_code=400, detail="avatar or image_url is required")

    db: Database = request.app.state.db
    stored = await profile_service.apply_and_store(db, avatar, actor_id=0)
    await db.add_log("webhook", "Bot avatar changed via webhook", "info")
    return {"ok": True, "avatar": stored.get("avatar")}
