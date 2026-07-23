#!/usr/bin/env bash
# One-shot setup: venv + dependencies + .env + pm2, with auto-restart on crash and on reboot.
# Safe to re-run — every step below only does something if it isn't already done.
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"

echo "==> Python virtual environment"
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
"$PROJECT_DIR/.venv/bin/pip" install --upgrade pip -q
"$PROJECT_DIR/.venv/bin/pip" install -r requirements.txt -q

echo "==> .env"
if [ ! -f .env ]; then
    cp .env.example .env
    ENC_KEY=$("$PROJECT_DIR/.venv/bin/python" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    sed -i.bak "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENC_KEY|" .env && rm -f .env.bak
    echo "    Created .env with a generated ENCRYPTION_KEY."
fi

if ! grep -q '^TELEGRAM_BOT_TOKEN=.\+' .env; then
    echo "    TELEGRAM_BOT_TOKEN is empty in .env — set it, then re-run this script:"
    echo "    $PROJECT_DIR/deploy/install.sh"
    exit 1
fi

echo "==> pm2"
if ! command -v pm2 >/dev/null 2>&1; then
    if command -v npm >/dev/null 2>&1; then
        echo "    pm2 not found, installing globally via npm..."
        npm install -g pm2
    else
        echo "    pm2 (and npm) not found. Install Node.js first, then re-run this script:"
        echo "    https://pm2.keymetrics.io/docs/usage/quick-start/"
        exit 1
    fi
fi

echo "==> Daily DB backup cron job"
if command -v crontab >/dev/null 2>&1; then
    CRON_CMD="0 3 * * * $PROJECT_DIR/deploy/backup_db.sh >> $PROJECT_DIR/logs/backup.log 2>&1"
    ( crontab -l 2>/dev/null | grep -vF "deploy/backup_db.sh" ; echo "$CRON_CMD" ) | crontab - \
        || echo "    Warning: couldn't update crontab, set it up yourself if you want backups." >&2
else
    echo "    No crontab command found — skipping automatic backups, see deploy/backup_db.sh."
fi

echo "==> pm2 log rotation"
if ! pm2 list 2>/dev/null | grep -q "pm2-logrotate"; then
    pm2 install pm2-logrotate
fi
pm2 set pm2-logrotate:max_size 10M >/dev/null
pm2 set pm2-logrotate:retain 5 >/dev/null

echo "==> Starting the bot under pm2 (auto-restarts on crash)"
pm2 delete calorie-bot >/dev/null 2>&1 || true
pm2 start "$PROJECT_DIR/deploy/start.sh" --name calorie-bot
pm2 save

echo "==> Enabling auto-start on reboot"
STARTUP_CMD=$(pm2 startup 2>&1 | grep -E '^(sudo|env) ' || true)
if [ -n "$STARTUP_CMD" ]; then
    eval "$STARTUP_CMD"
    pm2 save
else
    echo "    Couldn't auto-detect the pm2 startup command — run 'pm2 startup' yourself and"
    echo "    follow the printed instructions to survive reboots."
fi

echo ""
echo "==> Done. The bot is running under pm2 as 'calorie-bot'."
echo "    pm2 logs calorie-bot     — tail logs"
echo "    pm2 restart calorie-bot"
echo "    pm2 status"
