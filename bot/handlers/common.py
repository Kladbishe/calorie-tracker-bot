from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.db import users as users_repo
from bot.texts import t

router = Router(name="common")


@router.message(Command("help"))
async def cmd_help(message: Message, db) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    await message.answer(t(lang, "help_text"))


@router.message()
async def fallback(message: Message, state: FSMContext, db) -> None:
    """Last-resort catch-all, deliberately with no state filter: without it, a message that
    doesn't match the handler for whatever state the user happens to be stuck in (e.g. a photo
    sent while mid-way through an unrelated text-only flow) was silently dropped — no handler
    matched, so the user got no response at all. Clearing the state here means one stray
    message is always enough to unstick them instead of repeating the same dead end forever."""
    await state.clear()
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    await message.answer(t(lang, "fallback_text"))
