"""Тексты и подписи OPC Events."""

from __future__ import annotations

BOT_TITLE = "OPC · Иваново · Ленина"
LOCATION_LINE = "Иваново · ул. Ленина"
BRAND = "OPC"

MENU_BUILD_TAG = "opc-ui-2026-06"

VISIBILITY_OPEN_TEXT = "🔓 Открытая — может присоединиться любой"
VISIBILITY_APPROVAL_TEXT = "🔒 По согласованию с организатором"

CB_MENU_GAMES = "menu:games"
CB_MENU_MASTERCLASS = "menu:masterclass"
CB_MENU_CALENDAR = "menu:calendar"
CB_NAV_MAIN = "nav:main"

CB_GAMES_MAFIA = "games:mafia"
CB_GAMES_CODENAMES = "games:codenames"

CB_CREATE_PREFIX = "create:"
CB_EVENT_VIEW_PREFIX = "event:view:"
CB_EVENT_CHAT_PREFIX = "event:chat:"
CB_EVENT_CLOSE_PREFIX = "event:close:"
CB_EVENT_REOPEN_PREFIX = "event:reopen:"
CB_EVENT_DELETE_PREFIX = "event:delete:"

CB_SLOT_JOIN_PREFIX = "slot:join:"
CB_SLOT_LEAVE_PREFIX = "slot:leave:"

CB_APPROVE_PREFIX = "approve:"
CB_REJECT_PREFIX = "reject:"

CB_VIS_OPEN = "vis:open"
CB_VIS_APPROVAL = "vis:approval"

CB_OPEN_CARD_PREFIX = "open_card:"


def event_type_icon(event_type: str) -> str:
    return {
        "mafia": "🌙",
        "codenames": "🕵",
        "masterclass": "🎨",
    }.get(event_type, "🎪")


def event_type_label(event_type: str) -> str:
    return {
        "mafia": "Мафия",
        "codenames": "Коднеймс",
        "masterclass": "Мастер-класс",
    }.get(event_type, "Мероприятие")


def visibility_icon(visibility: str) -> str:
    return "🔓" if visibility == "open" else "🔒"


def format_date(date_str: str) -> str:
    y, m, d = date_str.split("-")
    return f"{d}.{m}"


def event_type_short(event_type: str) -> str:
    return {
        "mafia": "Мафия",
        "codenames": "Коднеймс",
        "masterclass": "МК",
    }.get(event_type, "Событие")


def format_event_card_html(
    *,
    event_type: str,
    title: str,
    event_date: str,
    event_time: str,
    filled: int,
    max_players: int,
) -> str:
    icon = event_type_icon(event_type)
    label = event_type_short(event_type)
    return (
        f"<b>{html_escape(title)}</b>\n"
        f"<i>{icon} {label} · {format_date(event_date)} · {event_time}</i>  "
        f"<code>{filled}/{max_players}</code>"
    )


def html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_main_menu_html(event_blocks: list[str]) -> str:
    lines = [
        f"<b>{BRAND}</b>",
        LOCATION_LINE,
        "<i>Твоя кофейня — твои игры</i>",
        "",
        "<b>БЛИЖАЙШИЕ МЕРОПРИЯТИЯ</b>",
    ]
    if event_blocks:
        lines.extend(event_blocks)
    else:
        lines.append("<i>Пока ничего не запланировано</i>")
    lines.extend(["", "<b>РАЗДЕЛЫ</b>", f"<i>{MENU_BUILD_TAG}</i>"])
    return "\n".join(lines)


def event_button_label(
    *,
    event_type: str,
    title: str,
    event_date: str,
    event_time: str,
    filled: int,
    max_players: int,
) -> str:
    icon = event_type_icon(event_type)
    short_title = title if len(title) <= 22 else title[:21] + "…"
    return f"{icon} {short_title} · {format_date(event_date)} · {filled}/{max_players}"


def format_event_line(
    *,
    event_type: str,
    title: str,
    event_date: str,
    event_time: str,
    filled: int,
    max_players: int,
    visibility: str | None = None,
) -> str:
    icon = event_type_icon(event_type)
    vis = f"{visibility_icon(visibility)} " if visibility else ""
    return (
        f"{vis}{icon} {title} · {format_date(event_date)} · "
        f"{event_time} · {filled}/{max_players}"
    )
