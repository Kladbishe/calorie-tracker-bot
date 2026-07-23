import json

import aiosqlite
from aiogram.fsm.storage.base import BaseStorage, StorageKey


def _key_str(key: StorageKey) -> str:
    return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.thread_id}:{key.business_connection_id}:{key.destiny}"


class SQLiteStorage(BaseStorage):
    """Persists FSM state/data in the same SQLite DB as everything else, so a bot restart
    never strands a user mid-flow (onboarding, settings edit, food confirm, ...)."""

    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def set_state(self, key: StorageKey, state=None) -> None:
        state_str = state.state if hasattr(state, "state") else state
        await self._db.execute(
            "INSERT INTO fsm_storage (key, state) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET state = excluded.state",
            (_key_str(key), state_str),
        )
        await self._db.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        cursor = await self._db.execute("SELECT state FROM fsm_storage WHERE key = ?", (_key_str(key),))
        row = await cursor.fetchone()
        return row["state"] if row else None

    async def set_data(self, key: StorageKey, data: dict) -> None:
        await self._db.execute(
            "INSERT INTO fsm_storage (key, data) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET data = excluded.data",
            (_key_str(key), json.dumps(data)),
        )
        await self._db.commit()

    async def get_data(self, key: StorageKey) -> dict:
        cursor = await self._db.execute("SELECT data FROM fsm_storage WHERE key = ?", (_key_str(key),))
        row = await cursor.fetchone()
        return json.loads(row["data"]) if row and row["data"] else {}

    async def close(self) -> None:
        pass  # the db connection's lifecycle is owned by main.py, not this storage
