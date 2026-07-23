import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import food_log as food_log_repo
from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.keyboards.inline import FoodConfirmCB, food_confirm_keyboard, manage_food_keyboard
from bot.services import openai_service
from bot.services.food_memory import get_known_items_hint, remember_items
from bot.services.openai_service import FoodParseError, food_parse_result_from_dict, food_parse_result_to_dict
from bot.states.food_log_states import FoodTextForm
from bot.texts import t, t_random
from bot.utils.dates import today_str
from bot.utils.formatting import food_summary
from bot.utils.meal_parsing import split_by_meal_sections

logger = logging.getLogger(__name__)

router = Router(name="food_text")


@router.message(StateFilter(None), F.text)
async def handle_food_text(message: Message, state: FSMContext, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    profile = await profiles_repo.get_profile(db, message.from_user.id)
    if profile is None or not profile.is_complete:
        await message.answer(t(lang, "settings_incomplete_profile"))
        return

    service = await openai_service.get_service_for_user(
        db, message.from_user.id, settings.openai_text_model, settings.openai_vision_model
    )
    if service is None:
        await message.answer(t(lang, "food_no_api_key"))
        return

    sections = split_by_meal_sections(message.text)
    await message.answer(t_random(lang, "calculating"))

    pending = []
    summaries = []
    for meal_type, segment_text in sections:
        known_items = await get_known_items_hint(db, message.from_user.id, segment_text)
        try:
            result = await service.parse_food_text(segment_text, known_items=known_items, lang=lang)
        except FoodParseError as e:
            await message.answer(t(lang, "food_item_parse_failed", text=segment_text.strip()[:50], error=e))
            continue
        except Exception:
            logger.exception("OpenAI food text parsing failed")
            await message.answer(t(lang, "food_parse_network_error"))
            return

        pending.append({"meal_type": meal_type, "result": food_parse_result_to_dict(result)})
        summaries.append(food_summary(result, lang))

    if not pending:
        await message.answer(t(lang, "food_nothing_recognized"))
        return

    await state.update_data(pending_food=pending)
    await state.set_state(FoodTextForm.waiting_confirm)
    await message.answer("\n\n".join(summaries), reply_markup=food_confirm_keyboard(lang))


@router.callback_query(FoodTextForm.waiting_confirm, FoodConfirmCB.filter())
async def confirm_food_text(call: CallbackQuery, callback_data: FoodConfirmCB, state: FSMContext, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    if callback_data.action == "fix":
        await state.clear()
        await call.message.edit_text(t(lang, "food_fix_prompt"))
        await call.answer()
        return

    data = await state.get_data()
    date = today_str(settings.timezone)
    for entry in data.get("pending_food", []):
        result = food_parse_result_from_dict(entry["result"])
        await food_log_repo.insert_food_entries(db, call.from_user.id, date, entry["meal_type"], result.items)
        await remember_items(db, call.from_user.id, result.items)

    await state.clear()
    await call.message.edit_text(t_random(lang, "food_saved"), reply_markup=manage_food_keyboard(lang))
    await call.answer()
