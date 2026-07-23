import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from bot.db import users as users_repo
from bot.texts import DEFAULT_LANGUAGE, t

logger = logging.getLogger(__name__)


class ErrorMiddleware(BaseMiddleware):
    """Catches any unhandled exception per-update so one bad update never kills polling."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("Unhandled error while processing update: %s", event)

            target = None
            user_id = None
            if isinstance(event, Update):
                if event.message:
                    target = event.message
                    user_id = event.message.from_user.id
                elif event.callback_query:
                    target = event.callback_query.message
                    user_id = event.callback_query.from_user.id

            if target is not None:
                lang = DEFAULT_LANGUAGE
                db = data.get("db")
                if db is not None and user_id is not None:
                    try:
                        lang = await users_repo.get_effective_language(db, user_id)
                    except Exception:
                        pass
                try:
                    await target.answer(t(lang, "generic_error"))
                except Exception:
                    logger.exception("Failed to notify user about error")
