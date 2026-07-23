from aiogram.fsm.state import State, StatesGroup


class WeightCheckinForm(StatesGroup):
    waiting_weight = State()
