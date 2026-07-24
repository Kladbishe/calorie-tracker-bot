from aiogram.fsm.state import State, StatesGroup


class FoodTextForm(StatesGroup):
    waiting_confirm = State()


class FoodPhotoForm(StatesGroup):
    waiting_grams = State()
    waiting_confirm = State()


class FoodEditForm(StatesGroup):
    waiting_confirm = State()
    waiting_field_value = State()
