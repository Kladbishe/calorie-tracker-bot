from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.texts import LANGUAGE_NAMES, LANGUAGES, t


class LanguageCB(CallbackData, prefix="lang"):
    value: str  # ru/en/he


class GenderCB(CallbackData, prefix="gender"):
    value: str  # male/female


class ActivityCB(CallbackData, prefix="activity"):
    value: str  # sedentary/light/moderate/high/very_high


class GoalCB(CallbackData, prefix="goal"):
    value: str  # loss/gain/maintain


class DeficitCB(CallbackData, prefix="deficit"):
    value: str  # "10"/"15"/"20"/"auto"


class TargetsCB(CallbackData, prefix="targets"):
    action: str  # accept / edit_kcal / edit_protein / edit_fat / edit_carbs / done


class FoodConfirmCB(CallbackData, prefix="food"):
    action: str  # ok / fix


class SettingsCB(CallbackData, prefix="settings"):
    field: str  # basic_info/goal_activity/deficit/targets/update_weight/api_key/language


class HistoryPeriodCB(CallbackData, prefix="history"):
    period: str  # today/yesterday/week


class WeightCheckinCB(CallbackData, prefix="wcheck"):
    action: str  # now / skip


class DeleteFoodCB(CallbackData, prefix="delfood"):
    entry_id: int


class ConfirmDeleteCB(CallbackData, prefix="confdel"):
    entry_id: int
    yes: str  # "y" / "n"


class ManageFoodCB(CallbackData, prefix="managefood"):
    action: str  # "open"


GENDER_VALUES = ("male", "female")
ACTIVITY_VALUES = ("sedentary", "light", "moderate", "high", "very_high")
GOAL_VALUES = ("loss", "gain", "maintain")


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=LANGUAGE_NAMES[lang], callback_data=LanguageCB(value=lang).pack())]
            for lang in LANGUAGES
        ]
    )


def gender_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, f"gender_{value}"), callback_data=GenderCB(value=value).pack())]
            for value in GENDER_VALUES
        ]
    )


def activity_level_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, f"activity_{value}"), callback_data=ActivityCB(value=value).pack())]
            for value in ACTIVITY_VALUES
        ]
    )


def goal_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, f"goal_{value}"), callback_data=GoalCB(value=value).pack())]
            for value in GOAL_VALUES
        ]
    )


def deficit_percent_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="10%", callback_data=DeficitCB(value="10").pack()),
                InlineKeyboardButton(text="15%", callback_data=DeficitCB(value="15").pack()),
                InlineKeyboardButton(text="20%", callback_data=DeficitCB(value="20").pack()),
            ],
            [InlineKeyboardButton(text=t(lang, "deficit_ai_suggest"), callback_data=DeficitCB(value="auto").pack())],
        ]
    )


def targets_confirm_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ " + _accept_label(lang), callback_data=TargetsCB(action="accept").pack())],
            [
                InlineKeyboardButton(text=t(lang, "target_kcal"), callback_data=TargetsCB(action="edit_kcal").pack()),
                InlineKeyboardButton(text=t(lang, "target_protein"), callback_data=TargetsCB(action="edit_protein").pack()),
            ],
            [
                InlineKeyboardButton(text=t(lang, "target_fat"), callback_data=TargetsCB(action="edit_fat").pack()),
                InlineKeyboardButton(text=t(lang, "target_carbs"), callback_data=TargetsCB(action="edit_carbs").pack()),
            ],
        ]
    )


def _accept_label(lang: str) -> str:
    return {"ru": "Принять", "en": "Accept", "he": "אשר"}.get(lang, "Accept")


def food_confirm_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "btn_food_ok"), callback_data=FoodConfirmCB(action="ok").pack()),
                InlineKeyboardButton(text=t(lang, "btn_food_fix"), callback_data=FoodConfirmCB(action="fix").pack()),
            ]
        ]
    )


def settings_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(lang, "settings_field_basic_info"), callback_data=SettingsCB(field="basic_info").pack())],
        [InlineKeyboardButton(text=t(lang, "settings_field_goal_activity"), callback_data=SettingsCB(field="goal_activity").pack())],
        [InlineKeyboardButton(text=t(lang, "settings_field_deficit"), callback_data=SettingsCB(field="deficit").pack())],
        [InlineKeyboardButton(text=t(lang, "settings_field_targets"), callback_data=SettingsCB(field="targets").pack())],
        [InlineKeyboardButton(text=t(lang, "settings_field_update_weight"), callback_data=SettingsCB(field="update_weight").pack())],
        [InlineKeyboardButton(text=t(lang, "settings_field_api_key"), callback_data=SettingsCB(field="api_key").pack())],
        [InlineKeyboardButton(text=t(lang, "settings_field_language"), callback_data=SettingsCB(field="language").pack())],
        [InlineKeyboardButton(text=t(lang, "settings_close"), callback_data=SettingsCB(field="close").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def history_period_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "history_period_today"), callback_data=HistoryPeriodCB(period="today").pack()),
                InlineKeyboardButton(text=t(lang, "history_period_yesterday"), callback_data=HistoryPeriodCB(period="yesterday").pack()),
            ],
            [InlineKeyboardButton(text=t(lang, "history_period_week"), callback_data=HistoryPeriodCB(period="week").pack())],
        ]
    )


def weight_checkin_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "weight_checkin_now"), callback_data=WeightCheckinCB(action="now").pack()),
                InlineKeyboardButton(text=t(lang, "weight_checkin_skip"), callback_data=WeightCheckinCB(action="skip").pack()),
            ]
        ]
    )


def food_entries_keyboard(entries, lang: str, confirming_id: int | None = None) -> InlineKeyboardMarkup:
    unit_kcal = t(lang, "unit_kcal")
    rows = []
    for row in entries:
        if row["id"] == confirming_id:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=t(lang, "confirm_yes"),
                        callback_data=ConfirmDeleteCB(entry_id=row["id"], yes="y").pack(),
                    ),
                    InlineKeyboardButton(
                        text=t(lang, "confirm_no"),
                        callback_data=ConfirmDeleteCB(entry_id=row["id"], yes="n").pack(),
                    ),
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"🗑 {row['item_name']} — {round(row['kcal'])} {unit_kcal}",
                        callback_data=DeleteFoodCB(entry_id=row["id"]).pack(),
                    )
                ]
            )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manage_food_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "manage_entries_button"), callback_data=ManageFoodCB(action="open").pack())]
        ]
    )
