from __future__ import annotations

import asyncio
import html
import re
from datetime import date, datetime
from typing import Any

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    ReplyKeyboardRemove,
    TelegramObject,
    User,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Settings, load_settings
from database import (
    EVENT_CLOSED,
    EVENT_OPEN,
    EVENT_TYPE_CODENAMES,
    EVENT_TYPE_MAFIA,
    EVENT_TYPE_MASTERCLASS,
    SIGNUP_CONFIRMED,
    SIGNUP_PENDING,
    VISIBILITY_APPROVAL,
    VISIBILITY_OPEN,
    Database,
)
from theme import (
    BOT_TITLE,
    BRAND,
    CB_APPROVE_PREFIX,
    CB_CREATE_PREFIX,
    CB_EVENT_CHAT_PREFIX,
    CB_EVENT_CLOSE_PREFIX,
    CB_EVENT_DELETE_PREFIX,
    CB_EVENT_REOPEN_PREFIX,
    CB_EVENT_VIEW_PREFIX,
    CB_GAMES_CODENAMES,
    CB_GAMES_MAFIA,
    CB_MENU_CALENDAR,
    CB_MENU_GAMES,
    CB_MENU_MASTERCLASS,
    CB_NAV_MAIN,
    CB_OPEN_CARD_PREFIX,
    CB_REJECT_PREFIX,
    CB_SLOT_JOIN_PREFIX,
    CB_SLOT_LEAVE_PREFIX,
    CB_VIS_APPROVAL,
    CB_VIS_OPEN,
    MENU_BUILD_TAG,
    VISIBILITY_APPROVAL_TEXT,
    VISIBILITY_OPEN_TEXT,
    build_main_menu_html,
    event_button_label,
    event_type_icon,
    event_type_label,
    format_date,
    format_event_card_html,
    format_event_line,
    visibility_icon,
)
from web_server import start_webapp_server

# Старые reply-кнопки прошлой версии бота — снимаем клавиатуру и ведём в новое меню.
LEGACY_REPLY_BUTTONS = {
    "🎴 Набор на стол",
    "🌑 Архив партий",
    "📅 Календарь",
    "🎩 Кабинет Дона",
    "Предстоящие игры",
    "Прошедшие игры",
    "Календарь игр",
    "Мафия",
    "Мастер-классы",
    "Назад в меню",
    "🏙 На площадь",
}

ROUTER = Router()
DB: Database
SETTINGS: Settings

DATE_INPUT_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?$")
TIME_INPUT_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


class CreateEvent(StatesGroup):
    title = State()
    date = State()
    time = State()
    max_players = State()
    visibility = State()


class TrackUsersMiddleware(BaseMiddleware):
    async def __call__(self, handler: Any, event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        if user and not user.is_bot:
            await DB.touch_user(user_id=user.id, username=user.username)
        return await handler(event, data)


def can_manage(user_id: int, event: dict) -> bool:
    return user_id == int(event["creator_id"]) or user_id in SETTINGS.admin_ids


def thread_link(chat_id: int, thread_id: int) -> str:
    cid = str(chat_id)
    if cid.startswith("-100"):
        cid = cid[4:]
    else:
        cid = str(abs(chat_id))
    return f"https://t.me/c/{cid}/{thread_id}"


def display_name(user: User) -> str:
    return (user.full_name or "").strip() or f"user_{user.id}"


def nav_row(back_cb: str) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text="‹ Назад", callback_data=back_cb),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data=CB_NAV_MAIN),
    ]


