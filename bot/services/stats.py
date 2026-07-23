from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiosqlite

from bot.db import profiles as profiles_repo


@dataclass
class BotStats:
    total_users: int
    onboarded_users: int
    active_today: int
    active_week: int
    new_week: int
    food_log_entries: int


async def _count(db: aiosqlite.Connection, query: str, params: tuple = ()) -> int:
    cursor = await db.execute(query, params)
    row = await cursor.fetchone()
    return row[0]


async def get_bot_stats(db: aiosqlite.Connection) -> BotStats:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    total_users = await _count(db, "SELECT COUNT(*) FROM users")
    onboarded_users = len(await profiles_repo.get_all_complete_profiles(db))
    active_today = await _count(db, "SELECT COUNT(*) FROM users WHERE last_seen_at >= ?", (today_start,))
    active_week = await _count(db, "SELECT COUNT(*) FROM users WHERE last_seen_at >= ?", (week_ago,))
    new_week = await _count(db, "SELECT COUNT(*) FROM users WHERE created_at >= ?", (week_ago,))
    food_log_entries = await _count(db, "SELECT COUNT(*) FROM food_log")

    return BotStats(
        total_users=total_users,
        onboarded_users=onboarded_users,
        active_today=active_today,
        active_week=active_week,
        new_week=new_week,
        food_log_entries=food_log_entries,
    )
