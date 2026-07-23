from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import users as users_repo
from bot.db import weight_log as weight_log_repo
from bot.keyboards.inline import SettingsCB, WeightCheckinCB
from bot.keyboards.reply import main_menu_keyboard
from bot.states.weight_checkin_states import WeightCheckinForm
from bot.texts import t
from bot.utils.dates import today_str, week_start_str
from bot.utils.validators import parse_weight

router = Router(name="weight_checkin")


async def _ask_weight(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(WeightCheckinForm.waiting_weight)
    await message.answer(t(lang, "weight_checkin_ask"))


@router.callback_query(SettingsCB.filter(F.field == "update_weight"))
async def settings_update_weight(call: CallbackQuery, state: FSMContext, db) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    await _ask_weight(call.message, state, lang)
    await call.answer()


@router.callback_query(WeightCheckinCB.filter())
async def weight_checkin_callback(call: CallbackQuery, callback_data: WeightCheckinCB, state: FSMContext, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    week_start = week_start_str(settings.timezone)

    if callback_data.action == "now":
        await _ask_weight(call.message, state, lang)
        await call.answer()
        return

    await weight_log_repo.upsert_checkin_status(db, call.from_user.id, week_start, "skipped")
    await call.message.edit_text(t(lang, "weight_checkin_skipped"))
    await call.answer()


@router.message(WeightCheckinForm.waiting_weight, F.text)
async def process_checkin_weight(message: Message, state: FSMContext, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    value = parse_weight(message.text)
    if value is None:
        await message.answer(t(lang, "weight_invalid"))
        return

    date = today_str(settings.timezone)
    week_start = week_start_str(settings.timezone)
    await weight_log_repo.insert_weight(db, message.from_user.id, date, value)
    await weight_log_repo.upsert_checkin_status(db, message.from_user.id, week_start, "done")

    await state.clear()
    await message.answer(t(lang, "weight_checkin_saved", value=value), reply_markup=main_menu_keyboard(lang))