async def edit_message(query: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    try:
        await query.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await query.message.answer(text, reply_markup=markup)


async def strip_old_reply_keyboard(message: Message) -> None:
    """Убирает залипшую нижнюю клавиатуру старого бота."""
    try:
        await message.answer(" ", reply_markup=ReplyKeyboardRemove())
    except TelegramBadRequest:
        pass


async def build_main_menu_text() -> str:
    events = await DB.get_upcoming_events(limit=3)
    blocks: list[str] = []
    for ev in events:
        filled = await DB.confirmed_count(int(ev["id"]))
        blocks.append(
            format_event_card_html(
                event_type=ev["event_type"],
                title=ev["title"],
                event_date=ev["event_date"],
                event_time=ev["event_time"],
                filled=filled,
                max_players=int(ev["max_players"]),
            )
        )
    return build_main_menu_html(blocks)


async def build_main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    events = await DB.get_upcoming_events(limit=3)
    for ev in events:
        filled = await DB.confirmed_count(int(ev["id"]))
        kb.button(
            text=event_button_label(
                event_type=ev["event_type"],
                title=ev["title"],
                event_date=ev["event_date"],
                event_time=ev["event_time"],
                filled=filled,
                max_players=int(ev["max_players"]),
            ),
            callback_data=f"{CB_EVENT_VIEW_PREFIX}{ev['id']}",
        )
    if SETTINGS.webapp_public_url:
        kb.button(
            text="📱 Открыть приложение OPC",
            web_app=WebAppInfo(url=f"{SETTINGS.webapp_public_url}/"),
        )
    kb.button(text="🎮 Игры", callback_data=CB_MENU_GAMES)
    kb.button(text="🎨 Мастер-классы", callback_data=CB_MENU_MASTERCLASS)
    kb.button(text="📅 Календарь всех мероприятий", callback_data=CB_MENU_CALENDAR)
    kb.adjust(1)
    return kb.as_markup()


async def render_main_menu(query: CallbackQuery) -> None:
    await edit_message(query, await build_main_menu_text(), await build_main_menu_kb())


async def send_main_menu(message: Message) -> None:
    await strip_old_reply_keyboard(message)
    await message.answer(
        await build_main_menu_text(),
        reply_markup=await build_main_menu_kb(),
    )


async def render_games_menu(query: CallbackQuery) -> None:
    mafia_n = await DB.count_upcoming_by_type(EVENT_TYPE_MAFIA)
    codenames_n = await DB.count_upcoming_by_type(EVENT_TYPE_CODENAMES)
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🌙 Мафия · {mafia_n} предстоящих", callback_data=CB_GAMES_MAFIA)
    kb.button(text=f"🕵 Коднеймс · {codenames_n} предстоящих", callback_data=CB_GAMES_CODENAMES)
    kb.row(*nav_row(CB_NAV_MAIN))
    await edit_message(query, "🎮 <b>Игры</b>\nВыбери игру:", kb.as_markup())


async def render_event_list(
    query: CallbackQuery,
    event_type: str,
    back_cb: str,
) -> None:
    events = await DB.get_upcoming_events(event_type=event_type)
    icon = event_type_icon(event_type)
    label = event_type_label(event_type)
    kb = InlineKeyboardBuilder()
    for ev in events:
        filled = await DB.confirmed_count(int(ev["id"]))
        vis = visibility_icon(ev["visibility"])
        btn = (
            f"{vis} {ev['title']} · {format_date(ev['event_date'])} · "
            f"{ev['event_time']} · {filled}/{ev['max_players']}"
        )
        kb.button(text=btn, callback_data=f"{CB_EVENT_VIEW_PREFIX}{ev['id']}")
    kb.button(text="➕ Создать мероприятие", callback_data=f"{CB_CREATE_PREFIX}{event_type}")
    kb.row(*nav_row(back_cb))
    kb.adjust(1)
    await edit_message(
        query,
        f"{icon} <b>{label}</b>\nБлижайшие мероприятия:",
        kb.as_markup(),
    )


def visibility_text(visibility: str) -> str:
    return VISIBILITY_OPEN_TEXT if visibility == VISIBILITY_OPEN else VISIBILITY_APPROVAL_TEXT


async def build_event_card(event_id: int, viewer_id: int) -> tuple[str, InlineKeyboardMarkup]:
    event = await DB.get_event(event_id)
    if not event:
        kb = InlineKeyboardBuilder()
        kb.row(*nav_row(CB_NAV_MAIN))
        return "Мероприятие не найдено.", kb.as_markup()

    signups = await DB.get_confirmed_signups(event_id)
    filled = len(signups)
    max_p = int(event["max_players"])
    icon = event_type_icon(event["event_type"])

    text = (
        f"<b>{icon} {html.escape(event['title'])}</b>\n"
        f"📅 {format_date(event['event_date'])} · {event['event_time']}\n"
        f"{visibility_text(event['visibility'])}\n"
        f"👤 Создал: {html.escape(event['creator_name'])}\n"
        f"👥 Игроков: {filled} / {max_p}"
    )

    kb = InlineKeyboardBuilder()
    signup_by_user = {int(s["user_id"]): s for s in signups}
    slot_buttons: list[InlineKeyboardButton] = []

    for s in signups:
        uid = int(s["user_id"])
        label = f"✓ {s['display_name']}"
        if uid == viewer_id:
            slot_buttons.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{CB_SLOT_LEAVE_PREFIX}{event_id}:{uid}",
                )
            )
        else:
            slot_buttons.append(InlineKeyboardButton(text=label, callback_data="noop"))

    for _ in range(max(0, max_p - filled)):
        slot_buttons.append(
            InlineKeyboardButton(
                text="+ свободно",
                callback_data=f"{CB_SLOT_JOIN_PREFIX}{event_id}",
            )
        )

    for i in range(0, len(slot_buttons), 2):
        row = slot_buttons[i : i + 2]
        kb.row(*row)

    kb.button(text="💬 Чат этой игры", callback_data=f"{CB_EVENT_CHAT_PREFIX}{event_id}")

    if can_manage(viewer_id, event):
        if event["status"] == EVENT_OPEN:
            kb.button(text="🔒 Закрыть запись", callback_data=f"{CB_EVENT_CLOSE_PREFIX}{event_id}")
        else:
            kb.button(text="🔓 Открыть запись", callback_data=f"{CB_EVENT_REOPEN_PREFIX}{event_id}")
        kb.button(text="🗑 Удалить", callback_data=f"{CB_EVENT_DELETE_PREFIX}{event_id}")

    if event["event_type"] == EVENT_TYPE_MASTERCLASS:
        back_cb = CB_MENU_MASTERCLASS
    elif event["event_type"] == EVENT_TYPE_CODENAMES:
        back_cb = CB_GAMES_CODENAMES
    else:
        back_cb = CB_GAMES_MAFIA
    kb.row(*nav_row(back_cb))
    kb.adjust(1)
    return text, kb.as_markup()


