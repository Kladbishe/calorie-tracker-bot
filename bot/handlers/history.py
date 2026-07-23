from aiogram import Router
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.keyboards.inline import HistoryPeriodCB, history_period_keyboard
from bot.keyboards.reply import is_menu_button
from bot.services.history import build_history_report
from bot.texts import t

router = Router(name="history")


@router.message(lambda m: is_menu_button(m.text, "btn_history"))
async def open_history(message: Message, db) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    profile = await profiles_repo.get_profile(db, message.from_user.id)
    if profile is None or not profile.is_complete:
        await message.answer(t(lang, "settings_incomplete_profile"))
        return

    await message.answer(t(lang, "history_choose_period"), reply_markup=history_period_keyboard(lang))


@router.callback_query(HistoryPeriodCB.filter())
async def show_history(call: CallbackQuery, callback_data: HistoryPeriodCB, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    report = await build_history_report(db, call.from_user.id, callback_data.period, settings.timezone, lang)
    await call.message.edit_text(report)
    await call.answer()
