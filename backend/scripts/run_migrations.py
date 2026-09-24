"""Run `alembic upgrade head` under a Postgres advisory lock.

Only the primary web container runs this on startup; the advisory lock keeps
concurrent instances from racing migrations. Uses non-blocking pg_try_advisory_lock
with bounded retries and timeouts to prevent startup hangs.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from urllib.parse import parse_qsl, urlsplit

import psycopg2

LOCK_KEY = 0x4D564750  # 'MVGP'
MAX_LOCK_WAIT_SECONDS = 20
ALEMBIC_TIMEOUT_SECONDS = 90

try:
    from app.core.database import normalize_database_url
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.getcwd())
    try:
        from app.core.database import normalize_database_url  # type: ignore[no-redef]
    except ImportError:

        def normalize_database_url(url: str) -> str:
            return url


def _conninfo(url: str) -> dict[str, str]:
    parsed = urlsplit(url)
    params = dict(parse_qsl(parsed.query))
    if "ssl" in params:
        params["sslmode"] = params.pop("ssl")
    elif "sslmode" not in params and "neon.tech" in (parsed.hostname or ""):
        params["sslmode"] = "require"
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "dbname": (parsed.path or "/").lstrip("/"),
        "user": params.pop("user", parsed.username or "postgres"),
        "password": params.pop("password", parsed.password or "postgres"),
        **params,
    }


def main() -> int:
    raw_url = os.environ.get("DATABASE_URL", "")
    if not raw_url:
        try:
            from app.core.config import settings

            raw_url = settings.DATABASE_URL
        except Exception:
            pass

    if not raw_url or "sqlite" in raw_url:
        print(
            "[run_migrations] Running alembic upgrade head directly (non-PostgreSQL)...", flush=True
        )
        try:
            res = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=os.getcwd(),
                timeout=ALEMBIC_TIMEOUT_SECONDS,
            )
            return res.returncode
        except Exception as exc:
            print(f"[run_migrations] Migration check failed: {exc}", flush=True)
            return 0

    url = normalize_database_url(raw_url)
    conn = None
    acquired = False

    try:
        print("[run_migrations] Connecting to database to check migration lock...", flush=True)
        conn = psycopg2.connect(**_conninfo(url), connect_timeout=15)
        conn.autocommit = True

        start_time = time.time()
        attempt = 1
        while time.time() - start_time < MAX_LOCK_WAIT_SECONDS:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,))
                row = cur.fetchone()
                if row and row[0]:
                    acquired = True
                    break
            print(
                f"[run_migrations] Migration lock held by another process; waiting (attempt {attempt})...",
                flush=True,
            )
            time.sleep(2)
            attempt += 1

        if not acquired:
            print(
                f"[run_migrations] Migration lock held for >{MAX_LOCK_WAIT_SECONDS}s. "
                "Assuming another instance is applying migrations; proceeding to start server.",
                flush=True,
            )
            return 0

        print(
            "[run_migrations] Migration lock acquired. Running alembic upgrade head...", flush=True
        )
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=os.getcwd(),
            timeout=ALEMBIC_TIMEOUT_SECONDS,
        )
        print(f"[run_migrations] Alembic finished with exit code {result.returncode}", flush=True)
        return result.returncode

    except subprocess.TimeoutExpired:
        print(
            f"[run_migrations] Alembic timed out after {ALEMBIC_TIMEOUT_SECONDS}s; proceeding to start server.",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"[run_migrations] Warning: migration check failed ({exc}); proceeding to start server.",
            flush=True,
        )
        return 0
    finally:
        if conn:
            if acquired:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
                    print("[run_migrations] Released advisory lock.", flush=True)
                except Exception as exc:
                    print(f"[run_migrations] Warning releasing advisory lock: {exc}", flush=True)
            with contextlib.suppress(Exception):
                conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
