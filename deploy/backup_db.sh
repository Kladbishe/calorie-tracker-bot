#!/usr/bin/env bash
set -euo pipefail

DB_PATH="/home/pi/calorie_bot/data/bot.db"
BACKUP_DIR="/home/pi/calorie_bot/backups"

mkdir -p "$BACKUP_DIR"
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/bot-$(date +%F).db'"
find "$BACKUP_DIR" -name 'bot-*.db' -mtime +30 -delete
