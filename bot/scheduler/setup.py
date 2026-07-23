from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import Settings
from bot.scheduler.jobs import daily_reminder_sweep_job, weekly_weight_checkin_job

DAY_NAME_TO_CRON = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


def build_scheduler(bot: Bot, db, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    hour, minute = (int(p) for p in settings.weekly_weight_check_time.split(":"))
    cron_day = DAY_NAME_TO_CRON[settings.weekly_weight_check_day.lower()]

    scheduler.add_job(
        weekly_weight_checkin_job,
        trigger=CronTrigger(day_of_week=cron_day, hour=hour, minute=minute, timezone=settings.timezone),
        kwargs={"bot": bot, "db": db, "settings": settings},
        id="weekly_weight_checkin",
        replace_existing=True,
    )

    scheduler.add_job(
        daily_reminder_sweep_job,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=settings.timezone),
        kwargs={"bot": bot, "db": db, "settings": settings},
        id="daily_weight_reminder_sweep",
        replace_existing=True,
    )

    return scheduler
