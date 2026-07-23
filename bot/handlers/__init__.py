from aiogram import Router

from bot.handlers import (
    admin,
    common,
    food_photo,
    food_text,
    history,
    profile_steps,
    remaining,
    settings,
    start,
    weight_checkin,
)


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_router(admin.router)
    root.include_router(start.router)
    root.include_router(profile_steps.router)
    root.include_router(settings.router)
    root.include_router(weight_checkin.router)
    root.include_router(remaining.router)
    root.include_router(history.router)
    root.include_router(food_photo.router)
    root.include_router(food_text.router)
    root.include_router(common.router)
    return root
