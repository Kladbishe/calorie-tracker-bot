from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import food_log as food_log_repo
from bot.db import profiles as profiles_repo
from bot.db import users as users_repo
from bot.keyboards.inline import ConfirmDeleteCB, DeleteFoodCB, ManageFoodCB, food_entries_keyboard, manage_food_keyboard
from bot.keyboards.reply import is_menu_button
from bot.services.remaining import get_today_entries, get_today_report
from bot.texts import t

router = Router(name="remaining")


@router.message(lambda m: is_menu_button(m.text, "btn_remaining"))
async def show_remaining(message: Message, state: FSMContext, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, message.from_user.id)
    profile = await profiles_repo.get_profile(db, message.from_user.id)
    if profile is None or not profile.is_complete:
        await message.answer(t(lang, "settings_incomplete_profile"))
        return

    await state.clear()
    report = await get_today_report(db, message.from_user.id, profile, settings.timezone, lang)
    entries = await get_today_entries(db, message.from_user.id, settings.timezone)
    markup = manage_food_keyboard(lang) if entries else None
    await message.answer(report, reply_markup=markup)


@router.callback_query(ManageFoodCB.filter())
async def open_manage_entries(call: CallbackQuery, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    entries = await get_today_entries(db, call.from_user.id, settings.timezone)
    if entries:
        await call.message.edit_reply_markup(reply_markup=food_entries_keyboard(entries, lang))
    await call.answer()


@router.callback_query(DeleteFoodCB.filter())
async def ask_delete_confirmation(call: CallbackQuery, callback_data: DeleteFoodCB, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)
    entries = await get_today_entries(db, call.from_user.id, settings.timezone)
    await call.message.edit_reply_markup(
        reply_markup=food_entries_keyboard(entries, lang, confirming_id=callback_data.entry_id)
    )

    target = next((row for row in entries if row["id"] == callback_data.entry_id), None)
    if target is not None:
        await call.answer(
            t(lang, "confirm_delete_prompt", name=target["item_name"], kcal=round(target["kcal"]), unit=t(lang, "unit_kcal"))
        )
    else:
        await call.answer()


@router.callback_query(ConfirmDeleteCB.filter())
async def confirm_delete_entry(call: CallbackQuery, callback_data: ConfirmDeleteCB, db, settings: Settings) -> None:
    lang = await users_repo.get_effective_language(db, call.from_user.id)

    if callback_data.yes == "y":
        await food_log_repo.delete_entry(db, callback_data.entry_id, call.from_user.id)
        await call.answer(t(lang, "entry_deleted"))
    else:
        await call.answer()

    entries = await get_today_entries(db, call.from_user.id, settings.timezone)
    if entries:
        await call.message.edit_reply_markup(reply_markup=food_entries_keyboard(entries, lang))
    else:
        await call.message.edit_reply_markup(reply_markup=None)
