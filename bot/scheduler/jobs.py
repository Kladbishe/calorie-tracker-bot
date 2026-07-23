import logging
from datetime import datetime, timezone

from aiogram import Bot

from bot.config import Settings
from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.db import weight_log as weight_log_repo
from bot.keyboards.inline import weight_checkin_keyboard
from bot.texts import t
from bot.utils.dates import week_start_str

logger = logging.getLogger(__name__)


async def weekly_weight_checkin_job(bot: Bot, db, settings: Settings) -> None:
    week_start = week_start_str(settings.timezone)
    profiles = await profiles_repo.get_all_complete_profiles(db)

    for profile in profiles:
        await weight_log_repo.upsert_checkin_status(db, profile.user_id, week_start, "pending")
        lang = await users_repo.get_effective_language(db, profile.user_id)
        try:
            await bot.send_message(
                profile.user_id,
                t(lang, "weight_checkin_prompt"),
                reply_markup=weight_checkin_keyboard(lang),
            )
        except Exception:
            logger.exception("Failed to send weekly weight check-in to user %s", profile.user_id)


async def daily_reminder_sweep_job(bot: Bot, db, settings: Settings) -> None:
    """Re-prompts users whose weekly check-in is still pending/skipped. Skipped on the
    configured weekly check-in day itself, since weekly_weight_checkin_job already covers it."""
    today_weekday = datetime.now().astimezone().strftime("%A").lower()
    if today_weekday == settings.weekly_weight_check_day.lower():
        return

    week_start = week_start_str(settings.timezone)
    pending = await weight_log_repo.get_pending_checkins(db, week_start)
    now_iso = datetime.now(timezone.utc).isoformat()

    for row in pending:
        lang = await users_repo.get_effective_language(db, row["user_id"])
        try:
            await bot.send_message(
                row["user_id"],
                t(lang, "weight_reminder"),
                reply_markup=weight_checkin_keyboard(lang),
            )
            await weight_log_repo.mark_reminder_sent(db, row["user_id"], week_start, now_iso)
        except Exception:
            logger.exception("Failed to send weight check-in reminder to user %s", row["user_id"])
