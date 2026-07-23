#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"

# Make sure the daily DB backup cron job is installed. Idempotent — de-dupes on every
# restart (pm2/systemd may call this script many times) instead of piling up entries.
if command -v crontab >/dev/null 2>&1; then
    CRON_CMD="0 3 * * * $PROJECT_DIR/deploy/backup_db.sh >> $PROJECT_DIR/logs/backup.log 2>&1"
    ( crontab -l 2>/dev/null | grep -vF "deploy/backup_db.sh" ; echo "$CRON_CMD" ) | crontab -
fi

# Calling the venv's python binary directly gives the same isolation as `source
# .venv/bin/activate` without needing an interactive-shell step first.
exec "$PROJECT_DIR/.venv/bin/python" -m bot.main
