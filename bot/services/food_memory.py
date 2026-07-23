import aiosqlite

from bot.db import known_foods as known_foods_repo
from bot.services.openai_service import FoodItem


async def get_known_items_hint(db: aiosqlite.Connection, user_id: int, text: str) -> list[dict]:
    rows = await known_foods_repo.find_matches(db, user_id, text)
    return [
        {
            "display_name": row["display_name"],
            "kcal_per_100g": row["kcal_per_100g"],
            "protein_per_100g": row["protein_per_100g"],
            "fat_per_100g": row["fat_per_100g"],
            "carbs_per_100g": row["carbs_per_100g"],
        }
        for row in rows
    ]


async def remember_items(db: aiosqlite.Connection, user_id: int, items: list[FoodItem]) -> None:
    for item in items:
        if not item.grams or item.grams <= 0:
            continue
        scale = 100 / item.grams
        await known_foods_repo.upsert_known_food(
            db,
            user_id,
            item.name,
            kcal_per_100g=round(item.kcal * scale, 1),
            protein_per_100g=round(item.protein * scale, 1),
            fat_per_100g=round(item.fat * scale, 1),
            carbs_per_100g=round(item.carbs * scale, 1),
        )
