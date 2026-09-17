"""FastAPI entry point for the WordLock dashboard backend."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import httpx

from . import auth, push_service
from .database import Database
from .routers import admin, dashboard, security, webhook
from .routers.dashboard import require_guild_admin
from .version import __version__

log = logging.getLogger("wordlock.api")

PUSH_POLL_SECONDS = int(os.environ.get("PUSH_POLL_SECONDS", "20"))

# Discord snowflake IDs exceed Number.MAX_SAFE_INTEGER (2^53 - 1). JavaScript
# would round them in JSON.parse, corrupting every subsequent lookup. We ship
# such big ints as strings so the dashboard can round-trip them exactly.
MAX_SAFE_INT = 2**53 - 1


def _safe(o):
    if isinstance(o, dict):
        return {k: _safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_safe(v) for v in o]
    if isinstance(o, int) and not isinstance(o, bool) and (o > MAX_SAFE_INT or o < -MAX_SAFE_INT):
        return str(o)
    return o


class SafeJSONResponse(JSONResponse):
    def render(self, content):
        return (
            json.dumps(
                _safe(content),
                ensure_ascii=False,
                allow_nan=False,
                indent=None,
                separators=(",", ":"),
            ).encode("utf-8")
        )


async def _push_poll_loop(db: Database) -> None:
    """Periodically send pending security push notifications."""
    log.info("Push notification poller started (every %ss)", PUSH_POLL_SECONDS)
    while True:
        await asyncio.sleep(PUSH_POLL_SECONDS)
        try:
            sent = await push_service.process_pending(db)
            if sent:
                log.info("Sent %s push notification(s)", sent)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Push poll iteration failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    dsn = os.environ.get(
        "DATABASE_URL", "postgresql://wordlock:wordlock@localhost:5432/wordlock"
    )
    db = Database(dsn)
    await db.connect()
    app.state.db = db
    app.state.started_at = datetime.now(timezone.utc).isoformat()
    log.info("WordLock API v%s connected to database", __version__)
    poller = asyncio.create_task(_push_poll_loop(db))
    try:
        yield
    finally:
        poller.cancel()
        try:
            await poller
        except (asyncio.CancelledError, Exception):
            pass
        await db.close()


app = FastAPI(
    title="WordLock API",
    description="Backend for the WordLock Discord moderation dashboard.",
    version=__version__,
    lifespan=lifespan,
    default_response_class=SafeJSONResponse,
)

origins = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(security.router)
app.include_router(webhook.router)


@app.get("/")
async def root() -> dict:
    return {"name": "WordLock API", "version": __version__, "docs": "/docs"}


@app.get("/api/health")
async def health(request: Request) -> dict:
    db: Database = request.app.state.db
    db_ok = True
    try:
        async with db._pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "version": __version__,
    }


@app.get("/api/status")
async def api_status(request: Request) -> dict:
    import time as _time

    db: Database = request.app.state.db
    started_at = getattr(request.app.state, "started_at", None)
    database = "unreachable"
    try:
        async with db._pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        database = "connected"
    except Exception:
        pass

    bot = "offline"
    last_hb = await db.last_heartbeat()
    if last_hb:
        age = _time.time() - last_hb
        bot = "online" if age < 120 else "offline"

    return {
        "version": __version__,
        "started_at": started_at,
        "status": {
            "api": "online",
            "database": database,
            "bot": bot,
        },
        "downtime": await db.get_service_downtime(),
        "stats": {
            "active_servers": await db.active_server_count(),
            "servers": await db.server_count(),
            "active_users": await db.active_users(),
            "violations_today": await db.violations_today(),
            "violations_total": await db.violations_total(),
        },
        "maintenance": await db.maintenance_mode(),
    }


@app.post("/api/tickets")
async def create_ticket(request: Request) -> dict:
    db: Database = request.app.state.db
    try:
        body = await request.json()
    except Exception:
        return {"error": "Invalid JSON body"}

    turnstile_token = body.get("turnstile_token", "")
    if not turnstile_token:
        return {"error": "Captcha token required"}

    secret_key = os.environ.get("TURNSTILE_SECRET_KEY", "")
    remote_ip = request.client.host if request.client else ""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": secret_key,
                    "response": turnstile_token,
                    "remoteip": remote_ip,
                },
            )
        result = resp.json()
        if not result.get("success"):
            return {"error": "Captcha validation failed"}
    except Exception:
        return {"error": "Captcha validation failed"}

    ticket_type = body.get("type", "contact")
    subject = (body.get("subject") or "").strip()
    message = (body.get("message") or "").strip()
    sender_name = (body.get("sender_name") or "").strip()
    sender_email = (body.get("sender_email") or "").strip()

    if not subject:
        return {"error": "subject is required"}
    if not message:
        return {"error": "message is required"}
    if not sender_name:
        return {"error": "sender_name is required"}
    if not sender_email:
        return {"error": "sender_email is required"}
    if ticket_type not in ("contact", "bug", "feature", "support"):
        return {"error": "Invalid type"}

    # Unauthenticated: never trust sender_id (would allow impersonation).
    # guild_id is kept for server-specific contact routing.
    sender_id = None
    guild_id = body.get("guild_id") if body.get("guild_id") else None

    ticket = await db.add_ticket(
        ticket_type=ticket_type,
        subject=subject,
        message=message,
        sender_name=sender_name,
        sender_email=sender_email,
        sender_id=sender_id,
        guild_id=guild_id,
    )
    return {"ok": True, "id": ticket["id"]}


@app.get("/api/me/tickets")
async def my_tickets(request: Request):
    user = await auth.current_user(request)
    db: Database = request.app.state.db
    tickets = await db.list_my_tickets(user["discord_id"])
    return {"tickets": tickets}


@app.post("/api/me/tickets")
async def create_my_ticket(request: Request):
    user = await auth.current_user(request)
    db: Database = request.app.state.db
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    ticket_type = body.get("type", "contact")
    subject = (body.get("subject") or "").strip()
    message = (body.get("message") or "").strip()

    if not subject:
        raise HTTPException(status_code=400, detail="subject is required")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if ticket_type not in ("contact", "bug", "feature", "support"):
        raise HTTPException(status_code=400, detail="Invalid type")

    guild_id = body.get("guild_id")
    email = (body.get("sender_email") or "").strip() or f"{user['discord_id']}@wordlock.local"

    ticket = await db.add_ticket(
        ticket_type=ticket_type,
        subject=subject,
        message=message,
        sender_name=user.get("username") or "user",
        sender_email=email,
        sender_id=user["discord_id"],
        guild_id=guild_id,
    )
    return {"ok": True, "id": ticket["id"]}


@app.get("/api/me/tickets/{ticket_id}")
async def get_my_ticket(ticket_id: int, request: Request):
    user = await auth.current_user(request)
    db: Database = request.app.state.db
    ticket = await db.get_ticket(ticket_id)
    if not ticket or ticket.get("sender_id") != user["discord_id"]:
        raise HTTPException(404, "Ticket not found")
    messages = await db.list_ticket_messages(ticket_id)
    return {"ticket": ticket, "messages": messages}


@app.post("/api/me/tickets/{ticket_id}/reply")
async def reply_my_ticket(ticket_id: int, request: Request):
    user = await auth.current_user(request)
    db: Database = request.app.state.db
    ticket = await db.get_ticket(ticket_id)
    if not ticket or ticket.get("sender_id") != user["discord_id"]:
        raise HTTPException(404, "Ticket not found")
    if ticket.get("status") == "closed":
        raise HTTPException(status_code=400, detail="ticket is closed")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    await db.add_ticket_message(
        ticket_id, "user", user.get("username") or "user", content,
    )
    await db.update_ticket(ticket_id, status="open", admin_reply=None)
    return {"ok": True}


@app.post("/api/me/tickets/{ticket_id}/close")
async def close_my_ticket(ticket_id: int, request: Request):
    user = await auth.current_user(request)
    db: Database = request.app.state.db
    ticket = await db.get_ticket(ticket_id)
    if not ticket or ticket.get("sender_id") != user["discord_id"]:
        raise HTTPException(404, "Ticket not found")
    if ticket.get("status") == "closed":
        return {"ok": True}
    await db.update_ticket(ticket_id, status="closed")
    return {"ok": True}


@app.get("/api/server/{guild_id}/tickets")
async def server_tickets(guild_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    db = request.app.state.db
    tickets = await db.list_discord_tickets(guild_id)
    created = {t["id"]: t.get("creator_id") for t in tickets}
    return {"tickets": tickets}


@app.get("/api/server/{guild_id}/tickets/transcripts/{transcript_id}")
async def get_server_transcript(guild_id: int, transcript_id: int, request: Request):
    await require_guild_admin(guild_id, request)
    db = request.app.state.db
    transcript = await db.get_transcript(transcript_id)
    if not transcript or transcript["guild_id"] != guild_id:
        raise HTTPException(404, "Transkript nicht gefunden")
    return {
        "id": transcript["id"],
        "ticket_id": transcript["ticket_id"],
        "html": transcript["html"],
        "created_at": transcript["created_at"],
    }
