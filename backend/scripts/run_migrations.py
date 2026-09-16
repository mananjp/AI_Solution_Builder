"""Run `alembic upgrade head` under a Postgres advisory lock.

Both the app and builder containers call this on startup; the lock keeps a
second container from racing a migration in progress. psycopg2 (sync) is used
because all we need is `pg_advisory_lock` — no async pool involvement.
"""

from __future__ import annotations

import os
import subprocess
import sys
from urllib.parse import parse_qsl, urlsplit

import psycopg2

LOCK_KEY = 0x4D564750  # 'MVGP'

try:
    from app.core.database import normalize_database_url
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.getcwd())
    from app.core.database import normalize_database_url  # type: ignore[no-redef]


def _conninfo(url: str) -> dict[str, str]:
    parsed = urlsplit(url)
    params = dict(parse_qsl(parsed.query))
    # normalize_database_url() rewrites sslmode=... -> ssl=... for asyncpg;
    # psycopg2 expects sslmode=... instead.
    if "ssl" in params:
        params["sslmode"] = params.pop("ssl")
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "dbname": (parsed.path or "/").lstrip("/"),
        "user": params.pop("user", parsed.username or "postgres"),
        "password": params.pop("password", parsed.password or "postgres"),
        **params,
    }


def main() -> int:
    url = normalize_database_url(os.environ.get("DATABASE_URL", ""))
    conn = psycopg2.connect(**_conninfo(url), connect_timeout=30)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=os.getcwd(),
        )
        return result.returncode
    finally:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
