from aiogram.fsm.state import State, StatesGroup


class ProfileForm(StatesGroup):
    waiting_language = State()
    waiting_api_key = State()
    waiting_weight = State()
    waiting_height = State()
    waiting_age = State()
    waiting_gender = State()
    waiting_activity = State()
    waiting_goal = State()
    waiting_deficit = State()
    waiting_ai_confirm = State()
    waiting_target_field_value = State()  # single-field manual override during confirm/settings
