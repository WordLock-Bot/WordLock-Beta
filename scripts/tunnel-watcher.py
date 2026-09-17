#!/usr/bin/env python3
"""tunnel-watcher: propagiert die aktuelle trycloudflare-URL ins Git-Repo
und überwacht gleichzeitig alle WordLock-Dienste (API, Datenbank, Bot).

Ausfall-Überwachung:
  - API wird per HTTP-Healthcheck geprüft, die Datenbank per SQL-Query und
    der Bot über bot_heartbeat.
  - Ist einer der Dienste länger als DOWN_THRESHOLD (Default 5 min) down,
    wird eine Web-Push-Nachricht an alle Admin-Subscriptions geschickt.
  - Der Ausfall-Zustand wird pro Dienst in der Tabelle `service_downtime`
    persistiert, sodass alle Clients (Status-Seite) denselben Zeitpunkt sehen.
  - Während der Ausfall anhält, wird alle RESEND_INTERVAL (Default 30 min)
    erneut gepusht.
  - Über die API (POST /api/admin/monitor/mute) kann der aktuelle Ausfall
    stummgeschaltet werden (State in DB, monitor_settings). Beim nächsten
    Ausfall (nach Erholung) wird wieder benachrichtigt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path

import asyncpg
import httpx

log = logging.getLogger("tunnel-watcher")
logging.basicConfig(level=logging.INFO, format="[watcher] %(message)s")

LOG = Path("/tunnel-log/tunnel.log")
REPO_DIR = Path("/repo")
BRANCH = os.environ.get("REPO_BRANCH", "main")
URL_INTERVAL = int(os.environ.get("INTERVAL", "15"))
FILE = os.environ.get("REPO_FILE", "config/instance-url.json")

REPO_URL = os.environ.get("REPO_URL")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GIT_USER_NAME = os.environ.get("GIT_USER_NAME", "wordlock-tunnel-watcher")
GIT_USER_EMAIL = os.environ.get("GIT_USER_EMAIL", "tunnel-watcher@users.noreply.github.com")

DATABASE_URL = os.environ.get("DATABASE_URL")
API_HEALTH_URL = os.environ.get("API_HEALTH_URL", "http://wordlock-api:8000/api/health")

VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN", "")
VERCEL_PROJECT_ID = os.environ.get("VERCEL_PROJECT_ID", "")
VERCEL_DEPLOY_HOOK_URL = os.environ.get("VERCEL_DEPLOY_HOOK_URL", "")
VERCEL_CONSOLE_API_URL = os.environ.get("VERCEL_CONSOLE_API_URL", "https://api.vercel.com")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "30"))
DOWN_THRESHOLD = int(os.environ.get("DOWN_THRESHOLD", "300"))
RESEND_INTERVAL = int(os.environ.get("RESEND_INTERVAL", "1800"))
HEARTBEAT_MAX_AGE = int(os.environ.get("HEARTBEAT_MAX_AGE", "120"))

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:dev@wordlock.example")

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def push_configured() -> bool:
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


# ---------------------------------------------------------------------------
# Tunnel-URL Propagation
# ---------------------------------------------------------------------------


def get_url() -> str | None:
    if not LOG.exists():
        return None
    try:
        content = LOG.read_text(errors="ignore")
    except OSError:
        return None
    matches = URL_RE.findall(content)
    return matches[-1] if matches else None


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)


def auth_url() -> str:
    if not REPO_URL or not GITHUB_TOKEN:
        raise RuntimeError("REPO_URL and GITHUB_TOKEN are required")
    return f"https://x-access-token:{GITHUB_TOKEN}@{REPO_URL.removeprefix('https://')}"


def clone_or_pull() -> None:
    if not (REPO_DIR / ".git").exists():
        log.info("Cloning repository ...")
        if REPO_DIR.exists():
            subprocess.run(["rm", "-rf", str(REPO_DIR)], timeout=120)
        _run(["git", "clone", "--depth", "1", "--branch", BRANCH, auth_url(), str(REPO_DIR)])
    else:
        _run(["git", "-C", str(REPO_DIR), "remote", "set-url", "origin", auth_url()])
        log.info("Pulling latest changes ...")
        res = _run(["git", "-C", str(REPO_DIR), "pull", "--ff-only", "origin", BRANCH])
        if res.returncode != 0:
            log.warning("Pull failed: %s", res.stderr.strip() or res.stdout.strip())


def push_url(url: str) -> None:
    clone_or_pull()
    payload = json.dumps({"url": url})
    target = REPO_DIR / FILE
    if target.exists() and target.read_text().strip() == payload:
        log.info("URL unchanged in repo, nothing to do.")
        return

    REPO_DIR.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload + "\n")
    _run(["git", "-C", str(REPO_DIR), "config", "user.name", GIT_USER_NAME])
    _run(["git", "-C", str(REPO_DIR), "config", "user.email", GIT_USER_EMAIL])
    _run(["git", "-C", str(REPO_DIR), "add", FILE])
    commit = _run(["git", "-C", str(REPO_DIR), "commit", "-m", f"chore: tunnel URL -> {url}"])
    if commit.returncode != 0:
        log.info("Nothing to commit")
        return
    log.info("Pushing tunnel URL to %s ...", BRANCH)
    _run(["git", "-C", str(REPO_DIR), "push", "origin", BRANCH])
    log.info("Done.")


def vercel_configured() -> bool:
    if not (VERCEL_TOKEN and VERCEL_PROJECT_ID and VERCEL_DEPLOY_HOOK_URL):
        log.info(
            "Vercel automation missing (need VERCEL_TOKEN, VERCEL_PROJECT_ID, "
            "VERCEL_DEPLOY_HOOK_URL) — skipping dashboard redeploy"
        )
        return False
    return True


def _vercel_headers() -> dict:
    return {"Authorization": f"Bearer {VERCEL_TOKEN}"}


def vercel_set_env_url(url: str) -> None:
    """Set NEXT_PUBLIC_API_URL (production) on the Vercel project."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{VERCEL_CONSOLE_API_URL}/v9/projects/{VERCEL_PROJECT_ID}/env",
            headers=_vercel_headers(),
        )
        if resp.status_code != 200:
            raise RuntimeError(f"list env failed: {resp.status_code} {resp.text[:200]}")
        existing = None
        for item in resp.json() or []:
            if item.get("key") == "NEXT_PUBLIC_API_URL" and "production" in (item.get("target", [])):
                existing = item
                break
        if existing and existing.get("value") == url:
            log.info("Vercel NEXT_PUBLIC_API_URL already up to date.")
            return
        if existing:
            del_resp = client.delete(
                f"{VERCEL_CONSOLE_API_URL}/v9/projects/{VERCEL_PROJECT_ID}/env/{existing['id']}",
                headers=_vercel_headers(),
            )
            if del_resp.status_code not in (200, 202, 204):
                raise RuntimeError(f"delete env failed: {del_resp.status_code} {del_resp.text[:200]}")
            log.info("Removed old NEXT_PUBLIC_API_URL (%s)", existing.get("value"))
        add_resp = client.post(
            f"{VERCEL_CONSOLE_API_URL}/v9/projects/{VERCEL_PROJECT_ID}/env",
            headers=_vercel_headers(),
            json={
                "key": "NEXT_PUBLIC_API_URL",
                "value": url,
                "type": "plain",
                "target": ["production"],
            },
        )
        if add_resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"add env failed: {add_resp.status_code} {add_resp.text[:200]}")
        log.info("Vercel NEXT_PUBLIC_API_URL set to %s", url)