async def render_event_card(query: CallbackQuery, event_id: int) -> None:
    text, markup = await build_event_card(event_id, query.from_user.id)
    await edit_message(query, text, markup)


async def render_calendar(query: CallbackQuery) -> None:
    events = await DB.get_upcoming_events()
    kb = InlineKeyboardBuilder()
    for ev in events:
        icon = event_type_icon(ev["event_type"])
        btn = (
            f"{icon} {format_date(ev['event_date'])} — "
            f"{event_type_label(ev['event_type'])} · {ev['title']} · {ev['event_time']}"
        )
        kb.button(text=btn, callback_data=f"{CB_EVENT_VIEW_PREFIX}{ev['id']}")
    kb.button(text="🏠 Главное меню", callback_data=CB_NAV_MAIN)
    kb.adjust(1)
    await edit_message(query, "📅 <b>Все мероприятия</b>\nВыбери дату:", kb.as_markup())


async def create_forum_thread(bot: Bot, event: dict) -> int | None:
    chat_id = SETTINGS.group_chat_id
    if not chat_id or not SETTINGS.group_thread_enabled:
        return None
    icon = event_type_icon(event["event_type"])
    name = f"{icon} {event['title']} · {format_date(event['event_date'])}"
    if len(name) > 128:
        name = name[:125] + "…"
    try:
        topic = await bot.create_forum_topic(chat_id=chat_id, name=name)
        thread_id = topic.message_thread_id
        pin_text = (
            f"<b>{icon} {html.escape(event['title'])}</b>\n"
            f"📅 {format_date(event['event_date'])} · {event['event_time']}\n"
            "Чат участников этой игры. Добро пожаловать!"
        )
        msg = await bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=pin_text,
        )
        try:
            await bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id)
        except TelegramBadRequest:
            pass
        return thread_id
    except (TelegramBadRequest, TelegramForbiddenError):
        return None


