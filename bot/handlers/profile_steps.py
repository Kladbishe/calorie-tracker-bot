import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.keyboards.inline import (
    ActivityCB,
    DeficitCB,
    GenderCB,
    GoalCB,
    LanguageCB,
    SettingsCB,
    TargetsCB,
    activity_level_keyboard,
    deficit_percent_keyboard,
    gender_keyboard,
    goal_keyboard,
    language_keyboard,
    settings_menu_keyboard,
    targets_confirm_keyboard,
)
from bot.keyboards.reply import main_menu_keyboard
from bot.services import openai_service
from bot.services.encryption import encrypt_api_key
from bot.services.nutrition_fallback import compute_fallback_targets
from bot.services.openai_service import ApiKeyInvalidError, OpenAIService
from bot.states.profile_form import ProfileForm
from bot.texts import t
from bot.utils.validators import parse_age, parse_height, parse_target_value, parse_weight

logger = logging.getLogger(__name__)

router = Router(name="profile_steps")


async def _get_lang(db, user_id: int) -> str:
    return await users_repo.get_effective_language(db, user_id)


async def _finish_settings(message: Message, lang: str) -> None:
    await message.answer(t(lang, "settings_saved"), reply_markup=settings_menu_keyboard(lang))


async def _prompt_chain_field(message: Message, state: FSMContext, field: str, lang: str) -> None:
    if field == "weight":
        await state.set_state(ProfileForm.waiting_weight)
        await message.answer(t(lang, "ask_weight"))
    elif field == "height":
        await state.set_state(ProfileForm.waiting_height)
        await message.answer(t(lang, "ask_height"))
    elif field == "age":
        await state.set_state(ProfileForm.waiting_age)
        await message.answer(t(lang, "ask_age"))
    elif field == "gender":
        await state.set_state(ProfileForm.waiting_gender)
        await message.answer(t(lang, "ask_gender"), reply_markup=gender_keyboard(lang))
    elif field == "activity":
        await state.set_state(ProfileForm.waiting_activity)
        await message.answer(t(lang, "ask_activity"), reply_markup=activity_level_keyboard(lang))
    elif field == "goal":
        await state.set_state(ProfileForm.waiting_goal)
        await message.answer(t(lang, "ask_goal"), reply_markup=goal_keyboard(lang))


async def _start_chain(message: Message, state: FSMContext, chain: list[str], lang: str) -> None:
    first, *rest = chain
    await state.update_data(flow="settings_edit_chain", chain=rest)
    await _prompt_chain_field(message, state, first, lang)


async def _after_field_saved(message: Message, state: FSMContext, lang: str) -> bool:
    """Handles Settings navigation after a field was saved. Returns True if it did (caller
    should stop), False if this is a normal onboarding flow and the caller should advance
    to the next onboarding step itself."""
    data = await state.get_data()
    flow = data.get("flow")

    if flow == "settings_edit_chain":
        chain = data.get("chain", [])
        if chain:
            next_field, *rest = chain
            await state.update_data(chain=rest)
            await _prompt_chain_field(message, state, next_field, lang)
            return True
        await state.clear()
        await _finish_settings(message, lang)
        return True

    if flow == "settings_edit":
        await state.clear()
        await _finish_settings(message, lang)
        return True

    return False


# ---------- Language ----------

async def ask_language(message: Message, state: FSMContext) -> None:
    await state.set_state(ProfileForm.waiting_language)
    await message.answer(t(None, "language_prompt"), reply_markup=language_keyboard())


@router.callback_query(ProfileForm.waiting_language, LanguageCB.filter())
async def process_language(call: CallbackQuery, callback_data: LanguageCB, state: FSMContext, db) -> None:
    lang = callback_data.value
    await users_repo.ensure_user(db, call.from_user.id)
    await users_repo.set_language(db, call.from_user.id, lang)
    await call.message.edit_text(t(lang, "language_saved"))

    if await _after_field_saved(call.message, state, lang):
        # Settings-menu confirmation above is an inline keyboard, which does not update the
        # persistent reply keyboard — send a follow-up so the bottom menu buttons switch language too.
        await call.message.answer(t(lang, "settings_title"), reply_markup=main_menu_keyboard(lang))
        await call.answer()
        return

    await state.set_state(ProfileForm.waiting_api_key)
    await call.message.answer(t(lang, "welcome"))
    await call.message.answer(t(lang, "ask_api_key"))
    await call.answer()


# ---------- API key ----------

