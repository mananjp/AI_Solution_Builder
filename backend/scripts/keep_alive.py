#!/usr/bin/env python3
"""
AI Solution Builder — Backend Keep-Alive Ping Script

Keeps hosted backends (e.g. Render free tier) awake by sending periodic
HTTP GET requests to the health or readiness endpoint before the idle timeout (15 mins).

Usage:
    # Run in continuous loop (every 10 minutes)
    python keep_alive.py

    # Specify custom URL
    python keep_alive.py --url https://ai-solution-builder.onrender.com

    # Run once (for system cron / Windows Task Scheduler)
    python keep_alive.py --once

    # Custom interval and endpoint
    python keep_alive.py --interval 10 --endpoint /ready
"""

import argparse
import contextlib
import datetime
import os
import sys
import time
import urllib.request
from urllib.error import HTTPError, URLError

# Ensure UTF-8 output on Windows consoles if supported
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_URL = os.getenv("BACKEND_URL", "https://ai-solution-builder.onrender.com")
DEFAULT_ENDPOINT = os.getenv("HEALTH_ENDPOINT", "/ready")
DEFAULT_INTERVAL_MINUTES = 10
DEFAULT_TIMEOUT_SECONDS = 75  # Render free tier cold starts can take up to ~50s


def ping(url: str, endpoint: str = "/health", timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bool:
    """Send a GET request to the target health endpoint."""
    base = url.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    full_url = f"{base}{path}"

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_time = time.time()

    req = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": "AI-Solution-Builder-KeepAlive/1.0",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            elapsed = round(time.time() - start_time, 2)
            print(f"[{now_str}] [OK] {full_url} responded with HTTP {status} in {elapsed}s")
            return 200 <= status < 400
    except HTTPError as e:
        elapsed = round(time.time() - start_time, 2)
        print(
            f"[{now_str}] [WARN] {full_url} returned HTTP error {e.code}: {e.reason} ({elapsed}s)"
        )
        return False
    except URLError as e:
        elapsed = round(time.time() - start_time, 2)
        print(f"[{now_str}] [FAIL] {full_url} failed to connect: {e.reason} ({elapsed}s)")
        return False
    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        print(f"[{now_str}] [FAIL] Unexpected error pinging {full_url}: {e} ({elapsed}s)")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Keep backend awake with periodic HTTP pings")
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Target backend base URL (default: {DEFAULT_URL} or $BACKEND_URL)",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"Health check endpoint path (default: {DEFAULT_ENDPOINT} or $HEALTH_ENDPOINT)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL_MINUTES,
        help=f"Ping interval in minutes for loop mode (default: {DEFAULT_INTERVAL_MINUTES})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS}s)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit immediately (useful for crontab or task schedulers)",
    )

    args = parser.parse_args()

    if args.once:
        success = ping(args.url, endpoint=args.endpoint, timeout=args.timeout)
        sys.exit(0 if success else 1)

    print("=" * 65)
    print("AI Solution Builder — Keep-Alive Daemon Started")
    print(f"   Target URL : {args.url.rstrip('/')}{args.endpoint}")
    print(f"   Interval   : Every {args.interval} minutes")
    print(f"   Timeout    : {args.timeout} seconds")
    print("   Press Ctrl+C to stop.")
    print("=" * 65)

    # Initial immediate ping
    ping(args.url, endpoint=args.endpoint, timeout=args.timeout)

    interval_seconds = args.interval * 60
    while True:
        try:
            time.sleep(interval_seconds)
            ping(args.url, endpoint=args.endpoint, timeout=args.timeout)
        except KeyboardInterrupt:
            print("\nKeep-alive daemon stopped.")
            break


if __name__ == "__main__":
    main()
