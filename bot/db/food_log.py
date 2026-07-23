from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite


@dataclass
class Totals:
    kcal: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbs: float = 0.0


@dataclass
class DailyTotals(Totals):
    date: str = ""


async def insert_food_entries(
    db: aiosqlite.Connection,
    user_id: int,
    date: str,
    meal_type: str,
    items: list,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.executemany(
        "INSERT INTO food_log (user_id, date, meal_type, item_name, grams, kcal, protein, fat, carbs, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (user_id, date, meal_type, item.name, item.grams, item.kcal, item.protein, item.fat, item.carbs, now)
            for item in items
        ],
    )
    await db.commit()


async def get_totals_for_date(db: aiosqlite.Connection, user_id: int, date: str) -> Totals:
    cursor = await db.execute(
        "SELECT COALESCE(SUM(kcal),0) kcal, COALESCE(SUM(protein),0) protein, "
        "COALESCE(SUM(fat),0) fat, COALESCE(SUM(carbs),0) carbs "
        "FROM food_log WHERE user_id = ? AND date = ?",
        (user_id, date),
    )
    row = await cursor.fetchone()
    return Totals(kcal=row["kcal"], protein=row["protein"], fat=row["fat"], carbs=row["carbs"])


async def get_totals_for_range(
    db: aiosqlite.Connection, user_id: int, date_from: str, date_to: str
) -> list[DailyTotals]:
    cursor = await db.execute(
        "SELECT date, COALESCE(SUM(kcal),0) kcal, COALESCE(SUM(protein),0) protein, "
        "COALESCE(SUM(fat),0) fat, COALESCE(SUM(carbs),0) carbs "
        "FROM food_log WHERE user_id = ? AND date BETWEEN ? AND ? "
        "GROUP BY date ORDER BY date DESC",
        (user_id, date_from, date_to),
    )
    rows = await cursor.fetchall()
    return [
        DailyTotals(date=row["date"], kcal=row["kcal"], protein=row["protein"], fat=row["fat"], carbs=row["carbs"])
        for row in rows
    ]


async def get_entries_for_date(db: aiosqlite.Connection, user_id: int, date: str) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM food_log WHERE user_id = ? AND date = ? ORDER BY created_at",
        (user_id, date),
    )
    return await cursor.fetchall()


async def delete_entry(db: aiosqlite.Connection, entry_id: int, user_id: int) -> None:
    await db.execute("DELETE FROM food_log WHERE id = ? AND user_id = ?", (entry_id, user_id))
    await db.commit()
