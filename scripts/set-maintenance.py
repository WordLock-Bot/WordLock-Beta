#!/usr/bin/env python3
"""set-maintenance: beendet den WordLock-Wartungsmodus in der Datenbank.

Setzt das `maintenance_mode`-Flag des neuesten Updates auf FALSE und stellt
alle Server, die auf Status 'maintenance' stehen, zurück auf 'active'.

Die DATABASE_URL wird aus der Umgebung, dem .env-File im Repo-Root oder
einem lokalen Default gelesen.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg

REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_URL = "postgresql://wordlock:wordlock@localhost:5432/wordlock"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_file = REPO_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    return load_env().get("DATABASE_URL", DEFAULT_DATABASE_URL)


def _parse_count(result: str) -> int:
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return 0


async def main() -> None:
    dsn = database_url()
    print(f"Verbinde mit Datenbank ... ({dsn})")
    conn = await asyncpg.connect(dsn)
    try:
        flag_res = await conn.execute(
            "UPDATE updates SET maintenance_mode = FALSE "
            "WHERE id = (SELECT id FROM updates ORDER BY date DESC, id DESC LIMIT 1)"
        )
        server_res = await conn.execute(
            "UPDATE servers SET status = 'active' WHERE status = 'maintenance'"
        )

        maintenance = await conn.fetchval(
            "SELECT maintenance_mode FROM updates ORDER BY date DESC, id DESC LIMIT 1"
        )

        print(f"Wartungsmodus deaktiviert: {_parse_count(flag_res)} Update-Zeile(n) angepasst.")
        print(
            f"Server reaktiviert: {_parse_count(server_res)} Server von 'maintenance' "
            "auf 'active' gesetzt."
        )
        print(f"Aktueller Wartungsmodus: {'AKTIV' if maintenance else 'INAKTIV'}")
    finally:
        await conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (ConnectionError, OSError) as exc:
        print(f"Fehler: Konnte keine Verbindung zur Datenbank herstellen. {exc}")
        raise SystemExit(1)