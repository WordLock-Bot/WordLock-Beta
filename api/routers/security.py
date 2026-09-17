"""Security incident + Web Push endpoints.

Guild admins can view their own incidents and re-enable the bot after a
self-protection lockout. Bot staff can see everything via /api/security/*.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .. import auth, push_service
from ..database import Database
from ..push_service import VAPID_PUBLIC_KEY

router = APIRouter(tags=["security"])


def get_db(request: Request) -> Database:
    return request.app.state.db


# ---------------------------------------------------------------------------
# Guild admin (self-service re-enable + incident history)
# ---------------------------------------------------------------------------


@router.get("/api/guilds/{guild_id}/incidents")
async def guild_incidents(guild_id: int, request: Request):
    from .dashboard import require_guild_admin

    await require_guild_admin(guild_id, request)
    return await get_db(request).list_incidents(guild_id=guild_id, limit=50)


@router.post("/api/guilds/{guild_id}/enable")
async def guild_enable(guild_id: int, request: Request):
    """Re-enable the bot after a self-protection lockout (guild admin)."""
    from .dashboard import require_guild_admin

    await require_guild_admin(guild_id, request)
    db = get_db(request)
    server = await db.get_server(guild_id)
    if not server:
        raise HTTPException(status_code=404, detail="WordLock is not on this server")
    await db.update_server(guild_id, status="active")
    resolved = await db.resolve_open_incidents(guild_id)
    await db.add_log(
        "security",
        f"Guild {guild_id} re-enabled via dashboard",
        "info",
        guild_id=guild_id,
    )
    return {"ok": True, "status": "active", "resolved_incidents": resolved}


# ---------------------------------------------------------------------------
# Bot staff (global incident overview)
# ---------------------------------------------------------------------------


@router.get("/api/security/incidents")
async def incidents(
    request: Request,
    limit: int = Query(100, le=500),
    status: Optional[str] = Query(None),
    _user=Depends(auth.require_admin),
):
    db = get_db(request)
    rows = await db.list_incidents(limit=limit, status=status)
    servers = {int(r["guild_id"]): r for r in await db.all_servers()}
    for row in rows:
        gid = int(row["guild_id"])
        row["guild_name"] = (servers.get(gid) or {}).get("name") or str(gid)
    return rows


@router.post("/api/security/incidents/{incident_id}/resolve")
async def resolve_incident(incident_id: int, request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    incident = await db.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    await db.resolve_incident(incident_id)
    await db.add_log("security", f"Incident {incident_id} resolved", "info")
    return {"ok": True}


@router.post("/api/security/guilds/{guild_id}/enable")
async def security_guild_enable(guild_id: int, request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    if not await db.get_server(guild_id):
        raise HTTPException(status_code=404, detail="Server not found")
    await db.update_server(guild_id, status="active")
    resolved = await db.resolve_open_incidents(guild_id)
    await db.add_log("security", f"Guild {guild_id} re-enabled by staff", "info", guild_id=guild_id)
    return {"ok": True, "status": "active", "resolved_incidents": resolved}


@router.get("/api/security/stats")
async def security_stats(request: Request, _user=Depends(auth.require_admin)):
    db = get_db(request)
    return {
        "open": await db.open_incident_count(),
        "total": len(await db.list_incidents(limit=5000)),
    }


# ---------------------------------------------------------------------------
# Push subscriptions (any logged-in user)
# ---------------------------------------------------------------------------


@router.get("/api/push/vapid-key")
async def vapid_key(request: Request):
    await auth.current_user(request)
    return {"public_key": VAPID_PUBLIC_KEY}


@router.post("/api/push/subscribe")
async def subscribe(payload: dict, request: Request):
    user = await auth.current_user(request)
    db = get_db(request)
    endpoint = (payload.get("endpoint") or "").strip()
    keys = payload.get("keys")
    if not endpoint or not isinstance(keys, dict):
        raise HTTPException(status_code=400, detail="endpoint and keys are required")
    await db.upsert_push_subscription(int(user["discord_id"]), endpoint, keys)
    return {"ok": True}


@router.post("/api/push/unsubscribe")
async def unsubscribe(payload: dict, request: Request):
    user = await auth.current_user(request)
    db = get_db(request)
    endpoint = (payload.get("endpoint") or "").strip()
    if endpoint:
        await db.remove_push_subscription(int(user["discord_id"]), endpoint)
    return {"ok": True}


@router.post("/api/push/test")
async def push_test(request: Request):
    """Send a test push notification to the logged-in user's devices."""
    user = await auth.current_user(request)
    db = get_db(request)
    sent = await push_service.send_test_push(db, int(user["discord_id"]))
    if sent == 0:
        raise HTTPException(
            status_code=400,
            detail="No push subscription found. Enable notifications first.",
        )
    return {"ok": True, "sent": sent}


@router.post("/api/admin/push/test")
async def admin_push_test(request: Request, _user=Depends(auth.require_admin)):
    """Send a test push notification to every WordLock admin device."""
    db = get_db(request)
    sent = await push_service.send_test_push_all_admins(db)
    if sent == 0:
        raise HTTPException(
            status_code=400,
            detail="No admin push subscriptions found. Admins must enable notifications first.",
        )
    return {"ok": True, "sent": sent}
