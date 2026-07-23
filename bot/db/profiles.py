from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite


@dataclass
class Profile:
    user_id: int
    weight: float | None
    height: float | None
    age: int | None
    gender: str | None
    activity_level: str | None
    goal: str | None
    deficit_percent: int | None
    target_kcal: int | None
    target_protein: int | None
    target_fat: int | None
    target_carbs: int | None

    @property
    def is_complete(self) -> bool:
        return all(
            v is not None
            for v in (
                self.weight,
                self.height,
                self.age,
                self.gender,
                self.activity_level,
                self.goal,
                self.target_kcal,
                self.target_protein,
                self.target_fat,
                self.target_carbs,
            )
        )


def _row_to_profile(row: aiosqlite.Row) -> Profile:
    return Profile(
        user_id=row["user_id"],
        weight=row["weight"],
        height=row["height"],
        age=row["age"],
        gender=row["gender"],
        activity_level=row["activity_level"],
        goal=row["goal"],
        deficit_percent=row["deficit_percent"],
        target_kcal=row["target_kcal"],
        target_protein=row["target_protein"],
        target_fat=row["target_fat"],
        target_carbs=row["target_carbs"],
    )


async def get_profile(db: aiosqlite.Connection, user_id: int) -> Profile | None:
    cursor = await db.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    return _row_to_profile(row) if row else None


async def get_all_complete_profiles(db: aiosqlite.Connection) -> list[Profile]:
    cursor = await db.execute("SELECT * FROM profiles")
    rows = await cursor.fetchall()
    return [p for row in rows if (p := _row_to_profile(row)).is_complete]


async def upsert_profile_field(
    db: aiosqlite.Connection, user_id: int, field: str, value
) -> None:
    allowed_fields = {
        "weight",
        "height",
        "age",
        "gender",
        "activity_level",
        "goal",
        "deficit_percent",
        "target_kcal",
        "target_protein",
        "target_fat",
        "target_carbs",
    }
    if field not in allowed_fields:
        raise ValueError(f"Unknown profile field: {field}")

    await db.execute(
        "INSERT INTO profiles (user_id, updated_at) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO NOTHING",
        (user_id, datetime.now(timezone.utc).isoformat()),
    )
    await db.execute(
        f"UPDATE profiles SET {field} = ?, updated_at = ? WHERE user_id = ?",
        (value, datetime.now(timezone.utc).isoformat(), user_id),
    )
    await db.commit()


async def save_targets(
    db: aiosqlite.Connection,
    user_id: int,
    *,
    kcal: int,
    protein: int,
    fat: int,
    carbs: int,
) -> None:
    await db.execute(
        "INSERT INTO profiles (user_id, target_kcal, target_protein, target_fat, target_carbs, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "target_kcal=excluded.target_kcal, target_protein=excluded.target_protein, "
        "target_fat=excluded.target_fat, target_carbs=excluded.target_carbs, updated_at=excluded.updated_at",
        (user_id, kcal, protein, fat, carbs, datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()