async def ask_api_key(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(ProfileForm.waiting_api_key)
    await message.answer(t(lang, "ask_api_key"))


@router.message(ProfileForm.waiting_api_key, F.text)
async def process_api_key(message: Message, state: FSMContext, db, settings: Settings) -> None:
    lang = await _get_lang(db, message.from_user.id)
    raw_key = message.text.strip()
    await message.answer(t(lang, "checking_key"))

    service = OpenAIService(
        api_key=raw_key, text_model=settings.openai_text_model, vision_model=settings.openai_vision_model
    )
    try:
        await service.validate_api_key()
    except ApiKeyInvalidError:
        await message.answer(t(lang, "key_invalid"))
        return
    except Exception:
        logger.exception("Failed to validate OpenAI API key")
        await message.answer(t(lang, "key_check_failed"))
        return

    await users_repo.ensure_user(db, message.from_user.id)
    await users_repo.set_api_key(db, message.from_user.id, encrypt_api_key(raw_key))
    openai_service.cache_service(message.from_user.id, service)

    if await _after_field_saved(message, state, lang):
        return

    await state.set_state(ProfileForm.waiting_weight)
    await message.answer(t(lang, "key_accepted_ask_weight"))


# ---------- Weight ----------

@router.message(ProfileForm.waiting_weight, F.text)
async def process_weight(message: Message, state: FSMContext, db) -> None:
    lang = await _get_lang(db, message.from_user.id)
    value = parse_weight(message.text)
    if value is None:
        await message.answer(t(lang, "weight_invalid"))
        return

    await profiles_repo.upsert_profile_field(db, message.from_user.id, "weight", value)

    if await _after_field_saved(message, state, lang):
        return

    await state.set_state(ProfileForm.waiting_height)
    await message.answer(t(lang, "ask_height"))


# ---------- Height ----------

@router.message(ProfileForm.waiting_height, F.text)
async def process_height(message: Message, state: FSMContext, db) -> None:
    lang = await _get_lang(db, message.from_user.id)
    value = parse_height(message.text)
    if value is None:
        await message.answer(t(lang, "height_invalid"))
        return

    await profiles_repo.upsert_profile_field(db, message.from_user.id, "height", value)

    if await _after_field_saved(message, state, lang):
        return

    await state.set_state(ProfileForm.waiting_age)
    await message.answer(t(lang, "ask_age"))


# ---------- Age ----------

@router.message(ProfileForm.waiting_age, F.text)
async def process_age(message: Message, state: FSMContext, db) -> None:
    lang = await _get_lang(db, message.from_user.id)
    value = parse_age(message.text)
    if value is None:
        await message.answer(t(lang, "age_invalid"))
        return

    await profiles_repo.upsert_profile_field(db, message.from_user.id, "age", value)

    if await _after_field_saved(message, state, lang):
        return

    await state.set_state(ProfileForm.waiting_gender)
    await message.answer(t(lang, "ask_gender"), reply_markup=gender_keyboard(lang))


# ---------- Gender ----------

@router.callback_query(ProfileForm.waiting_gender, GenderCB.filter())
async def process_gender(call: CallbackQuery, callback_data: GenderCB, state: FSMContext, db) -> None:
    lang = await _get_lang(db, call.from_user.id)
    await profiles_repo.upsert_profile_field(db, call.from_user.id, "gender", callback_data.value)
    await call.message.edit_text(t(lang, "gender_saved", label=t(lang, f"gender_{callback_data.value}")))

    if await _after_field_saved(call.message, state, lang):
        await call.answer()
        return

    await state.set_state(ProfileForm.waiting_activity)
    await call.message.answer(t(lang, "ask_activity"), reply_markup=activity_level_keyboard(lang))
    await call.answer()


# ---------- Activity ----------

@router.callback_query(ProfileForm.waiting_activity, ActivityCB.filter())
async def process_activity(call: CallbackQuery, callback_data: ActivityCB, state: FSMContext, db) -> None:
    lang = await _get_lang(db, call.from_user.id)
    await profiles_repo.upsert_profile_field(db, call.from_user.id, "activity_level", callback_data.value)
    await call.message.edit_text(t(lang, "activity_saved", label=t(lang, f"activity_{callback_data.value}")))

    if await _after_field_saved(call.message, state, lang):
        await call.answer()
        return

    await state.set_state(ProfileForm.waiting_goal)
    await call.message.answer(t(lang, "ask_goal"), reply_markup=goal_keyboard(lang))
    await call.answer()


# ---------- Goal ----------

@router.callback_query(ProfileForm.waiting_goal, GoalCB.filter())
async def process_goal(call: CallbackQuery, callback_data: GoalCB, state: FSMContext, db, settings: Settings) -> None:
    lang = await _get_lang(db, call.from_user.id)
    await profiles_repo.upsert_profile_field(db, call.from_user.id, "goal", callback_data.value)
    await call.message.edit_text(t(lang, "goal_saved", label=t(lang, f"goal_{callback_data.value}")))

    if await _after_field_saved(call.message, state, lang):
        await call.answer()
        return

    if callback_data.value == "maintain":
        await propose_targets(call.message, state, db, settings, call.from_user.id, lang)
    else:
        await state.set_state(ProfileForm.waiting_deficit)
        key = "ask_deficit_loss" if callback_data.value == "loss" else "ask_deficit_gain"
        await call.message.answer(t(lang, key), reply_markup=deficit_percent_keyboard(lang))
    await call.answer()


# ---------- Deficit ----------

@router.callback_query(ProfileForm.waiting_deficit, DeficitCB.filter())
async def process_deficit(call: CallbackQuery, callback_data: DeficitCB, state: FSMContext, db, settings: Settings) -> None:
    lang = await _get_lang(db, call.from_user.id)
    deficit_percent = None if callback_data.value == "auto" else int(callback_data.value)
    await profiles_repo.upsert_profile_field(db, call.from_user.id, "deficit_percent", deficit_percent)
    value_label = t(lang, "deficit_ai_suggest") if deficit_percent is None else f"{deficit_percent}%"
    await call.message.edit_text(t(lang, "deficit_saved", value=value_label))

    if await _after_field_saved(call.message, state, lang):
        await call.answer()
        return

    await propose_targets(call.message, state, db, settings, call.from_user.id, lang)
    await call.answer()


# ---------- AI targets proposal + per-field editing ----------

async def propose_targets(message: Message, state: FSMContext, db, settings: Settings, user_id: int, lang: str) -> None:
    profile = await profiles_repo.get_profile(db, user_id)
    await message.answer(t(lang, "computing_targets"))

    service = await openai_service.get_service_for_user(
        db, user_id, settings.openai_text_model, settings.openai_vision_model
    )

    result = None
    if service is not None:
        try:
            result = await service.compute_nutrition_targets(
                weight=profile.weight,
                height=profile.height,
                age=profile.age,
                gender=profile.gender,
                activity_level=profile.activity_level,
                goal=profile.goal,
                deficit_percent=profile.deficit_percent,
                lang=lang,
            )
        except Exception:
            logger.exception("OpenAI target computation failed, falling back to local estimate")

    if result is None:
        result = compute_fallback_targets(
            weight=profile.weight,
            height=profile.height,
            age=profile.age,
            gender=profile.gender,
            activity_level=profile.activity_level,
            goal=profile.goal,
            deficit_percent=profile.deficit_percent,
            lang=lang,
        )

    await state.update_data(
        proposed_kcal=result.target_kcal,
        proposed_protein=result.target_protein,
        proposed_fat=result.target_fat,
        proposed_carbs=result.target_carbs,
    )
    await state.set_state(ProfileForm.waiting_ai_confirm)
    await message.answer(_targets_summary_text(result, lang), reply_markup=targets_confirm_keyboard(lang))


async def start_settings_targets_edit(message: Message, state: FSMContext, db, user_id: int, lang: str) -> None:
    """Entry point from Settings -> 'Macros manually': reuses the same confirm/edit UI,
    seeded with the user's current stored targets instead of a fresh AI proposal."""
    profile = await profiles_repo.get_profile(db, user_id)
    await state.update_data(
        flow="settings_edit",
        single_field="targets",
        proposed_kcal=profile.target_kcal or 0,
        proposed_protein=profile.target_protein or 0,
        proposed_fat=profile.target_fat or 0,
        proposed_carbs=profile.target_carbs or 0,
    )
    await state.set_state(ProfileForm.waiting_ai_confirm)
    data = await state.get_data()
    await message.answer(_targets_summary_text_from_data(data, lang), reply_markup=targets_confirm_keyboard(lang))


def _targets_summary_text(result, lang: str) -> str:
    lines = [
        t(lang, "targets_proposed_header"),
        t(lang, "targets_line", label=t(lang, "target_kcal"), value=result.target_kcal, unit=t(lang, "unit_kcal")),
        t(lang, "targets_line", label=t(lang, "target_protein"), value=result.target_protein, unit=t(lang, "unit_g")),
        t(lang, "targets_line", label=t(lang, "target_fat"), value=result.target_fat, unit=t(lang, "unit_g")),
        t(lang, "targets_line", label=t(lang, "target_carbs"), value=result.target_carbs, unit=t(lang, "unit_g")),
    ]
    if result.explanation:
        lines.append(f"\n{result.explanation}")
    lines.append(f"\n{t(lang, 'targets_accept_or_edit')}")
    return "\n".join(lines)


def _targets_summary_text_from_data(data: dict, lang: str) -> str:
    lines = [
        t(lang, "targets_current_header"),
        t(lang, "targets_line", label=t(lang, "target_kcal"), value=data["proposed_kcal"], unit=t(lang, "unit_kcal")),
        t(lang, "targets_line", label=t(lang, "target_protein"), value=data["proposed_protein"], unit=t(lang, "unit_g")),
        t(lang, "targets_line", label=t(lang, "target_fat"), value=data["proposed_fat"], unit=t(lang, "unit_g")),
        t(lang, "targets_line", label=t(lang, "target_carbs"), value=data["proposed_carbs"], unit=t(lang, "unit_g")),
        "",
        t(lang, "targets_accept_or_edit"),
    ]
    return "\n".join(lines)


@router.callback_query(ProfileForm.waiting_ai_confirm, TargetsCB.filter())
async def process_targets_confirm(call: CallbackQuery, callback_data: TargetsCB, state: FSMContext, db) -> None:
    lang = await _get_lang(db, call.from_user.id)
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
        await call.message.edit_text(t(lang, "targets_saved"))

        if await _after_field_saved(call.message, state, lang):
            await call.answer()
            return

        await state.clear()
        await call.message.answer(t(lang, "onboarding_complete"), reply_markup=main_menu_keyboard(lang))
        await call.answer()
        return

    field = callback_data.action.removeprefix("edit_")
    await state.update_data(editing_target_field=field)
    await state.set_state(ProfileForm.waiting_target_field_value)
    await call.message.answer(t(lang, "targets_field_prompt", field=t(lang, f"target_{field}")))
    await call.answer()


@router.message(ProfileForm.waiting_target_field_value, F.text)
async def process_target_field_value(message: Message, state: FSMContext, db) -> None:
    lang = await _get_lang(db, message.from_user.id)
    value = parse_target_value(message.text)
    if value is None:
        await message.answer(t(lang, "targets_field_invalid"))
        return

    data = await state.get_data()
    field = data["editing_target_field"]
    await state.update_data(**{f"proposed_{field}": value})

    data = await state.get_data()
    await state.set_state(ProfileForm.waiting_ai_confirm)
    await message.answer(_targets_summary_text_from_data(data, lang), reply_markup=targets_confirm_keyboard(lang))


# ---------- Settings entry points into the shared steps ----------

@router.callback_query(SettingsCB.filter(~F.field.in_({"update_weight"})))
async def settings_field_entry(call: CallbackQuery, callback_data: SettingsCB, state: FSMContext, db) -> None:
    field = callback_data.field
    user_id = call.from_user.id
    lang = await _get_lang(db, user_id)
    await call.answer()

    if field == "close":
        await call.message.edit_reply_markup(reply_markup=None)
        return

    if field == "basic_info":
        await _start_chain(call.message, state, ["weight", "height", "age", "gender"], lang)
        return

    if field == "goal_activity":
        await _start_chain(call.message, state, ["activity", "goal"], lang)
        return

    if field == "deficit":
        await state.update_data(flow="settings_edit", single_field="deficit")
        await state.set_state(ProfileForm.waiting_deficit)
        await call.message.answer(t(lang, "settings_ask_deficit"), reply_markup=deficit_percent_keyboard(lang))
        return

    if field == "targets":
        await start_settings_targets_edit(call.message, state, db, user_id, lang)
        return

    if field == "api_key":
        await state.update_data(flow="settings_edit", single_field="api_key")
        await state.set_state(ProfileForm.waiting_api_key)
        await call.message.answer(t(lang, "settings_ask_new_api_key"))
        return

    if field == "language":
        await state.update_data(flow="settings_edit", single_field="language")
        await state.set_state(ProfileForm.waiting_language)
        await call.message.answer(t(None, "language_prompt"), reply_markup=language_keyboard())
        return
