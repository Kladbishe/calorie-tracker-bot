import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Settings
from bot.db import food_log as food_log_repo
from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.keyboards.reply import advice_chat_keyboard, is_menu_button, main_menu_keyboard
from bot.services import gemini_service
from bot.services.ai_types import ApiKeyInvalidError, build_advice_prompt
from bot.states.advice_states import AdviceForm
from bot.texts import t
from bot.utils.dates import today_str

logger = logging.getLogger(__name__)

router = Router(name="advice")


@router.message(StateFilter(None), lambda m: is_menu_button(m.text, "btn_advice"))
async def ask_advice(message: Message, state: FSMContext, db) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    profile = await profiles_repo.get_profile(db, message.from_user.id)
    if profile is None or not profile.is_complete:
        await message.answer(t(lang, "settings_incomplete_profile"))
        return

    await state.set_state(AdviceForm.waiting_food)
    await state.update_data(advice_history=[])
    await message.answer(t(lang, "ask_advice_food"), reply_markup=advice_chat_keyboard(lang))


@router.message(AdviceForm.waiting_food, lambda m: is_menu_button(m.text, "btn_exit_advice"))
async def exit_advice(message: Message, state: FSMContext, db) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    await state.clear()
    await message.answer(t(lang, "advice_exited"), reply_markup=main_menu_keyboard(lang))


@router.message(AdviceForm.waiting_food, F.text)
async def give_advice(message: Message, state: FSMContext, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    data = await state.get_data()
    history: list[dict] = data.get("advice_history") or []

    service = await gemini_service.get_service_for_user(db, message.from_user.id, settings)
    if service is None:
        await state.clear()
        await message.answer(t(lang, "food_no_api_key"), reply_markup=main_menu_keyboard(lang))
        return

    if history:
        user_text = message.text
    else:
        profile = await profiles_repo.get_profile(db, message.from_user.id)
        date = today_str(settings.timezone)
        totals = await food_log_repo.get_totals_for_date(db, message.from_user.id, date)
        user_text = build_advice_prompt(
            food_description=message.text,
            remaining_kcal=max(profile.target_kcal - totals.kcal, 0),
            remaining_protein=max(profile.target_protein - totals.protein, 0),
            remaining_fat=max(profile.target_fat - totals.fat, 0),
            remaining_carbs=max(profile.target_carbs - totals.carbs, 0),
            goal=profile.goal,
        )

    await message.answer(t(lang, "advice_thinking"))
    history.append({"role": "user", "text": user_text})

    try:
        advice = await service.chat_advice(history=history, lang=lang)
    except ApiKeyInvalidError:
        await state.clear()
        await message.answer(t(lang, "key_invalid"), reply_markup=main_menu_keyboard(lang))
        return
    except Exception:
        logger.exception("Gemini food advice request failed")
        await message.answer(t(lang, "food_parse_network_error"))
        return

    history.append({"role": "model", "text": advice})
    await state.update_data(advice_history=history)
    await message.answer(advice)
