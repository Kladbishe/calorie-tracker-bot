from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Settings
from bot.services.stats import get_bot_stats

router = Router(name="admin")


@router.message(Command("stats"))
async def cmd_stats(message: Message, db, settings: Settings) -> None:
    if message.from_user.id not in settings.admin_telegram_ids:
        return

    stats = await get_bot_stats(db)
    await message.answer(
        "📊 Bot stats\n\n"
        f"👥 Total users: {stats.total_users}\n"
        f"✅ Onboarded: {stats.onboarded_users}\n"
        f"🟢 Active today: {stats.active_today}\n"
        f"🟢 Active this week: {stats.active_week}\n"
        f"🆕 New this week: {stats.new_week}\n"
        f"🍽 Food log entries: {stats.food_log_entries}"
    )
