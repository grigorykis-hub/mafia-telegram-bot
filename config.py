from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    admin_usernames: frozenset[str]
    db_path: str


def _parse_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        ids.add(int(part))
    return ids


def _parse_admin_usernames(raw: str) -> frozenset[str]:
    names: set[str] = set()
    for part in raw.split(","):
        part = part.strip().lower().lstrip("@")
        if part:
            names.add(part)
    return frozenset(names)


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

    admin_usernames = _parse_admin_usernames(os.getenv("ADMIN_USERNAMES", "").strip())

    db_path = os.getenv("DB_PATH", "mafia_bot.db").strip()
    return Settings(
        bot_token=token,
        admin_ids=_parse_admin_ids(admin_ids_raw),
        admin_usernames=admin_usernames,
        db_path=db_path,
    )
