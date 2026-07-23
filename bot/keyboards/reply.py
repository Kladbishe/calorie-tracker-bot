from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot.texts import LANGUAGES, t


def main_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_remaining"))],
            [KeyboardButton(text=t(lang, "btn_history"))],
            [KeyboardButton(text=t(lang, "btn_settings"))],
        ],
        resize_keyboard=True,
    )


def is_menu_button(message_text: str | None, key: str) -> bool:
    """Matches a reply-keyboard button regardless of which language it was rendered in —
    handlers don't know the user's language before this filter runs."""
    if message_text is None:
        return False
    return message_text in {t(lang, key) for lang in LANGUAGES}