def vercel_trigger_deploy() -> None:
    """Trigger a redeploy (deploy hook) so the dashboard rebuilds with the new URL."""
    with httpx.Client(timeout=60) as client:
        resp = client.post(VERCEL_DEPLOY_HOOK_URL)
        if resp.status_code != 200:
            raise RuntimeError(f"deploy hook failed: {resp.status_code} {resp.text[:200]}")
        log.info("Vercel deploy hook triggered (job=%s)", (resp.json() or {}).get("job", "?"))


async def url_loop() -> None:
    last = ""
    while True:
        try:
            url = get_url()
            if url and url != last:
                log.info("Detected tunnel URL: %s", url)
                last = url
                await asyncio.to_thread(push_url, url)
                if vercel_configured():
                    try:
                        await asyncio.to_thread(vercel_set_env_url, url)
                        await asyncio.to_thread(vercel_trigger_deploy)
                    except Exception:
                        log.exception("Vercel redeploy update failed")
        except Exception:
            log.exception("URL propagation failed")
        await asyncio.sleep(URL_INTERVAL)


# ---------------------------------------------------------------------------
# Downtime monitoring + push (per service: api, database, bot)
# ---------------------------------------------------------------------------


def _now() -> float:
    return time.time()


async def api_is_healthy() -> bool:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(API_HEALTH_URL)
            return resp.status_code == 200
    except Exception:
        return False


