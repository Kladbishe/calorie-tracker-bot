import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Settings
from bot.db import food_log as food_log_repo
from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.keyboards.reply import is_menu_button
from bot.services import openai_service
from bot.services.openai_service import ApiKeyInvalidError
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
    await message.answer(t(lang, "ask_advice_food"))


@router.message(AdviceForm.waiting_food, F.text)
async def give_advice(message: Message, state: FSMContext, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    await state.clear()

    profile = await profiles_repo.get_profile(db, message.from_user.id)
    service = await openai_service.get_service_for_user(
        db, message.from_user.id, settings.openai_text_model, settings.openai_vision_model
    )
    if service is None:
        await message.answer(t(lang, "food_no_api_key"))
        return

    await message.answer(t(lang, "advice_thinking"))

    date = today_str(settings.timezone)
    totals = await food_log_repo.get_totals_for_date(db, message.from_user.id, date)

    try:
        advice = await service.get_food_advice(
            food_description=message.text,
            remaining_kcal=max(profile.target_kcal - totals.kcal, 0),
            remaining_protein=max(profile.target_protein - totals.protein, 0),
            remaining_fat=max(profile.target_fat - totals.fat, 0),
            remaining_carbs=max(profile.target_carbs - totals.carbs, 0),
            goal=profile.goal,
            lang=lang,
        )
    except ApiKeyInvalidError:
        await message.answer(t(lang, "key_invalid"))
        return
    except Exception:
        logger.exception("OpenAI food advice request failed")
        await message.answer(t(lang, "food_parse_network_error"))
        return

    await message.answer(advice)
