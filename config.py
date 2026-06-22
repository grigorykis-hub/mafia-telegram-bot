from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    db_path: str
    group_chat_id: int | None
    group_thread_enabled: bool


def _parse_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        ids.add(int(part))
    return ids


def _parse_bool(raw: str, *, default: bool = False) -> bool:
    s = (raw or "").strip().lower()
    if not s:
        return default
    return s in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("BOT_TOKEN не задан в .env")
    if token == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise ValueError("Замените BOT_TOKEN в .env на реальный токен от BotFather")

    admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
    if not admin_ids_raw:
        raise ValueError("ADMIN_IDS не задан в .env")

    group_chat_raw = os.getenv("GROUP_CHAT_ID", "").strip()
    group_chat_id: int | None = None
    if group_chat_raw:
        group_chat_id = int(group_chat_raw)

    db_path = os.getenv("DB_PATH", "opc_bot.db").strip()
    return Settings(
        bot_token=token,
        admin_ids=_parse_admin_ids(admin_ids_raw),
        db_path=db_path,
        group_chat_id=group_chat_id,
        group_thread_enabled=_parse_bool(
            os.getenv("GROUP_THREAD_ENABLED", "true"),
            default=True,
        ),
    )