async def db_is_healthy(pool: asyncpg.Pool) -> bool:
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False


async def bot_is_healthy(pool: asyncpg.Pool) -> bool:
    try:
        row = await pool.fetchval("SELECT EXTRACT(EPOCH FROM last_seen) FROM bot_heartbeat WHERE id = 1")
    except Exception:
        return False
    return bool(row is not None and (_now() - float(row)) < HEARTBEAT_MAX_AGE)


SERVICES = ("api", "database", "bot")


async def load_settings(pool: asyncpg.Pool) -> dict:
    row = await pool.fetchrow("SELECT muted, down_since, last_notified FROM monitor_settings WHERE id = 1")
    if not row:
        await pool.execute(
            "INSERT INTO monitor_settings (id, muted) VALUES (1, FALSE) ON CONFLICT (id) DO NOTHING"
        )
        return {"muted": False, "down_since": None, "last_notified": None}
    return {
        "muted": bool(row["muted"]),
        "down_since": row["down_since"].timestamp() if row["down_since"] else None,
        "last_notified": row["last_notified"].timestamp() if row["last_notified"] else None,
    }


async def ensure_service_downtime_table(pool: asyncpg.Pool) -> None:
    await pool.execute(
        "CREATE TABLE IF NOT EXISTS service_downtime ("
        " service TEXT PRIMARY KEY,"
        " down_since TIMESTAMPTZ,"
        " last_notified TIMESTAMPTZ,"
        " updated_at TIMESTAMPTZ DEFAULT now())"
    )
    await pool.execute(
        "INSERT INTO service_downtime (service) VALUES ('api'),('database'),('bot') "
        "ON CONFLICT (service) DO NOTHING"
    )


async def load_service_states(pool: asyncpg.Pool) -> dict:
    rows = await pool.fetch("SELECT service, down_since, last_notified FROM service_downtime")
    out: dict = {}
    for r in rows:
        out[r["service"]] = {
            "down_since": r["down_since"].timestamp() if r["down_since"] else None,
            "last_notified": r["last_notified"].timestamp() if r["last_notified"] else None,
        }
    return out


async def save_service_state(
    pool: asyncpg.Pool, service: str, down_since: float | None, last_notified: float | None
) -> None:
    await pool.execute(
        "INSERT INTO service_downtime (service, down_since, last_notified, updated_at) "
        "VALUES ($1, CASE WHEN $2::float IS NULL THEN NULL ELSE to_timestamp($2) END, "
        "CASE WHEN $3::float IS NULL THEN NULL ELSE to_timestamp($3) END, now()) "
        "ON CONFLICT (service) DO UPDATE SET "
        "down_since = CASE WHEN EXCLUDED.down_since IS NULL THEN NULL "
        "ELSE EXCLUDED.down_since END, "
        "last_notified = CASE WHEN EXCLUDED.last_notified IS NULL THEN NULL "
        "ELSE EXCLUDED.last_notified END, "
        "updated_at = now()",
        service,
        down_since,
        last_notified,
    )


def _describe_outage(down: list[str]) -> str:
    names = {"api": "API", "database": "Datenbank", "bot": "Bot"}
    return " + ".join(names.get(s, s) for s in down)


def _whitelist_ids() -> set[int]:
    return {
        int(i)
        for i in os.environ.get("ADMIN_WHITELIST_IDS", "").split(",")
        if i.strip()
    }


