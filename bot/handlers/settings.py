from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.keyboards.inline import settings_menu_keyboard
from bot.keyboards.reply import is_menu_button
from bot.texts import t

router = Router(name="settings")


@router.message(lambda m: is_menu_button(m.text, "btn_settings"))
async def open_settings(message: Message, state: FSMContext, db) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    profile = await profiles_repo.get_profile(db, message.from_user.id)
    if profile is None or not profile.is_complete:
        await message.answer(t(lang, "settings_incomplete_profile"))
        return

    await state.clear()
    await message.answer(t(lang, "settings_title"), reply_markup=settings_menu_keyboard(lang))
