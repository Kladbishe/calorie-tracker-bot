from aiogram.fsm.state import State, StatesGroup


class AdviceForm(StatesGroup):
    waiting_food = State()
