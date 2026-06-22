from __future__ import annotations

import aiosqlite
from datetime import datetime

EVENT_TYPE_MAFIA = "mafia"
EVENT_TYPE_CODENAMES = "codenames"
EVENT_TYPE_MASTERCLASS = "masterclass"

SIGNUP_CONFIRMED = "confirmed"
SIGNUP_PENDING = "pending"

EVENT_OPEN = "open"
EVENT_CLOSED = "closed"

VISIBILITY_OPEN = "open"
VISIBILITY_APPROVAL = "approval"


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            # Удаляем только наследие старого бота мафии
            await db.execute("DROP TABLE IF EXISTS registrations")
            await db.execute("DROP TABLE IF EXISTS photos")
            await db.execute("DROP TABLE IF EXISTS games")
            await db.execute("DROP TABLE IF EXISTS dynamic_admins")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    max_players INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    visibility TEXT NOT NULL DEFAULT 'open',
                    creator_id INTEGER NOT NULL,
                    creator_name TEXT NOT NULL,
                    thread_id INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS signups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'confirmed',
                    signed_at TEXT NOT NULL,
                    UNIQUE(event_id, user_id),
                    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS known_users (
                    user_id INTEGER PRIMARY KEY NOT NULL,
                    username TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def event_datetime(event: dict) -> datetime:
        return datetime.strptime(
            f"{event['event_date']} {event['event_time']}",
            "%Y-%m-%d %H:%M",
        )

    async def create_event(
        self,
        *,
        chat_id: int,
        event_type: str,
        title: str,
        event_date: str,
        event_time: str,
        max_players: int,
        visibility: str,
        creator_id: int,
        creator_name: str,
        thread_id: int | None = None,
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                INSERT INTO events (
                    chat_id, event_type, title, event_date, event_time,
                    max_players, status, visibility, creator_id, creator_name,
                    thread_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    event_type,
                    title,
                    event_date,
                    event_time,
                    max_players,
                    visibility,
                    creator_id,
                    creator_name,
                    thread_id,
                    self._now_iso(),
                ),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def set_thread_id(self, event_id: int, thread_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE events SET thread_id = ? WHERE id = ?",
                (thread_id, event_id),
            )
            await db.commit()

    async def get_event(self, event_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def delete_event(self, event_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("DELETE FROM events WHERE id = ?", (event_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def set_event_status(self, event_id: int, status: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE events SET status = ? WHERE id = ?",
                (status, event_id),
            )
            await db.commit()

    async def get_upcoming_events(
        self,
        *,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        now = datetime.now()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            if event_type:
                cursor = await db.execute(
                    """
                    SELECT * FROM events
                    WHERE event_type = ?
                    ORDER BY event_date ASC, event_time ASC
                    """,
                    (event_type,),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT * FROM events
                    ORDER BY event_date ASC, event_time ASC
                    """
                )
            rows = await cursor.fetchall()
        upcoming = [dict(r) for r in rows if self.event_datetime(dict(r)) >= now]
        if limit is not None:
            return upcoming[:limit]
        return upcoming

    async def count_upcoming_by_type(self, event_type: str) -> int:
        return len(await self.get_upcoming_events(event_type=event_type))

    async def get_signups(self, event_id: int) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM signups
                WHERE event_id = ?
                ORDER BY signed_at ASC
                """,
                (event_id,),
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def get_confirmed_signups(self, event_id: int) -> list[dict]:
        signups = await self.get_signups(event_id)
        return [s for s in signups if s["status"] == SIGNUP_CONFIRMED]

    async def confirmed_count(self, event_id: int) -> int:
        return len(await self.get_confirmed_signups(event_id))

    async def get_signup(self, event_id: int, user_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM signups
                WHERE event_id = ? AND user_id = ?
                """,
                (event_id, user_id),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def add_signup(
        self,
        *,
        event_id: int,
        user_id: int,
        display_name: str,
        status: str = SIGNUP_CONFIRMED,
    ) -> bool:
        async with aiosqlite.connect(self.path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO signups (event_id, user_id, display_name, status, signed_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (event_id, user_id, display_name, status, self._now_iso()),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def remove_signup(self, event_id: int, user_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "DELETE FROM signups WHERE event_id = ? AND user_id = ?",
                (event_id, user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def set_signup_status(self, event_id: int, user_id: int, status: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                UPDATE signups SET status = ?
                WHERE event_id = ? AND user_id = ?
                """,
                (status, event_id, user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def touch_user(self, *, user_id: int, username: str | None) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO known_users (user_id, username, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, username),
            )
            await db.commit()