async def send_push(pool: asyncpg.Pool, down: list[str], down_since: float) -> None:
    if not push_configured():
        log.warning("VAPID not configured — skipping push")
        return

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        log.warning("pywebpush is not installed — skipping push")
        return

    rows = await pool.fetch(
        "SELECT ps.id, ps.endpoint, ps.keys FROM push_subscriptions ps "
        "JOIN users u ON u.discord_id = ps.user_id "
        "WHERE u.role IN ('owner', 'developer', 'moderator') "
        "OR u.discord_id = ANY($1::bigint[])",
        list(_whitelist_ids()),
    )
    if not rows:
        log.info("No admin push subscriptions — nothing to send")
        return

    duration = int(_now() - down_since)
    minutes = max(1, duration // 60)
    payload = {
        "title": "⚠️ WordLock Ausfall",
        "body": f"{_describe_outage(down)} sind seit ~{minutes} Min. nicht erreichbar.",
        "icon": "/icon-192.png",
        "badge": "/icon-192.png",
        "url": "/admin",
        "tag": "wordlock-outage",
        "downId": int(down_since),
        "actions": [
            {"action": "mute", "title": "🔕 Für diesen Ausfall stummschalten"},
        ],
    }

    sent = 0
    for row in rows:
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info={
                    "endpoint": row["endpoint"],
                    "keys": json.loads(row["keys"]),
                },
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
                timeout=10,
            )
            sent += 1
        except WebPushException as exc:
            if getattr(exc.response, "status_code", None) in (404, 410):
                await pool.execute(
                    "DELETE FROM push_subscriptions WHERE id = $1", row["id"]
                )
            else:
                log.debug("Push failed: %s", exc)
        except Exception:
            log.exception("Unexpected push error")
    log.info("Sent %s push notification(s)", sent)


async def monitor_loop(pool: asyncpg.Pool) -> None:
    log.info(
        "Monitor started: down-threshold %ss, resend every %ss, check every %ss",
        DOWN_THRESHOLD,
        RESEND_INTERVAL,
        CHECK_INTERVAL,
    )
    await ensure_service_downtime_table(pool)
    while True:
        try:
            settings = await load_settings(pool)
            states = await load_service_states(pool)
            now = _now()

            checks = {
                "api": await api_is_healthy(),
                "database": await db_is_healthy(pool),
                "bot": await bot_is_healthy(pool),
            }
            down: list[str] = [s for s in SERVICES if not checks[s]]

            for service in SERVICES:
                state = states.get(service, {})
                if checks[service]:
                    if state.get("down_since") is not None:
                        log.info("Service '%s' healthy again — outage ended.", service)
                    await save_service_state(pool, service, None, None)
                else:
                    if state.get("down_since") is None:
                        log.warning("Outage started: %s down", service)
                        await save_service_state(pool, service, now, None)
                    elif not settings["muted"]:
                        age = now - state["down_since"]
                        last = state.get("last_notified")
                        if (
                            age >= DOWN_THRESHOLD
                            and (last is None or (now - last) >= RESEND_INTERVAL)
                        ):
                            await send_push(pool, down, state["down_since"])
                            last = now
                        await save_service_state(pool, service, state["down_since"], last)

            if not down and settings.get("muted"):
                await pool.execute(
                    "UPDATE monitor_settings SET muted = FALSE, updated_at = now() WHERE id = 1"
                )
        except Exception:
            log.exception("Monitor iteration failed")
        await asyncio.sleep(CHECK_INTERVAL)


async def main() -> None:
    if not DATABASE_URL:
        log.error("DATABASE_URL is required")
        raise SystemExit(1)

    pool = await asyncpg.create_pool(DATABASE_URL)
    await pool.execute(
        "CREATE TABLE IF NOT EXISTS monitor_settings ("
        " id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),"
        " muted BOOLEAN NOT NULL DEFAULT FALSE,"
        " down_since TIMESTAMPTZ,"
        " last_notified TIMESTAMPTZ,"
        " updated_at TIMESTAMPTZ DEFAULT now())"
    )
    await pool.execute(
        "INSERT INTO monitor_settings (id, muted) VALUES (1, FALSE) ON CONFLICT (id) DO NOTHING"
    )

    try:
        await asyncio.gather(url_loop(), monitor_loop(pool))
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
