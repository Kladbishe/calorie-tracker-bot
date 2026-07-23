import os
from importlib import resources

import aiosqlite


async def init_db(database_path: str) -> aiosqlite.Connection:
    db_dir = os.path.dirname(database_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = await aiosqlite.connect(database_path)
    conn.row_factory = aiosqlite.Row

    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA foreign_keys=ON;")

    schema_sql = resources.files("bot.db").joinpath("schema.sql").read_text(encoding="utf-8")
    await conn.executescript(schema_sql)
    await conn.commit()

    await _migrate(conn)

    return conn


async def _migrate(conn: aiosqlite.Connection) -> None:
    """Adds columns introduced after the initial schema to already-existing DB files.
    CREATE TABLE IF NOT EXISTS above only handles brand-new tables, not new columns
    on tables that already exist on disk."""
    cursor = await conn.execute("PRAGMA table_info(users)")
    columns = {row["name"] for row in await cursor.fetchall()}
    if "language" not in columns:
        await conn.execute("ALTER TABLE users ADD COLUMN language TEXT")
        await conn.commit()
    if "last_seen_at" not in columns:
        await conn.execute("ALTER TABLE users ADD COLUMN last_seen_at TEXT")
        await conn.commit()
