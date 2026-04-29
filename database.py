from __future__ import annotations

import aiosqlite


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    game_date TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    capacity INTEGER NOT NULL CHECK(capacity > 0),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    username TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(game_id, user_id),
                    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS dynamic_admins (
                    username_lower TEXT PRIMARY KEY NOT NULL,
                    added_by_user_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

    async def add_game(
        self,
        *,
        title: str,
        game_date_iso: str,
        direction: str,
        capacity: int,
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                INSERT INTO games (title, game_date, direction, capacity)
                VALUES (?, ?, ?, ?)
                """,
                (title, game_date_iso, direction, capacity),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_upcoming_games(self, now_iso: str) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM games
                WHERE game_date >= ?
                ORDER BY game_date ASC
                """,
                (now_iso,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_past_games(self, now_iso: str) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM games
                WHERE game_date < ?
                ORDER BY game_date DESC
                """,
                (now_iso,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_game(self, game_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM games WHERE id = ?", (game_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_registrations(self, game_id: int) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT user_id, display_name, username
                FROM registrations
                WHERE game_id = ?
                ORDER BY created_at ASC
                """,
                (game_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_registered_user_ids(self, game_id: int) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT user_id FROM registrations
                WHERE game_id = ?
                ORDER BY created_at ASC
                """,
                (game_id,),
            )
            rows = await cursor.fetchall()
            return [int(row[0]) for row in rows]

    async def get_registration_count(self, game_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM registrations WHERE game_id = ?", (game_id,)
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    async def register_user(
        self,
        *,
        game_id: int,
        user_id: int,
        display_name: str,
        username: str | None,
    ) -> tuple[bool, str]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            game_cursor = await db.execute("SELECT capacity FROM games WHERE id = ?", (game_id,))
            game = await game_cursor.fetchone()
            if not game:
                return False, "Игра не найдена."

            count_cursor = await db.execute(
                "SELECT COUNT(*) FROM registrations WHERE game_id = ?", (game_id,)
            )
            count_row = await count_cursor.fetchone()
            current_count = int(count_row[0]) if count_row else 0
            if current_count >= int(game["capacity"]):
                return False, "Свободных мест уже нет."

            try:
                await db.execute(
                    """
                    INSERT INTO registrations (game_id, user_id, display_name, username)
                    VALUES (?, ?, ?, ?)
                    """,
                    (game_id, user_id, display_name, username),
                )
            except aiosqlite.IntegrityError:
                return False, "Вы уже записаны на эту игру."

            await db.commit()
            return True, "Вы успешно записались на игру."

    async def unregister_user(self, *, game_id: int, user_id: int) -> tuple[bool, str]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "DELETE FROM registrations WHERE game_id = ? AND user_id = ?",
                (game_id, user_id),
            )
            await db.commit()
            if cursor.rowcount == 0:
                return False, "Вы не были записаны на эту игру."
            return True, "Ваша запись отменена."

    async def add_photo(self, *, game_id: int, file_id: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO photos (game_id, file_id) VALUES (?, ?)",
                (game_id, file_id),
            )
            await db.commit()

    async def get_photos(self, game_id: int) -> list[str]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT file_id FROM photos
                WHERE game_id = ?
                ORDER BY created_at ASC
                """,
                (game_id,),
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

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

    async def get_known_user_ids(self) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT user_id FROM known_users ORDER BY user_id ASC")
            rows = await cursor.fetchall()
            return [int(row[0]) for row in rows]

    async def is_dynamic_admin(self, username_lower: str) -> bool:
        if not username_lower:
            return False
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM dynamic_admins WHERE username_lower = ? LIMIT 1",
                (username_lower,),
            )
            row = await cursor.fetchone()
            return row is not None

    async def add_dynamic_admin(
        self,
        *,
        username_lower: str,
        added_by_user_id: int,
    ) -> tuple[bool, str]:
        async with aiosqlite.connect(self.path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO dynamic_admins (username_lower, added_by_user_id)
                    VALUES (?, ?)
                    """,
                    (username_lower, added_by_user_id),
                )
            except aiosqlite.IntegrityError:
                return False, "Этот логин уже в списке администраторов."
            await db.commit()
            return True, f"Админские права для @{username_lower} добавлены."
