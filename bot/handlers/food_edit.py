from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import food_log as food_log_repo
from bot.db import users as users_repo
from bot.keyboards.inline import TargetsCB, targets_confirm_keyboard
from bot.services.food_memory import remember_items
from bot.services.openai_service import FoodItem, food_parse_result_from_dict
from bot.states.food_log_states import FoodEditForm
from bot.texts import t
from bot.utils.dates import today_str
from bot.utils.validators import parse_target_value

router = Router(name="food_edit")


async def start_food_edit(message: Message, state: FSMContext, lang: str) -> None:
    """Entry point from the food-confirm keyboard's 'Adjust numbers' button: collapses the
    pending items (possibly spanning several meal sections) into one editable total, reusing
    the same per-field edit UI as onboarding's AI-proposed targets."""
    data = await state.get_data()
    total_kcal = total_protein = total_fat = total_carbs = total_grams = 0.0
    for entry in data.get("pending_food", []):
        result = food_parse_result_from_dict(entry["result"])
        total_kcal += result.meal_total.kcal
        total_protein += result.meal_total.protein
        total_fat += result.meal_total.fat
        total_carbs += result.meal_total.carbs
        total_grams += result.meal_total.grams

    await state.update_data(
        proposed_kcal=round(total_kcal),
        proposed_protein=round(total_protein),
        proposed_fat=round(total_fat),
        proposed_carbs=round(total_carbs),
        proposed_grams=round(total_grams),
    )
    await state.set_state(FoodEditForm.waiting_confirm)
    await message.answer(_summary_text(await state.get_data(), lang), reply_markup=targets_confirm_keyboard(lang))


def _summary_text(data: dict, lang: str) -> str:
    return (
        f"{t(lang, 'targets_current_header')}\n"
        f"{t(lang, 'target_kcal')}: {data['proposed_kcal']} {t(lang, 'unit_kcal')}\n"
        f"{t(lang, 'target_protein')}: {data['proposed_protein']} {t(lang, 'unit_g')}\n"
        f"{t(lang, 'target_fat')}: {data['proposed_fat']} {t(lang, 'unit_g')}\n"
        f"{t(lang, 'target_carbs')}: {data['proposed_carbs']} {t(lang, 'unit_g')}\n\n"
        f"{t(lang, 'targets_accept_or_edit')}"
    )


@router.callback_query(FoodEditForm.waiting_confirm, TargetsCB.filter())
async def process_food_edit_confirm(
    call: CallbackQuery, callback_data: TargetsCB, state: FSMContext, db, settings: Settings
) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    data = await state.get_data()

    if callback_data.action == "accept":
        item = FoodItem(
            name=t(lang, "food_summary_total"),
            grams=data.get("proposed_grams", 0),
            kcal=data["proposed_kcal"],
            protein=data["proposed_protein"],
            fat=data["proposed_fat"],
            carbs=data["proposed_carbs"],
        )
        date = today_str(settings.timezone)
        await food_log_repo.insert_food_entries(db, call.from_user.id, date, "unspecified", [item])
        await remember_items(db, call.from_user.id, [item])
        await state.clear()
        await call.message.edit_text(t(lang, "food_edit_saved"))
        await call.answer()
        return

    field = callback_data.action.removeprefix("edit_")
    await state.update_data(editing_field=field)
    await state.set_state(FoodEditForm.waiting_field_value)
    await call.message.answer(t(lang, "targets_field_prompt", field=t(lang, f"target_{field}")))
    await call.answer()


@router.message(FoodEditForm.waiting_field_value)
async def process_food_edit_field_value(message: Message, state: FSMContext, db) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    value = parse_target_value(message.text)
    if value is None:
        await message.answer(t(lang, "targets_field_invalid"))
        return

    data = await state.get_data()
    field = data["editing_field"]
    await state.update_data(**{f"proposed_{field}": value})

    data = await state.get_data()
    await state.set_state(FoodEditForm.waiting_confirm)
    await message.answer(_summary_text(data, lang), reply_markup=targets_confirm_keyboard(lang))
