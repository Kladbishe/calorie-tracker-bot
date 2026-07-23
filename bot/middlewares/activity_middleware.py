import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from bot.db import users as users_repo

logger = logging.getLogger(__name__)


class ActivityMiddleware(BaseMiddleware):
    """Stamps users.last_seen_at on every update, so /stats can report daily/weekly active users."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user_id = None
        if isinstance(event, Update):
            if event.message:
                user_id = event.message.from_user.id
            elif event.callback_query:
                user_id = event.callback_query.from_user.id

        db = data.get("db")
        if db is not None and user_id is not None:
            try:
                await users_repo.touch_last_seen(db, user_id)
            except Exception:
                logger.exception("Failed to update last_seen_at for user %s", user_id)

        return await handler(event, data)
