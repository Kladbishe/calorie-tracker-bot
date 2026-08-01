from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.db import weight_log as weight_log_repo
from bot.keyboards.inline import SettingsCB, TargetsCB, WeightCheckinCB, targets_confirm_keyboard
from bot.keyboards.reply import main_menu_keyboard
from bot.services.adaptive_targets import suggest_target_adjustment
from bot.states.weight_checkin_states import WeightCheckinForm
from bot.texts import t
from bot.utils.dates import today_str, week_start_str
from bot.utils.validators import parse_target_value, parse_weight

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

    profile = await profiles_repo.get_profile(db, message.from_user.id)
    adjustment = await suggest_target_adjustment(db, message.from_user.id, profile, value, date)
    if adjustment is None:
        return

    await state.update_data(
        proposed_kcal=adjustment.target_kcal,
        proposed_protein=adjustment.target_protein,
        proposed_fat=adjustment.target_fat,
        proposed_carbs=adjustment.target_carbs,
    )
    await state.set_state(WeightCheckinForm.waiting_adjust_confirm)
    intro = t(
        lang,
        "weight_trend_adjust_intro",
        days=adjustment.days_elapsed,
        change_kg=f"{adjustment.weight_change_kg:+.1f}",
        avg_kcal=round(adjustment.avg_daily_kcal),
        current_kcal=profile.target_kcal,
    )
    await state.update_data(intro=intro)
    await message.answer(_adjustment_summary_text(intro, await state.get_data(), lang), reply_markup=targets_confirm_keyboard(lang))


def _adjustment_summary_text(intro: str, data: dict, lang: str) -> str:
    return "\n".join(
        [
            intro,
            "",
            t(lang, "targets_current_header"),
            t(lang, "targets_line", label=t(lang, "target_kcal"), value=data["proposed_kcal"], unit=t(lang, "unit_kcal")),
            t(lang, "targets_line", label=t(lang, "target_protein"), value=data["proposed_protein"], unit=t(lang, "unit_g")),
            t(lang, "targets_line", label=t(lang, "target_fat"), value=data["proposed_fat"], unit=t(lang, "unit_g")),
            t(lang, "targets_line", label=t(lang, "target_carbs"), value=data["proposed_carbs"], unit=t(lang, "unit_g")),
            "",
            t(lang, "targets_accept_or_edit"),
        ]
    )


@router.callback_query(WeightCheckinForm.waiting_adjust_confirm, TargetsCB.filter())
async def process_adjust_confirm(call: CallbackQuery, callback_data: TargetsCB, state: FSMContext, db) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    data = await state.get_data()

    if callback_data.action == "accept":
        await profiles_repo.save_targets(
            db,
            call.from_user.id,
            kcal=data["proposed_kcal"],
            protein=data["proposed_protein"],
            fat=data["proposed_fat"],
            carbs=data["proposed_carbs"],
        )
        await state.clear()
        await call.message.edit_text(t(lang, "weight_trend_targets_saved"))
        await call.answer()
        return

    field = callback_data.action.removeprefix("edit_")
    await state.update_data(editing_field=field)
    await state.set_state(WeightCheckinForm.waiting_adjust_field)
    await call.message.answer(t(lang, "targets_field_prompt", field=t(lang, f"target_{field}")))
    await call.answer()


@router.message(WeightCheckinForm.waiting_adjust_field)
async def process_adjust_field_value(message: Message, state: FSMContext, db) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    value = parse_target_value(message.text)
    if value is None:
        await message.answer(t(lang, "targets_field_invalid"))
        return

    data = await state.get_data()
    field = data["editing_field"]
    await state.update_data(**{f"proposed_{field}": value})

    data = await state.get_data()
    await state.set_state(WeightCheckinForm.waiting_adjust_confirm)
    await message.answer(_adjustment_summary_text(data["intro"], data, lang), reply_markup=targets_confirm_keyboard(lang))
