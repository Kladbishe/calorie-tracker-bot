import re
from datetime import datetime, timezone

import aiosqlite


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


async def upsert_known_food(
    db: aiosqlite.Connection,
    user_id: int,
    display_name: str,
    *,
    kcal_per_100g: float,
    protein_per_100g: float,
    fat_per_100g: float,
    carbs_per_100g: float,
) -> None:
    name_normalized = normalize_name(display_name)
    if not name_normalized:
        return

    await db.execute(
        "INSERT INTO known_foods "
        "(user_id, name_normalized, display_name, kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, name_normalized) DO UPDATE SET "
        "display_name=excluded.display_name, kcal_per_100g=excluded.kcal_per_100g, "
        "protein_per_100g=excluded.protein_per_100g, fat_per_100g=excluded.fat_per_100g, "
        "carbs_per_100g=excluded.carbs_per_100g, updated_at=excluded.updated_at",
        (
            user_id,
            name_normalized,
            display_name,
            kcal_per_100g,
            protein_per_100g,
            fat_per_100g,
            carbs_per_100g,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    await db.commit()


async def get_all_for_user(db: aiosqlite.Connection, user_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute("SELECT * FROM known_foods WHERE user_id = ?", (user_id,))
    return await cursor.fetchall()


async def find_matches(db: aiosqlite.Connection, user_id: int, text: str, limit: int = 20) -> list[aiosqlite.Row]:
    """Returns known foods whose name appears as a substring of the (lowercased) message text —
    a cheap relevance filter so only foods actually mentioned are sent as hints to the model."""
    text_lower = text.lower()
    all_known = await get_all_for_user(db, user_id)
    matches = [row for row in all_known if row["name_normalized"] in text_lower]
    return matches[:limit]
