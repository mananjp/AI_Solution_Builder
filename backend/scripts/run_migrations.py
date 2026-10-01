"""Run `alembic upgrade head` under a Postgres advisory lock.

Only the primary web container runs this on startup; the advisory lock keeps
concurrent instances from racing migrations. Uses non-blocking pg_try_advisory_lock
with bounded retries and fails startup if the lock or migration cannot complete.
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


def _conninfo(url: str, direct: bool = False) -> dict[str, str]:
    parsed = urlsplit(url)
    params = dict(parse_qsl(parsed.query))
    if "ssl" in params:
        params["sslmode"] = params.pop("ssl")
    elif "sslmode" not in params and "neon.tech" in (parsed.hostname or ""):
        params["sslmode"] = "require"

    host = parsed.hostname or "localhost"
    if direct and "-pooler" in host and "neon.tech" in host:
        host = host.replace("-pooler", "")

    return {
        "host": host,
        "port": parsed.port or 5432,
        "dbname": (parsed.path or "/").lstrip("/"),
        "user": params.pop("user", parsed.username or "postgres"),
        "password": params.pop("password", parsed.password or "postgres"),
        **params,
    }


def is_database_at_head(conn: psycopg2.extensions.connection) -> bool:
    """Check if the database schema is already at the latest Alembic revision."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(cfg)
        heads = set(script.get_heads())
        if not heads:
            return True

        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version')"
            )
            exists = cur.fetchone()[0]
            if not exists:
                return False
            cur.execute("SELECT version_num FROM alembic_version")
            db_versions = {row[0] for row in cur.fetchall()}
            return db_versions == heads
    except Exception as exc:
        print(
            f"[run_migrations] Notice: could not verify alembic version directly: {exc}", flush=True
        )
        return False


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
            return 1

    url = normalize_database_url(raw_url)
    conn = None
    acquired = False

    try:
        print("[run_migrations] Connecting to database to check migration status...", flush=True)
        # Prefer direct connection over pooled host (e.g. Neon -pooler) to prevent
        # PgBouncer from caching session-level advisory locks on idle backends.
        try:
            conn = psycopg2.connect(**_conninfo(url, direct=True), connect_timeout=10)
        except Exception as conn_err:
            print(
                f"[run_migrations] Direct connection attempt failed ({conn_err}); falling back to default...",
                flush=True,
            )
            conn = psycopg2.connect(**_conninfo(url, direct=False), connect_timeout=15)
        conn.autocommit = True

        # Fast path: if migrations are already at head, no migration or lock needed.
        if is_database_at_head(conn):
            print(
                "[run_migrations] Database schema is already at head. No migrations required.",
                flush=True,
            )
            return 0

        start_time = time.time()
        attempt = 1
        while time.time() - start_time < MAX_LOCK_WAIT_SECONDS:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,))
                row = cur.fetchone()
                if row and row[0]:
                    acquired = True
                    break

            # If another process was running migrations, check if it just finished.
            if is_database_at_head(conn):
                print(
                    "[run_migrations] Migrations completed by another process. Database is now at head.",
                    flush=True,
                )
                return 0

            print(
                f"[run_migrations] Migration lock held by another process; waiting (attempt {attempt})...",
                flush=True,
            )
            time.sleep(2)
            attempt += 1

        if not acquired:
            if is_database_at_head(conn):
                print(
                    "[run_migrations] Lock wait timed out, but database is already at head. Safe to proceed.",
                    flush=True,
                )
                return 0

            # Inspect if an idle pooled connection is holding the advisory lock.
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT a.pid, a.state, a.query
                        FROM pg_locks l
                        JOIN pg_stat_activity a ON l.pid = a.pid
                        WHERE l.locktype = 'advisory' AND (l.objid = %s OR l.classid = %s)
                        """,
                        (LOCK_KEY, LOCK_KEY),
                    )
                    holders = cur.fetchall()
                    idle_holders = [h for h in holders if h[1] == "idle"]
                    if idle_holders:
                        print(
                            f"[run_migrations] Found stale idle lock holder(s): {idle_holders}. Terminating...",
                            flush=True,
                        )
                        for h in idle_holders:
                            cur.execute("SELECT pg_terminate_backend(%s)", (h[0],))
                        time.sleep(1)
                        cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,))
                        row = cur.fetchone()
                        if row and row[0]:
                            acquired = True
            except Exception as exc:
                print(f"[run_migrations] Could not inspect/clear lock holders: {exc}", flush=True)

        if not acquired and not is_database_at_head(conn):
            print(
                f"[run_migrations] Migration lock held for >{MAX_LOCK_WAIT_SECONDS}s and database is not at head. "
                "Cannot safely start while another instance may be applying migrations.",
                flush=True,
            )
            return 1

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
            f"[run_migrations] Alembic timed out after {ALEMBIC_TIMEOUT_SECONDS}s; aborting startup.",
            flush=True,
        )
        return 1
    except Exception as exc:
        print(
            f"[run_migrations] Migration check failed ({exc}); aborting startup.",
            flush=True,
        )
        return 1
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
