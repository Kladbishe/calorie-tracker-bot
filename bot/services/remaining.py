import aiosqlite

from bot.db import food_log as food_log_repo
from bot.db.profiles import Profile
from bot.utils.dates import today_str
from bot.utils.formatting import remaining_report


async def get_today_report(db: aiosqlite.Connection, user_id: int, profile: Profile, tz_name: str, lang: str) -> str:
    date = today_str(tz_name)
    totals = await food_log_repo.get_totals_for_date(db, user_id, date)
    return remaining_report(totals, profile, lang)


async def get_today_entries(db: aiosqlite.Connection, user_id: int, tz_name: str):
    date = today_str(tz_name)
    return await food_log_repo.get_entries_for_date(db, user_id, date)
