import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import load_settings
from bot.db.connection import init_db
from bot.handlers import build_root_router
from bot.logging_setup import configure_logging
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.error_middleware import ErrorMiddleware
from bot.scheduler.setup import build_scheduler
from bot.services.encryption import init_fernet

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = load_settings()
    configure_logging(settings)
    init_fernet(settings.encryption_key)

    db = await init_db(settings.database_path)

    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(ErrorMiddleware())
    dp.update.outer_middleware(ActivityMiddleware())
    dp["db"] = db
    dp["settings"] = settings

    dp.include_router(build_root_router())

    scheduler = build_scheduler(bot, db, settings)
    scheduler.start()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot starting")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