def resolve_chat_id() -> int:
    return SETTINGS.group_chat_id or 0


@ROUTER.message(Command("start", "menu"))
async def cmd_start_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_main_menu(message)


@ROUTER.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Создание отменено.")
    await send_main_menu(message)


@ROUTER.message(F.web_app_data)
async def on_web_app_data(message: Message, state: FSMContext) -> None:
    await state.clear()
    await strip_old_reply_keyboard(message)
    action = (message.web_app_data.data or "").strip()
    if action.startswith(CB_EVENT_VIEW_PREFIX):
        event_id = int(action.removeprefix(CB_EVENT_VIEW_PREFIX))
        text, markup = await build_event_card(event_id, message.from_user.id)
        await message.answer(text, reply_markup=markup)
        return
    if action == CB_MENU_GAMES:
        mafia_n = await DB.count_upcoming_by_type(EVENT_TYPE_MAFIA)
        codenames_n = await DB.count_upcoming_by_type(EVENT_TYPE_CODENAMES)
        kb = InlineKeyboardBuilder()
        kb.button(text=f"🌙 Мафия · {mafia_n} предстоящих", callback_data=CB_GAMES_MAFIA)
        kb.button(text=f"🕵 Коднеймс · {codenames_n} предстоящих", callback_data=CB_GAMES_CODENAMES)
        kb.row(*nav_row(CB_NAV_MAIN))
        await message.answer("🎮 <b>Игры</b>\nВыбери игру:", reply_markup=kb.as_markup())
        return
    if action == CB_MENU_MASTERCLASS:
        kb = InlineKeyboardBuilder()
        events = await DB.get_upcoming_events(event_type=EVENT_TYPE_MASTERCLASS)
        for ev in events:
            filled = await DB.confirmed_count(int(ev["id"]))
            vis = visibility_icon(ev["visibility"])
            btn = (
                f"{vis} {ev['title']} · {format_date(ev['event_date'])} · "
                f"{ev['event_time']} · {filled}/{ev['max_players']}"
            )
            kb.button(text=btn, callback_data=f"{CB_EVENT_VIEW_PREFIX}{ev['id']}")
        kb.button(text="➕ Создать мероприятие", callback_data=f"{CB_CREATE_PREFIX}{EVENT_TYPE_MASTERCLASS}")
        kb.row(*nav_row(CB_NAV_MAIN))
        kb.adjust(1)
        await message.answer(
            f"{event_type_icon(EVENT_TYPE_MASTERCLASS)} <b>Мастер-классы</b>\nБлижайшие мероприятия:",
            reply_markup=kb.as_markup(),
        )
        return
    if action == CB_MENU_CALENDAR:
        events = await DB.get_upcoming_events()
        kb = InlineKeyboardBuilder()
        for ev in events:
            icon = event_type_icon(ev["event_type"])
            btn = (
                f"{icon} {format_date(ev['event_date'])} — "
                f"{event_type_label(ev['event_type'])} · {ev['title']} · {ev['event_time']}"
            )
            kb.button(text=btn, callback_data=f"{CB_EVENT_VIEW_PREFIX}{ev['id']}")
        kb.button(text="🏠 Главное меню", callback_data=CB_NAV_MAIN)
        kb.adjust(1)
        await message.answer("📅 <b>Все мероприятия</b>\nВыбери дату:", reply_markup=kb.as_markup())
        return
    await send_main_menu(message)


@ROUTER.message(F.text.in_(LEGACY_REPLY_BUTTONS))
async def legacy_reply_buttons(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_main_menu(message)


@ROUTER.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery) -> None:
    await call.answer()


