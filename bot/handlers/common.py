from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.types import Message

from bot.db import users as users_repo
from bot.texts import t

router = Router(name="common")


@router.message(Command("help"))
async def cmd_help(message: Message, db) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    await message.answer(t(lang, "help_text"))


@router.message(StateFilter(None))
async def fallback(message: Message, db) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    await message.answer(t(lang, "fallback_text"))
