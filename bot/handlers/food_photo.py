import base64
import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import food_log as food_log_repo
from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.handlers.food_edit import start_food_edit
from bot.keyboards.inline import FoodConfirmCB, food_confirm_keyboard, manage_food_keyboard
from bot.services import gemini_service
from bot.services.ai_types import FoodParseError, food_parse_result_from_dict, food_parse_result_to_dict
from bot.services.food_memory import get_known_items_hint, remember_items
from bot.states.food_log_states import FoodPhotoForm
from bot.texts import t, t_random
from bot.utils.dates import today_str
from bot.utils.formatting import food_summary

logger = logging.getLogger(__name__)

router = Router(name="food_photo")


@router.message(StateFilter(None), F.photo)
async def handle_food_photo(message: Message, state: FSMContext, db, settings: Settings, bot: Bot) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    profile = await profiles_repo.get_profile(db, message.from_user.id)
    if profile is None or not profile.is_complete:
        await message.answer(t(lang, "settings_incomplete_profile"))
        return

    service = await gemini_service.get_service_for_user(db, message.from_user.id, settings)
    if service is None:
        await message.answer(t(lang, "food_no_api_key"))
        return

    file_io = await bot.download(message.photo[-1])
    image_b64 = base64.b64encode(file_io.read()).decode()

    if message.caption:
        await _parse_and_confirm(message, state, db, settings, service, image_b64, message.caption, message.from_user.id, lang)
        return

    await state.update_data(photo_b64=image_b64)
    await state.set_state(FoodPhotoForm.waiting_grams)
    await message.answer(t(lang, "photo_ask_grams"))


@router.message(FoodPhotoForm.waiting_grams, F.text)
async def handle_photo_grams(message: Message, state: FSMContext, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    data = await state.get_data()
    image_b64 = data.get("photo_b64")
    if not image_b64:
        await state.clear()
        await message.answer(t(lang, "photo_lost_state"))
        return

    service = await gemini_service.get_service_for_user(db, message.from_user.id, settings)
    await _parse_and_confirm(message, state, db, settings, service, image_b64, message.text, message.from_user.id, lang)


async def _parse_and_confirm(
    message: Message,
    state: FSMContext,
    db,
    settings: Settings,
    service,
    image_b64: str,
    grams_hint: str,
    user_id: int,
    lang: str,
) -> None:
    await message.answer(t(lang, "photo_recognizing"))
    image_bytes = base64.b64decode(image_b64)
    known_items = await get_known_items_hint(db, user_id, grams_hint)

    try:
        result = await service.parse_food_photo(image_bytes, "image/jpeg", grams_hint, known_items=known_items, lang=lang)
    except FoodParseError as e:
        await state.clear()
        await message.answer(f"{e}{t(lang, 'photo_unreadable_suffix')}")
        return
    except Exception:
        logger.exception("Gemini food photo parsing failed")
        await state.clear()
        await message.answer(t(lang, "food_parse_network_error"))
        return

    await state.update_data(pending_food=[{"meal_type": "unspecified", "result": food_parse_result_to_dict(result)}])
    await state.set_state(FoodPhotoForm.waiting_confirm)
    await message.answer(food_summary(result, lang), reply_markup=food_confirm_keyboard(lang))


@router.callback_query(FoodPhotoForm.waiting_confirm, FoodConfirmCB.filter())
async def confirm_food_photo(call: CallbackQuery, callback_data: FoodConfirmCB, state: FSMContext, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    if callback_data.action == "fix":
        await state.clear()
        await call.message.edit_text(t(lang, "photo_fix_prompt"))
        await call.answer()
        return

    if callback_data.action == "edit_numbers":
        await start_food_edit(call.message, state, lang)
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