@ROUTER.callback_query(F.data == CB_NAV_MAIN)
async def cb_nav_main(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render_main_menu(call)
    await call.answer()


@ROUTER.callback_query(F.data == CB_MENU_GAMES)
async def cb_menu_games(call: CallbackQuery) -> None:
    await render_games_menu(call)
    await call.answer()


@ROUTER.callback_query(F.data == CB_MENU_MASTERCLASS)
async def cb_menu_masterclass(call: CallbackQuery) -> None:
    await render_event_list(call, EVENT_TYPE_MASTERCLASS, CB_NAV_MAIN)
    await call.answer()


@ROUTER.callback_query(F.data == CB_MENU_CALENDAR)
async def cb_menu_calendar(call: CallbackQuery) -> None:
    await render_calendar(call)
    await call.answer()


@ROUTER.callback_query(F.data == CB_GAMES_MAFIA)
async def cb_games_mafia(call: CallbackQuery) -> None:
    await render_event_list(call, EVENT_TYPE_MAFIA, CB_MENU_GAMES)
    await call.answer()


@ROUTER.callback_query(F.data == CB_GAMES_CODENAMES)
async def cb_games_codenames(call: CallbackQuery) -> None:
    await render_event_list(call, EVENT_TYPE_CODENAMES, CB_MENU_GAMES)
    await call.answer()


@ROUTER.callback_query(F.data.startswith(CB_EVENT_VIEW_PREFIX))
async def cb_event_view(call: CallbackQuery) -> None:
    event_id = int(call.data.removeprefix(CB_EVENT_VIEW_PREFIX))
    await render_event_card(call, event_id)
    await call.answer()


@ROUTER.callback_query(F.data.startswith(CB_CREATE_PREFIX))
async def cb_create_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.data == "create:cancel":
        await state.clear()
        await call.message.answer("Создание отменено.")
        await send_main_menu(call.message)
        await call.answer()
        return
    event_type = call.data.removeprefix(CB_CREATE_PREFIX)
    if event_type not in (EVENT_TYPE_MAFIA, EVENT_TYPE_CODENAMES, EVENT_TYPE_MASTERCLASS):
        await call.answer("Неизвестный тип.", show_alert=True)
        return
    await state.clear()
    await state.update_data(event_type=event_type)
    await state.set_state(CreateEvent.title)
    kb = InlineKeyboardBuilder()
    kb.button(text="✖️ Отмена", callback_data="create:cancel")
    await call.message.answer(
        "✨ <b>Создаём мероприятие!</b>\n\nНазвание?",
        reply_markup=kb.as_markup(),
    )
    await call.answer()


@ROUTER.message(CreateEvent.title)
async def create_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title or len(title) > 60:
        await message.answer("⚠️ Название: от 1 до 60 символов.")
        return
    await state.update_data(title=title)
    await state.set_state(CreateEvent.date)
    await message.answer("📅 Дата? (<code>ДД.ММ</code> или <code>ДД.ММ.ГГГГ</code>)")


@ROUTER.message(CreateEvent.date)
async def create_date(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    m = DATE_INPUT_RE.match(raw)
    if not m:
        await message.answer("⚠️ Формат: <code>25.06</code> или <code>25.06.2026</code>")
        return
    d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
    year = int(y) if y else date.today().year
    try:
        dt = date(year, mo, d)
    except ValueError:
        await message.answer("⚠️ Некорректная дата.")
        return
    if dt < date.today():
        await message.answer("⚠️ Дата не может быть в прошлом.")
        return
    await state.update_data(event_date=dt.strftime("%Y-%m-%d"))
    await state.set_state(CreateEvent.time)
    await message.answer("⏰ Время? (<code>ЧЧ:ММ</code>)")


@ROUTER.message(CreateEvent.time)
async def create_time(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    m = TIME_INPUT_RE.match(raw)
    if not m:
        await message.answer("⚠️ Формат: <code>19:00</code>")
        return
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        await message.answer("⚠️ Некорректное время.")
        return
    data = await state.get_data()
    event_dt = datetime.strptime(
        f"{data['event_date']} {h:02d}:{mi:02d}",
        "%Y-%m-%d %H:%M",
    )
    if event_dt < datetime.now():
        await message.answer("⚠️ Дата и время должны быть в будущем.")
        return
    await state.update_data(event_time=f"{h:02d}:{mi:02d}")
    await state.set_state(CreateEvent.max_players)
    await message.answer("👥 Максимум участников? (число 2–50)")


@ROUTER.message(CreateEvent.max_players)
async def create_max_players(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("⚠️ Введите целое число.")
        return
    n = int(raw)
    if n < 2 or n > 50:
        await message.answer("⚠️ От 2 до 50 участников.")
        return
    await state.update_data(max_players=n)
    await state.set_state(CreateEvent.visibility)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔓 Открытая для всех", callback_data=CB_VIS_OPEN)
    kb.button(text="🔒 По моему одобрению", callback_data=CB_VIS_APPROVAL)
    kb.adjust(1)
    await message.answer("🔐 <b>Тип записи:</b>", reply_markup=kb.as_markup())


@ROUTER.callback_query(CreateEvent.visibility, F.data.in_({CB_VIS_OPEN, CB_VIS_APPROVAL}))
async def create_visibility(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    visibility = VISIBILITY_OPEN if call.data == CB_VIS_OPEN else VISIBILITY_APPROVAL
    data = await state.get_data()
    user = call.from_user
    event_id = await DB.create_event(
        chat_id=resolve_chat_id(),
        event_type=data["event_type"],
        title=data["title"],
        event_date=data["event_date"],
        event_time=data["event_time"],
        max_players=int(data["max_players"]),
        visibility=visibility,
        creator_id=user.id,
        creator_name=display_name(user),
    )
    event = await DB.get_event(event_id)
    thread_note = ""
    if SETTINGS.group_thread_enabled and SETTINGS.group_chat_id and event:
        thread_id = await create_forum_thread(bot, event)
        if thread_id:
            await DB.set_thread_id(event_id, thread_id)
            thread_note = "\n💬 Тред создан"
        else:
            thread_note = "\n<i>Тред не создан — проверьте права бота в группе.</i>"

    await state.clear()
    icon = event_type_icon(data["event_type"])
    vis_line = visibility_text(visibility)
    await call.message.answer(
        "✅ <b>Готово! Мероприятие создано.</b>\n\n"
        f"{icon} {html.escape(data['title'])}\n"
        f"📅 {format_date(data['event_date'])} · {data['event_time']} · 0/{data['max_players']}\n"
        f"{vis_line}{thread_note}",
        reply_markup=InlineKeyboardBuilder()
        .button(text="👀 Открыть карточку", callback_data=f"{CB_OPEN_CARD_PREFIX}{event_id}")
        .button(text="🏠 Главное меню", callback_data=CB_NAV_MAIN)
        .adjust(1)
        .as_markup(),
    )
    await call.answer()


@ROUTER.callback_query(F.data.startswith(CB_OPEN_CARD_PREFIX))
async def cb_open_card(call: CallbackQuery) -> None:
    event_id = int(call.data.removeprefix(CB_OPEN_CARD_PREFIX))
    text, markup = await build_event_card(event_id, call.from_user.id)
    await call.message.answer(text, reply_markup=markup)
    await call.answer()


@ROUTER.callback_query(F.data.startswith(CB_SLOT_JOIN_PREFIX))
async def cb_slot_join(call: CallbackQuery, bot: Bot) -> None:
    event_id = int(call.data.removeprefix(CB_SLOT_JOIN_PREFIX))
    event = await DB.get_event(event_id)
    if not event:
        await call.answer("Мероприятие не найдено.", show_alert=True)
        return
    if event["status"] == EVENT_CLOSED:
        await call.answer("Запись закрыта", show_alert=True)
        return
    uid = call.from_user.id
    existing = await DB.get_signup(event_id, uid)
    if existing:
        await call.answer("Ты уже в списке 👍", show_alert=True)
        return
    confirmed = await DB.confirmed_count(event_id)
    if confirmed >= int(event["max_players"]):
        await call.answer("Мест нет 😔 Следи за открытием", show_alert=True)
        return

    name = display_name(call.from_user)
    if event["visibility"] == VISIBILITY_OPEN:
        await DB.add_signup(
            event_id=event_id,
            user_id=uid,
            display_name=name,
            status=SIGNUP_CONFIRMED,
        )
        await render_event_card(call, event_id)
        await call.answer("Ты в игре! 🎉")
        return

    await DB.add_signup(
        event_id=event_id,
        user_id=uid,
        display_name=name,
        status=SIGNUP_PENDING,
    )
    await render_event_card(call, event_id)
    await call.answer("Заявка отправлена! Ждём подтверждения организатора 🙏")
    creator_id = int(event["creator_id"])
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять", callback_data=f"{CB_APPROVE_PREFIX}{event_id}:{uid}")
    kb.button(text="❌ Отклонить", callback_data=f"{CB_REJECT_PREFIX}{event_id}:{uid}")
    try:
        await bot.send_message(
            creator_id,
            "📩 <b>Новая заявка на участие!</b>\n"
            f"Игра: {html.escape(event['title'])} · "
            f"{format_date(event['event_date'])} · {event['event_time']}\n"
            f"От: {html.escape(name)}",
            reply_markup=kb.as_markup(),
        )
    except TelegramForbiddenError:
        pass


@ROUTER.callback_query(F.data.startswith(CB_SLOT_LEAVE_PREFIX))
async def cb_slot_leave(call: CallbackQuery) -> None:
    parts = call.data.removeprefix(CB_SLOT_LEAVE_PREFIX).split(":")
    event_id, target_uid = int(parts[0]), int(parts[1])
    if call.from_user.id != target_uid:
        await call.answer()
        return
    await DB.remove_signup(event_id, target_uid)
    await render_event_card(call, event_id)
    await call.answer("Отписался")


@ROUTER.callback_query(F.data.startswith(CB_APPROVE_PREFIX))
async def cb_approve(call: CallbackQuery, bot: Bot) -> None:
    parts = call.data.removeprefix(CB_APPROVE_PREFIX).split(":")
    event_id, user_id = int(parts[0]), int(parts[1])
    event = await DB.get_event(event_id)
    if not event or not can_manage(call.from_user.id, event):
        await call.answer("Нет доступа.", show_alert=True)
        return
    confirmed = await DB.confirmed_count(event_id)
    if confirmed >= int(event["max_players"]):
        await call.answer("Мест больше нет.", show_alert=True)
        return
    await DB.set_signup_status(event_id, user_id, SIGNUP_CONFIRMED)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Принято ✅")
    try:
        await bot.send_message(
            user_id,
            f"✅ Твоя заявка на {html.escape(event['title'])} подтверждена!",
        )
    except TelegramForbiddenError:
        pass


@ROUTER.callback_query(F.data.startswith(CB_REJECT_PREFIX))
async def cb_reject(call: CallbackQuery, bot: Bot) -> None:
    parts = call.data.removeprefix(CB_REJECT_PREFIX).split(":")
    event_id, user_id = int(parts[0]), int(parts[1])
    event = await DB.get_event(event_id)
    if not event or not can_manage(call.from_user.id, event):
        await call.answer("Нет доступа.", show_alert=True)
        return
    await DB.remove_signup(event_id, user_id)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Отклонено")
    try:
        await bot.send_message(
            user_id,
            f"❌ По заявке на {html.escape(event['title'])} отказано. "
            "Попробуй записаться на другую игру.",
        )
    except TelegramForbiddenError:
        pass


@ROUTER.callback_query(F.data.startswith(CB_EVENT_CHAT_PREFIX))
async def cb_event_chat(call: CallbackQuery, bot: Bot) -> None:
    event_id = int(call.data.removeprefix(CB_EVENT_CHAT_PREFIX))
    event = await DB.get_event(event_id)
    if not event:
        await call.answer("Не найдено.", show_alert=True)
        return

    if not SETTINGS.group_thread_enabled:
        await call.answer()
        await call.message.answer("Треды не включены. Обсуждение ведётся в общем чате группы.")
        return

    thread_id = event.get("thread_id")
    chat_id = int(event["chat_id"]) or SETTINGS.group_chat_id
    if not chat_id:
        await call.answer("Группа не настроена (GROUP_CHAT_ID).", show_alert=True)
        return

    if thread_id:
        link = thread_link(chat_id, int(thread_id))
        kb = InlineKeyboardBuilder()
        kb.button(text="💬 Открыть тред в группе →", url=link)
        await call.message.answer("💬 Чат мероприятия:", reply_markup=kb.as_markup())
        await call.answer()
        return

    thread_id = await create_forum_thread(bot, event)
    if thread_id:
        await DB.set_thread_id(event_id, thread_id)
        link = thread_link(chat_id, thread_id)
        kb = InlineKeyboardBuilder()
        kb.button(text="💬 Открыть тред в группе →", url=link)
        await call.message.answer("💬 Чат мероприятия:", reply_markup=kb.as_markup())
    else:
        await call.message.answer("Не удалось создать тред. Проверьте права бота в группе.")
    await call.answer()


@ROUTER.callback_query(F.data.startswith(CB_EVENT_CLOSE_PREFIX))
async def cb_event_close(call: CallbackQuery) -> None:
    event_id = int(call.data.removeprefix(CB_EVENT_CLOSE_PREFIX))
    event = await DB.get_event(event_id)
    if not event or not can_manage(call.from_user.id, event):
        await call.answer("Нет доступа.", show_alert=True)
        return
    await DB.set_event_status(event_id, EVENT_CLOSED)
    await render_event_card(call, event_id)
    await call.answer("Запись закрыта")


@ROUTER.callback_query(F.data.startswith(CB_EVENT_REOPEN_PREFIX))
async def cb_event_reopen(call: CallbackQuery) -> None:
    event_id = int(call.data.removeprefix(CB_EVENT_REOPEN_PREFIX))
    event = await DB.get_event(event_id)
    if not event or not can_manage(call.from_user.id, event):
        await call.answer("Нет доступа.", show_alert=True)
        return
    await DB.set_event_status(event_id, EVENT_OPEN)
    await render_event_card(call, event_id)
    await call.answer("Запись открыта")


@ROUTER.callback_query(F.data.startswith(CB_EVENT_DELETE_PREFIX))
async def cb_event_delete(call: CallbackQuery) -> None:
    event_id = int(call.data.removeprefix(CB_EVENT_DELETE_PREFIX))
    event = await DB.get_event(event_id)
    if not event or not can_manage(call.from_user.id, event):
        await call.answer("Нет доступа.", show_alert=True)
        return
    await DB.delete_event(event_id)
    await render_main_menu(call)
    await call.answer("Удалено")


@ROUTER.message()
async def fallback(message: Message) -> None:
    await send_main_menu(message)


async def main() -> None:
    global DB, SETTINGS
    SETTINGS = load_settings()
    DB = Database(SETTINGS.db_path)
    await DB.init()
    print(f"{BRAND} bot start {MENU_BUILD_TAG} db={SETTINGS.db_path!r}")

    bot = Bot(
        token=SETTINGS.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    await start_webapp_server(DB, port=SETTINGS.webapp_port)
    print(f"WebApp server on :{SETTINGS.webapp_port}")

    if SETTINGS.webapp_public_url.startswith("https://"):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Меню OPC",
                web_app=WebAppInfo(url=f"{SETTINGS.webapp_public_url}/"),
            )
        )

    dp = Dispatcher()
    dp.include_router(ROUTER)
    dp.message.middleware(TrackUsersMiddleware())
    dp.callback_query.middleware(TrackUsersMiddleware())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
