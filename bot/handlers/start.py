from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.handlers.profile_steps import ask_api_key, ask_language
from bot.keyboards.reply import main_menu_keyboard
from bot.texts import DEFAULT_LANGUAGE, t

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db) -> None:
    await users_repo.ensure_user(db, message.from_user.id)
    profile = await profiles_repo.get_profile(db, message.from_user.id)
    language = await users_repo.get_language(db, message.from_user.id)

    if profile is not None and profile.is_complete:
        lang = language or DEFAULT_LANGUAGE
        await message.answer(t(lang, "welcome_back"), reply_markup=main_menu_keyboard(lang))
        return

    await state.clear()

    if language is None:
        await ask_language(message, state)
        return

    await message.answer(t(language, "welcome"))
    await ask_api_key(message, state, language)
