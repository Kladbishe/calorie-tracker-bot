from datetime import datetime, timezone

import aiosqlite

from bot.texts import DEFAULT_LANGUAGE


async def get_user(db: aiosqlite.Connection, user_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return await cursor.fetchone()


async def ensure_user(db: aiosqlite.Connection, user_id: int) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO users (id, created_at) VALUES (?, ?)",
        (user_id, datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()


async def set_api_key(db: aiosqlite.Connection, user_id: int, encrypted_key: bytes) -> None:
    await db.execute(
        "UPDATE users SET openai_api_key_encrypted = ? WHERE id = ?",
        (encrypted_key, user_id),
    )
    await db.commit()


async def get_encrypted_api_key(db: aiosqlite.Connection, user_id: int) -> bytes | None:
    cursor = await db.execute(
        "SELECT openai_api_key_encrypted FROM users WHERE id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    return row["openai_api_key_encrypted"] if row else None


async def get_language(db: aiosqlite.Connection, user_id: int) -> str | None:
    cursor = await db.execute("SELECT language FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    return row["language"] if row else None


async def set_language(db: aiosqlite.Connection, user_id: int, language: str) -> None:
    await db.execute("UPDATE users SET language = ? WHERE id = ?", (language, user_id))
    await db.commit()


async def get_effective_language(db: aiosqlite.Connection, user_id: int) -> str:
    return await get_language(db, user_id) or DEFAULT_LANGUAGE


async def touch_last_seen(db: aiosqlite.Connection, user_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO users (id, created_at, last_seen_at) VALUES (?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_seen_at = excluded.last_seen_at",
        (user_id, now, now),
    )
    await db.commit()
