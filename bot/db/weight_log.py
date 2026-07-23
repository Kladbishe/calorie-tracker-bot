import aiosqlite


async def insert_weight(db: aiosqlite.Connection, user_id: int, date: str, weight: float) -> None:
    await db.execute(
        "INSERT INTO weight_log (user_id, date, weight) VALUES (?, ?, ?)",
        (user_id, date, weight),
    )
    await db.commit()


async def get_weight_history(db: aiosqlite.Connection, user_id: int, limit: int = 12) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM weight_log WHERE user_id = ? ORDER BY date DESC LIMIT ?",
        (user_id, limit),
    )
    return await cursor.fetchall()


async def get_weight_for_range(
    db: aiosqlite.Connection, user_id: int, date_from: str, date_to: str
) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM weight_log WHERE user_id = ? AND date BETWEEN ? AND ? ORDER BY date",
        (user_id, date_from, date_to),
    )
    return await cursor.fetchall()


async def upsert_checkin_status(db: aiosqlite.Connection, user_id: int, week_start_date: str, status: str) -> None:
    await db.execute(
        "INSERT INTO weight_checkin_status (user_id, week_start_date, status) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, week_start_date) DO UPDATE SET status=excluded.status",
        (user_id, week_start_date, status),
    )
    await db.commit()


async def mark_reminder_sent(db: aiosqlite.Connection, user_id: int, week_start_date: str, sent_at: str) -> None:
    await db.execute(
        "UPDATE weight_checkin_status SET last_reminder_at = ? WHERE user_id = ? AND week_start_date = ?",
        (sent_at, user_id, week_start_date),
    )
    await db.commit()


async def get_pending_checkins(db: aiosqlite.Connection, week_start_date: str) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM weight_checkin_status WHERE week_start_date = ? AND status IN ('pending', 'skipped')",
        (week_start_date,),
    )
    return await cursor.fetchall()
