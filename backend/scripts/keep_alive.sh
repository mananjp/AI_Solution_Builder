#!/usr/bin/env bash
# AI Solution Builder — Keep-Alive Ping Script for Unix/macOS/Linux
#
# Usage:
#   ./keep_alive.sh [BACKEND_URL] [INTERVAL_MINUTES]
#
# Examples:
#   ./keep_alive.sh
#   ./keep_alive.sh https://ai-solution-builder.onrender.com 10
#
# Crontab example (runs every 10 minutes):
#   */10 * * * * /path/to/keep_alive.sh https://ai-solution-builder.onrender.com > /dev/null 2>&1

set -euo pipefail

TARGET_URL="${1:-${BACKEND_URL:-https://ai-solution-builder.onrender.com}}"
INTERVAL_MINUTES="${2:-10}"
INTERVAL_SECONDS=$((INTERVAL_MINUTES * 60))

CLEAN_URL="${TARGET_URL%/}"
HEALTH_URL="${CLEAN_URL}/ready"

ping_backend() {
    local now
    now=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    echo "[$now] Pinging $HEALTH_URL..."

    local status
    status=$(curl -s -S -o /dev/null -w "%{http_code}" \
        --connect-timeout 20 \
        --max-time 75 \
        --retry 2 \
        --retry-delay 5 \
        -H "User-Agent: KeepAlive-Script/1.0" \
        "$HEALTH_URL" || echo "failed")

    if [ "$status" -ge 200 ] && [ "$status" -lt 400 ]; then
        echo "[$now] ✅ Backend is awake! HTTP $status"
    else
        echo "[$now] ⚠️ Backend ping returned status $status"
    fi
}

# If run with --once, ping once and exit
if [ "${3:-}" = "--once" ] || [ "${1:-}" = "--once" ]; then
    ping_backend
    exit 0
fi

echo "================================================="
echo "🚀 Keep-Alive Daemon Started"
echo "   Target   : $HEALTH_URL"
echo "   Interval : Every $INTERVAL_MINUTES minutes"
echo "   Press [Ctrl+C] to stop"
echo "================================================="

# Immediate initial ping
ping_backend

while true; do
    sleep "$INTERVAL_SECONDS"
    ping_backend
done
