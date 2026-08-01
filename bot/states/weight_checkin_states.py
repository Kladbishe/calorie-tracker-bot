from aiogram.fsm.state import State, StatesGroup


class WeightCheckinForm(StatesGroup):
    waiting_weight = State()
    waiting_adjust_confirm = State()
    waiting_adjust_field = State()
