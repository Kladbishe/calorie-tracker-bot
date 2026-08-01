from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.keyboards.inline import (
    AddPastEntryCB,
    HistoryBackCB,
    HistoryPeriodCB,
    history_period_keyboard,
    history_report_keyboard,
)
from bot.keyboards.reply import is_menu_button
from bot.services.history import build_history_report
from bot.states.food_log_states import FoodTextForm
from bot.texts import t
from bot.utils.dates import date_days_ago

router = Router(name="history")


@router.message(lambda m: is_menu_button(m.text, "btn_history"))
async def open_history(message: Message, state: FSMContext, db) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    profile = await profiles_repo.get_profile(db, message.from_user.id)
    if profile is None or not profile.is_complete:
        await message.answer(t(lang, "settings_incomplete_profile"))
        return

    await state.clear()
    await message.answer(t(lang, "history_choose_period"), reply_markup=history_period_keyboard(lang))


def _addable_dates(period: str, tz_name: str) -> list[str]:
    """Past days (excluding today) covered by the report — a missed meal can still be
    logged against any of them straight from the history view."""
    if period == "yesterday":
        return [date_days_ago(tz_name, 1)]
    if period == "week":
        return [date_days_ago(tz_name, days_ago) for days_ago in range(1, 7)]
    return []


@router.callback_query(HistoryPeriodCB.filter())
async def show_history(call: CallbackQuery, callback_data: HistoryPeriodCB, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    report = await build_history_report(db, call.from_user.id, callback_data.period, settings.timezone, lang)
    dates = _addable_dates(callback_data.period, settings.timezone)
    await call.message.edit_text(report, reply_markup=history_report_keyboard(dates, lang))
    await call.answer()


@router.callback_query(HistoryBackCB.filter())
async def back_to_period_choice(call: CallbackQuery, db) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    await call.message.edit_text(t(lang, "history_choose_period"), reply_markup=history_period_keyboard(lang))
    await call.answer()


@router.callback_query(AddPastEntryCB.filter())
async def start_add_past_entry(call: CallbackQuery, callback_data: AddPastEntryCB, state: FSMContext, db) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    await state.update_data(target_date=callback_data.date)
    await state.set_state(FoodTextForm.waiting_text_for_date)
    await call.message.answer(t(lang, "history_add_entry_prompt", date=callback_data.date))
    await call.answer()
