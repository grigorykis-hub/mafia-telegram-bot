from __future__ import annotations

import asyncio
import html
import re
from datetime import datetime
from typing import Any

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
)
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    TelegramObject,
    User,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import Settings, load_settings
from database import (
    MASTERCLASS_DIRECTION_STUB,
    GAME_KIND_MASTERCLASS,
    GAME_KIND_MAFIA,
    Database,
)
from theme import (
    BTN_ADMIN,
    BTN_ADMIN_ADD_CAPO,
    BTN_ADMIN_BROADCAST,
    BTN_ADMIN_NEW_GAME,
    BTN_ADMIN_NEW_MASTERCLASS,
    BTN_ADMIN_NOTIFY_GAME,
    BTN_ADMIN_PHOTOS,
    BTN_BACK,
    BTN_CALENDAR,
    BTN_CANCEL,
    BTN_DIR_ADULT,
    BTN_DIR_CHILD,
    BTN_FINISH_UPLOAD,
    BTN_MAFIA,
    BTN_MASTERCLASS,
    BTN_MASTERCLASS_SHORT,
    BTN_PAST,
    BTN_UPCOMING,
    LEGACY_ADMIN,
    LEGACY_ADMIN_ADD_CAPO,
    LEGACY_ADMIN_BROADCAST,
    LEGACY_ADMIN_NEW_GAME,
    LEGACY_ADMIN_NEW_MASTERCLASS,
    LEGACY_ADMIN_PHOTOS,
    LEGACY_BACK,
    LEGACY_CALENDAR,
    LEGACY_CANCEL,
    LEGACY_FINISH_UPLOAD,
    LEGACY_MAFIA,
    LEGACY_MASTERCLASS,
    LEGACY_MASTERCLASS_ALT,
    LEGACY_MASTERCLASS_SHORT,
    LEGACY_PAST,
    LEGACY_UPCOMING,
    format_calendar_header,
    format_game_card,
    html_mafia_hub,
    html_masterclass_hub,
    html_no_masterclasses,
    html_pick_masterclass,
    html_access_denied,
    html_admin_panel,
    html_calendar_empty,
    html_main_menu_hint,
    html_no_past,
    html_no_upcoming,
    html_pick_game,
    html_pick_past,
    html_welcome,
    is_cancel_text,
    MENU_BUILD_TAG,
    resolve_direction_choice,
)


DATE_INPUT_FORMAT = "%d.%m.%Y %H:%M"
DB_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

ROUTER = Router()
DB: Database
SETTINGS: Settings


class AdminCreateGame(StatesGroup):
    title = State()
    date = State()
    direction = State()
    capacity = State()
    price = State()


class AdminCreateMasterclass(StatesGroup):
    title = State()
    date = State()
    capacity = State()
    price = State()


class AdminUploadPhotos(StatesGroup):
    waiting_photos = State()


class AdminAddAdmin(StatesGroup):
    waiting_login = State()


class AdminBroadcast(StatesGroup):
    waiting_text = State()


class AdminNotifyParticipants(StatesGroup):
    waiting_text = State()


def now_iso() -> str:
    return datetime.now().strftime(DB_DATE_FORMAT)


def to_user_datetime(date_iso: str) -> str:
    dt = datetime.strptime(date_iso, DB_DATE_FORMAT)
    return dt.strftime("%d.%m.%Y %H:%M")


def direction_to_human(direction: str) -> str:
    return "Взрослый стол" if direction == "adult" else "Детский стол"


def row_kind(game: dict) -> str:
    return (game.get("kind") or GAME_KIND_MAFIA).strip() or GAME_KIND_MAFIA


def row_price_html(game: dict) -> str:
    s = (game.get("price_text") or "").strip()
    return html.escape(s) if s else "<i>не указана</i>"


def row_type_line_html(game: dict) -> str:
    if row_kind(game) == GAME_KIND_MASTERCLASS:
        return "🎓 <b>Формат:</b> мастер-класс"
    return f"🎭 <b>Стол:</b> {html.escape(direction_to_human(game['direction']))}"


def inline_event_caption(game: dict) -> str:
    """Подпись инлайн-кнопки (лимит Telegram ~64 символа)."""
    dt = to_user_datetime(game["game_date"])
    title = game["title"]
    if len(title) > 18:
        title = title[:17] + "…"
    if row_kind(game) == GAME_KIND_MASTERCLASS:
        mark = "МК"
        prefix = "🎓"
    else:
        mark = "Взр." if game["direction"] == "adult" else "Дет."
        prefix = "🎴"
    raw = f"{prefix} {dt} · {title} · {mark}"
    return raw if len(raw) <= 64 else raw[:61] + "…"


TELEGRAM_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{5,32}$")


def normalize_username(username: str | None) -> str | None:
    if not username:
        return None
    s = username.strip().lstrip("@").lower()
    return s if s else None


def is_version_slash_command(text: str | None) -> bool:
    """В группах Telegram шлёт /version@BotName — стандартный Command без ignore_mention не ловит."""
    if not text:
        return False
    head = text.strip().split()[0]
    return head == "/version" or head.startswith("/version@")


async def is_admin(user: User | None) -> bool:
    if user is None:
        return False
    uname = normalize_username(user.username)
    if user.id in SETTINGS.admin_ids:
        if not SETTINGS.admin_usernames:
            return True
        if uname and uname in SETTINGS.admin_usernames:
            return True
    if uname and await DB.is_dynamic_admin(uname):
        return True
    return False


async def main_menu_kb(user: User | None) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    # Первая строка — мафия и мастер-класс рядом (на узких экранах столбец режет подписи).
    kb.button(text=BTN_MAFIA)
    kb.button(text=BTN_MASTERCLASS_SHORT)
    kb.button(text=BTN_CALENDAR)
    if await is_admin(user):
        kb.button(text=BTN_ADMIN)
        kb.adjust(2, 2)
    else:
        kb.adjust(2, 1)
    return kb.as_markup(resize_keyboard=True, is_persistent=False)


def mafia_hub_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_UPCOMING)
    kb.button(text=BTN_PAST)
    kb.button(text=BTN_BACK)
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True, is_persistent=True)


def masterclass_hub_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_BACK)
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True, is_persistent=True)


async def send_main_menu_message(message: Message, text: str) -> None:
    """Главное меню. Новая reply-клавиатура от Telegram подменяет предыдущую — отдельный Remove не шлём."""
    await message.answer(text, reply_markup=await main_menu_kb(message.from_user))


async def ensure_main_menu_keyboard(message: Message) -> None:
    """Обновить нижнюю клавиатуру без лишнего текста (легаси-подписи у пользователя)."""
    try:
        await message.answer("\u2060", reply_markup=await main_menu_kb(message.from_user))
    except TelegramNetworkError:
        return


def cancel_only_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_CANCEL)
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


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


def admin_menu_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_ADMIN_NEW_GAME)
    kb.button(text=BTN_ADMIN_NEW_MASTERCLASS)
    kb.button(text=BTN_ADMIN_PHOTOS)
    kb.button(text=BTN_ADMIN_ADD_CAPO)
    kb.button(text=BTN_ADMIN_BROADCAST)
    kb.button(text=BTN_ADMIN_NOTIFY_GAME)
    kb.button(text=BTN_BACK)
    kb.adjust(2, 2, 2, 1)
    return kb.as_markup(resize_keyboard=True, is_persistent=True)


async def send_admin_panel(message: Message) -> None:
    await message.answer(html_admin_panel(), reply_markup=admin_menu_kb())


def direction_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_DIR_ADULT)
    kb.button(text=BTN_DIR_CHILD)
    kb.button(text=BTN_CANCEL)
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


def finish_upload_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_FINISH_UPLOAD)
    kb.button(text=BTN_CANCEL)
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


def games_inline_kb(games: list[dict], prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for game in games:
        builder.button(text=inline_event_caption(game), callback_data=f"{prefix}:{game['id']}")
    builder.adjust(1)
    return builder.as_markup()


def game_actions_kb_for(game: dict) -> InlineKeyboardMarkup:
    gid = int(game["id"])
    is_mc = row_kind(game) == GAME_KIND_MASTERCLASS
    builder = InlineKeyboardBuilder()
    join_txt = "🎓 Записаться" if is_mc else "🪑 За стол"
    leave_txt = "🚪 Отменить запись" if is_mc else "🚪 Вон из дома"
    builder.button(text=join_txt, callback_data=f"join:{gid}")
    builder.button(text=leave_txt, callback_data=f"leave:{gid}")
    builder.adjust(1)
    return builder.as_markup()


def admin_upload_pick_game_kb(games: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for game in games:
        builder.button(text=inline_event_caption(game), callback_data=f"upload_pick:{game['id']}")
    builder.adjust(1)
    return builder.as_markup()


async def compose_game_details(game_id: int) -> str:
    game = await DB.get_game(game_id)
    if not game:
        return "🎭 <i>Событие не найдено — возможно, его уже сняли с афиши.</i>"

    participants = await DB.get_registrations(game_id)
    count = len(participants)
    free_slots = max(int(game["capacity"]) - count, 0)
    title_esc = html.escape(game["title"])
    when_esc = html.escape(to_user_datetime(game["game_date"]))
    lead = "🎓" if row_kind(game) == GAME_KIND_MASTERCLASS else "🎴"
    participants_title = (
        "<i>Пока пусто — будь первым у дверей.</i>"
        if row_kind(game) == GAME_KIND_MASTERCLASS
        else "<i>Пока никого — только пустые стулья.</i>"
    )

    if not participants:
        block = participants_title
    else:
        lines: list[str] = []
        for idx, user in enumerate(participants, start=1):
            uname = f"@{user['username']}" if user["username"] else "—"
            dn = html.escape(user["display_name"])
            lines.append(f"{idx}. {dn} <code>({html.escape(uname)})</code>")
        block = "\n".join(lines)

    return format_game_card(
        title=title_esc,
        lead_emoji=lead,
        when=when_esc,
        type_line_html=row_type_line_html(game),
        count=count,
        free=free_slots,
        price_line_html=row_price_html(game),
        participants_block=block,
    )


@ROUTER.message(Command("start", ignore_mention=True))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_main_menu_message(message, html_welcome())


@ROUTER.message(Command("menu", ignore_mention=True))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_main_menu_message(
        message,
        "<b>⌨️ Клавиатура обновлена.</b>\n" + html_main_menu_hint(),
    )


@ROUTER.message(F.text.func(is_version_slash_command))
async def cmd_version(message: Message) -> None:
    """Диагностика деплоя: /version и /version@BotName (часто в группах)."""
    await message.answer(
        f"Версия кода: {MENU_BUILD_TAG}\n"
        "Если до этого вместо этого приходило «только через меню» — на сервере была старая сборка "
        "или второй процесс с тем же токеном.",
        parse_mode=None,
    )


@ROUTER.message(F.text.in_({BTN_BACK, LEGACY_BACK}))
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_main_menu_message(message, html_main_menu_hint())


@ROUTER.message(F.text.in_({BTN_MAFIA, LEGACY_MAFIA}))
async def mafia_hub(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(html_mafia_hub(), reply_markup=mafia_hub_kb())


@ROUTER.message(
    F.text.in_(
        {
            BTN_MASTERCLASS,
            BTN_MASTERCLASS_SHORT,
            LEGACY_MASTERCLASS,
            LEGACY_MASTERCLASS_ALT,
            LEGACY_MASTERCLASS_SHORT,
        }
    ),
)
async def masterclass_hub(message: Message, state: FSMContext) -> None:
    await state.clear()
    games = await DB.get_upcoming_games(now_iso(), kind=GAME_KIND_MASTERCLASS)
    await message.answer(html_masterclass_hub(), reply_markup=masterclass_hub_kb())
    if not games:
        await message.answer(html_no_masterclasses())
        return
    await message.answer(
        html_pick_masterclass(),
        reply_markup=games_inline_kb(games, "game"),
    )


@ROUTER.message(F.text.in_({BTN_UPCOMING, LEGACY_UPCOMING}))
async def upcoming_games(message: Message) -> None:
    if (message.text or "").strip() == LEGACY_UPCOMING:
        await ensure_main_menu_keyboard(message)
    games = await DB.get_upcoming_games(now_iso(), kind=GAME_KIND_MAFIA)
    if not games:
        await message.answer(html_no_upcoming())
        return
    await message.answer(
        html_pick_game(),
        reply_markup=games_inline_kb(games, "game"),
    )


@ROUTER.callback_query(F.data.startswith("game:"))
async def show_game(call: CallbackQuery) -> None:
    game_id = int(call.data.split(":")[1])
    game = await DB.get_game(game_id)
    if not game:
        await call.answer("Событие не найдено.", show_alert=True)
        return
    text = await compose_game_details(game_id)
    await call.message.answer(text, reply_markup=game_actions_kb_for(game))
    await call.answer()


@ROUTER.callback_query(F.data.startswith("join:"))
async def join_game(call: CallbackQuery) -> None:
    game_id = int(call.data.split(":")[1])
    user = call.from_user
    display_name = user.full_name.strip() or f"user_{user.id}"
    ok, text = await DB.register_user(
        game_id=game_id,
        user_id=user.id,
        display_name=display_name,
        username=user.username,
    )
    details = await compose_game_details(game_id)
    game = await DB.get_game(game_id)
    await call.message.answer(text, parse_mode=None)
    if ok and game:
        await call.message.answer(details, reply_markup=game_actions_kb_for(game))
    await call.answer()


@ROUTER.callback_query(F.data.startswith("leave:"))
async def leave_game(call: CallbackQuery) -> None:
    game_id = int(call.data.split(":")[1])
    ok, text = await DB.unregister_user(game_id=game_id, user_id=call.from_user.id)
    details = await compose_game_details(game_id)
    game = await DB.get_game(game_id)
    await call.message.answer(text, parse_mode=None)
    if ok and game:
        await call.message.answer(details, reply_markup=game_actions_kb_for(game))
    await call.answer()


@ROUTER.message(F.text.in_({BTN_PAST, LEGACY_PAST}))
async def past_games(message: Message) -> None:
    if (message.text or "").strip() == LEGACY_PAST:
        await ensure_main_menu_keyboard(message)
    games = await DB.get_past_games(now_iso())
    if not games:
        await message.answer(html_no_past())
        return

    await message.answer(
        html_pick_past(),
        reply_markup=games_inline_kb(games, "past"),
    )


@ROUTER.callback_query(F.data.startswith("past:"))
async def show_past_game(call: CallbackQuery) -> None:
    game_id = int(call.data.split(":")[1])
    game = await DB.get_game(game_id)
    if not game:
        await call.answer("Игра не найдена.", show_alert=True)
        return

    await call.message.answer(
        f"<b>🌑 Архив</b> · <i>{html.escape(game['title'])}</i>\n"
        f"📆 <b>Было:</b> {html.escape(to_user_datetime(game['game_date']))}\n"
        f"🎭 <b>Стол:</b> {html.escape(direction_to_human(game['direction']))}"
    )

    photos = await DB.get_photos(game_id)
    if not photos:
        await call.message.answer("📷 <i>В досье пока ни одного снимка.</i>")
    else:
        media = [InputMediaPhoto(media=file_id) for file_id in photos[:10]]
        await call.message.answer_media_group(media)
        if len(photos) > 10:
            await call.message.answer(
                f"📷 Первые 10 снимков из <b>{len(photos)}</b>. Остальные — по одному сообщению ниже."
            )
            for file_id in photos[10:]:
                await call.message.answer_photo(file_id)

    await call.answer()


@ROUTER.message(F.text.in_({BTN_CALENDAR, LEGACY_CALENDAR}))
async def calendar_games(message: Message) -> None:
    if (message.text or "").strip() == LEGACY_CALENDAR:
        await ensure_main_menu_keyboard(message)
    games = await DB.get_upcoming_games(now_iso())
    if not games:
        await message.answer(html_calendar_empty())
        return

    game_ids = [int(g["id"]) for g in games]
    reg_by_game = await DB.get_registration_counts(game_ids)

    grouped: dict[str, list[str]] = {}
    for game in games:
        dt = datetime.strptime(game["game_date"], DB_DATE_FORMAT)
        day_key = dt.strftime("%d.%m.%Y")
        gid = int(game["id"])
        reg_count = reg_by_game.get(gid, 0)
        cap = int(game["capacity"])
        free = max(cap - reg_count, 0)
        price_show = html.escape(price_s) if (price_s := (game.get("price_text") or "").strip()) else "<i>не указана</i>"
        badge = "🎓" if row_kind(game) == GAME_KIND_MASTERCLASS else "🎴"
        if row_kind(game) == GAME_KIND_MASTERCLASS:
            type_line = "<b>🎓 Мастер-класс</b>"
        else:
            type_line = (
                "Стол: "
                f"<i>{html.escape(direction_to_human(game['direction']))}</i>"
            )
        block = (
            f"{badge} • <b>{html.escape(day_key)}</b> · <code>{dt.strftime('%H:%M')}</code>\n"
            f"  <b>{html.escape(game['title'])}</b>\n"
            f"  🪑 <b>Свободно мест:</b> {free} · <b>Всего мест:</b> {cap}\n"
            f"  💰 <b>Стоимость:</b> {price_show}\n"
            f"  {type_line}"
        )
        grouped.setdefault(day_key, []).append(block)

    lines = [format_calendar_header(), ""]
    for day_key in sorted(
        grouped.keys(),
        key=lambda d: datetime.strptime(d, "%d.%m.%Y"),
    ):
        for block in grouped[day_key]:
            lines.append(block)
            lines.append("")

    await message.answer("\n".join(lines).rstrip())


@ROUTER.message(Command("admin", ignore_mention=True))
async def cmd_admin(message: Message) -> None:
    if not await is_admin(message.from_user):
        await message.answer(html_access_denied())
        return
    await send_admin_panel(message)


@ROUTER.message(F.text.in_({BTN_ADMIN, LEGACY_ADMIN}))
async def admin_panel(message: Message) -> None:
    if not await is_admin(message.from_user):
        await message.answer(html_access_denied())
        return
    await send_admin_panel(message)


@ROUTER.message(F.text.in_({BTN_ADMIN_ADD_CAPO, LEGACY_ADMIN_ADD_CAPO}))
async def admin_add_admin_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await message.answer(html_access_denied())
        return
    await state.set_state(AdminAddAdmin.waiting_login)
    await message.answer(
        "<b>🤝 Вербовка</b>\n"
        "Отправьте <b>логин</b> в Telegram <i>без</i> символа <code>@</code> "
        "(пример: <code>Grigory_K</code>).\n\n"
        f"После этого у человека появится кнопка «{BTN_ADMIN}», когда он напишет боту.",
        reply_markup=cancel_only_kb(),
    )


@ROUTER.message(AdminAddAdmin.waiting_login)
async def admin_add_admin_login(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await state.clear()
        return
    if is_cancel_text(message.text):
        await state.clear()
        await send_main_menu_message(message, "<i>Операция отменена.</i>")
        return
    raw = (message.text or "").strip().lstrip("@").lower()
    if not raw:
        await message.answer("✍️ Введите логин латиницей, например <code>Ivan_Ivanov</code>")
        return
    if not TELEGRAM_USERNAME_RE.match(raw):
        await message.answer(
            "⚠️ Неверный формат. Нужен username Telegram: <b>5–32</b> символов, "
            "латиница, цифры и <code>_</code>.\nПример: <code>player_one</code>",
        )
        return
    if raw in SETTINGS.admin_usernames or await DB.is_dynamic_admin(raw):
        await state.clear()
        await send_main_menu_message(
            message,
            "🎩 <i>Этот логин уже в кругу «своих».</i>",
        )
        return
    _, reply = await DB.add_dynamic_admin(
        username_lower=raw,
        added_by_user_id=message.from_user.id,
    )
    await state.clear()
    await message.answer(
        html.escape(reply),
        reply_markup=await main_menu_kb(message.from_user),
        parse_mode=None,
    )


@ROUTER.message(F.text.in_({BTN_ADMIN_BROADCAST, LEGACY_ADMIN_BROADCAST}))
async def admin_broadcast_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await message.answer(html_access_denied())
        return
    await state.set_state(AdminBroadcast.waiting_text)
    await message.answer(
        "<b>📣 Созвать город</b>\n"
        "Напишите текст объявления. Сообщение уйдёт <b>всем</b>, кто хоть раз "
        "заглядывал в бота (до <b>4096</b> символов).",
        reply_markup=cancel_only_kb(),
    )


@ROUTER.message(AdminBroadcast.waiting_text)
async def admin_broadcast_run(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await is_admin(message.from_user):
        await state.clear()
        return
    if not message.text:
        await message.answer("✍️ Нужен текст или кнопка «Стоп».")
        return
    if is_cancel_text(message.text):
        await state.clear()
        await send_main_menu_message(message, "<i>Рассылка отменена.</i>")
        return
    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Пустое сообщение не отправить.")
        return
    if len(text) > 4096:
        await message.answer("⚠️ Слишком длинно. Максимум <b>4096</b> символов.")
        return
    user_ids = await DB.get_known_user_ids()
    if not user_ids:
        await state.clear()
        await send_main_menu_message(
            message,
            "🌃 <i>В городе пусто — в базе ещё никого нет.</i>",
        )
        return

    await message.answer(f"📣 <b>Рассылка…</b> получателей: <code>{len(user_ids)}</code>")

    ok = 0
    blocked = 0
    other_errors = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode=None)
            ok += 1
        except TelegramForbiddenError:
            blocked += 1
        except TelegramBadRequest:
            other_errors += 1
        await asyncio.sleep(0.04)

    await state.clear()
    await send_main_menu_message(
        message,
        "<b>📋 Итог</b>\n"
        f"✅ Доставлено: <b>{ok}</b>\n"
        f"🚫 Заблокировали бота: <b>{blocked}</b>\n"
        f"⚠️ Прочие ошибки: <b>{other_errors}</b>",
    )


@ROUTER.message(F.text == BTN_ADMIN_NOTIFY_GAME)
async def admin_notify_game_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await message.answer(html_access_denied())
        return
    await state.clear()
    games = await DB.get_upcoming_games(now_iso())
    if not games:
        await message.answer(
            "🌃 <i>Сейчас ничего не запланировано — выберите другой способ рассылки.</i>",
        )
        return
    await message.answer(
        "<b>📨 Рассылка участникам</b>\n"
        "Выберите игру или мастер-класс — сообщение получат только <b>записавшиеся участники</b>:",
        reply_markup=games_inline_kb(games, "notify_game"),
    )



@ROUTER.callback_query(F.data.startswith("notify_game:"))
async def admin_notify_game_picked(call: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(call.from_user):
        await call.answer("🚫 Нет доступа.", show_alert=True)
        return
    game_id = int(call.data.split(":")[1])
    game = await DB.get_game(game_id)
    if not game:
        await call.answer("Событие не найдено.", show_alert=True)
        return
    if game["game_date"] < now_iso():
        await call.answer("Событие уже в прошлом — выберите другую.", show_alert=True)
        return
    user_ids = await DB.get_registered_user_ids(game_id)
    n = len(user_ids)
    await state.set_state(AdminNotifyParticipants.waiting_text)
    await state.update_data(notify_game_id=game_id)
    await call.message.answer(
        "<b>📨 Рассылка участникам</b>\n"
        f"Событие: <b>{html.escape(game['title'])}</b>\n"
        f"Дата: <code>{html.escape(to_user_datetime(game['game_date']))}</code>\n"
        f"Записано: <b>{n}</b>\n\n"
        + (
            "Введите текст объявления (до <b>4096</b> символов). "
            "Его получат только участники этого события."
            if n
            else "<i>Пока никто не записан — после текста бот сообщит, что отправить некому.</i> Нажмите «Стоп», если передумали."
        ),
        reply_markup=cancel_only_kb(),
    )
    await call.answer()


@ROUTER.message(AdminNotifyParticipants.waiting_text)
async def admin_notify_game_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await is_admin(message.from_user):
        await state.clear()
        return
    if not message.text:
        await message.answer("✍️ Нужен текст или «Стоп».")
        return
    if is_cancel_text(message.text):
        await state.clear()
        await send_main_menu_message(message, "<i>Рассылка отменена.</i>")
        return
    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Пустое сообщение не отправить.")
        return
    if len(text) > 4096:
        await message.answer("⚠️ Слишком длинно. Максимум <b>4096</b> символов.")
        return
    data = await state.get_data()
    game_id = data.get("notify_game_id")
    if not game_id:
        await state.clear()
        await send_main_menu_message(message, "⚠️ Сессия сбита — начните заново из админки.")
        return
    game = await DB.get_game(int(game_id))
    if not game or game["game_date"] < now_iso():
        await state.clear()
        await send_main_menu_message(message, "⚠️ Событие недоступно или уже прошло.")
        return

    user_ids = await DB.get_registered_user_ids(int(game_id))
    if not user_ids:
        await state.clear()
        await send_main_menu_message(
            message,
            "ℹ️ <i>На это событие никто не записан — рассылка не нужна.</i>",
        )
        return

    await message.answer(
        f"📨 <b>Отправка…</b> участников: <code>{len(user_ids)}</code>",
    )
    ok = 0
    blocked = 0
    other_errors = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode=None)
            ok += 1
        except TelegramForbiddenError:
            blocked += 1
        except TelegramBadRequest:
            other_errors += 1
        await asyncio.sleep(0.04)

    await state.clear()
    await send_main_menu_message(
        message,
        "<b>📋 Итог по рассылке</b>\n"
        f"Событие: {html.escape(game['title'])}\n"
        f"✅ Доставлено: <b>{ok}</b>\n"
        f"🚫 Заблокировали бота: <b>{blocked}</b>\n"
        f"⚠️ Прочие ошибки: <b>{other_errors}</b>",
    )


@ROUTER.message(F.text.in_({BTN_ADMIN_NEW_GAME, LEGACY_ADMIN_NEW_GAME}))
async def admin_add_game_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await message.answer(html_access_denied())
        return
    await state.set_state(AdminCreateGame.title)
    await message.answer(
        "<b>➕ Новая партия</b>\nКак назовём игру?",
        reply_markup=ReplyKeyboardRemove(),
    )


@ROUTER.message(AdminCreateGame.title)
async def admin_add_game_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("⚠️ Название не может быть пустым.")
        return
    await state.update_data(title=title)
    await state.set_state(AdminCreateGame.date)
    await message.answer(
        "📆 Укажите <b>дату и время</b> партии:\n<code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n"
        "<i>Пример:</i> <code>25.05.2026 19:00</code>",
    )


@ROUTER.message(AdminCreateGame.date)
async def admin_add_game_date(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    try:
        dt = datetime.strptime(raw, DATE_INPUT_FORMAT)
    except ValueError:
        await message.answer("⚠️ Формат не тот. Нужно: <code>25.05.2026 19:00</code>")
        return

    if dt <= datetime.now():
        await message.answer("⚠️ Дата должна быть <b>в будущем</b>.")
        return

    await state.update_data(game_date_iso=dt.strftime(DB_DATE_FORMAT))
    await state.set_state(AdminCreateGame.direction)
    await message.answer(
        "🎭 Какой <b>стол</b>?",
        reply_markup=direction_kb(),
    )


@ROUTER.message(AdminCreateGame.direction)
async def admin_add_game_direction(message: Message, state: FSMContext) -> None:
    t = (message.text or "").strip()
    if is_cancel_text(message.text):
        await state.clear()
        await send_main_menu_message(message, "<i>Создание партии отменено.</i>")
        return

    direction = resolve_direction_choice(t)
    if direction is None:
        await message.answer("👆 Нажмите кнопку стола подсказки.")
        return

    await state.update_data(direction=direction)
    await state.set_state(AdminCreateGame.capacity)
    await message.answer(
        "🪑 Сколько <b>мест</b> за столом? (число)",
        reply_markup=ReplyKeyboardRemove(),
    )


@ROUTER.message(AdminCreateGame.capacity)
async def admin_add_game_capacity(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("⚠️ Введите целое число, например <code>12</code>.")
        return
    capacity = int(raw)
    if capacity <= 0:
        await message.answer("⚠️ Мест должно быть больше нуля.")
        return

    await state.update_data(capacity=capacity)
    await state.set_state(AdminCreateGame.price)
    await message.answer(
        "💰 Укажите <b>стоимость участия</b> любым текстом "
        "(например <code>1500 ₽</code> или <code>Бесплатно для своих</code>).\n"
        "Если оставите поле условно пустым — отправьте <code>-</code> или слово «нет».",
        reply_markup=ReplyKeyboardRemove(),
    )


@ROUTER.message(AdminCreateGame.price)
async def admin_add_game_price(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().lower()
    price_text = ""
    if raw not in {"", "-", "нет", "no", "n/a"}:
        price_text = (message.text or "").strip()

    data = await state.get_data()
    game_id = await DB.add_game(
        title=data["title"],
        game_date_iso=data["game_date_iso"],
        direction=data["direction"],
        capacity=int(data["capacity"]),
        kind=GAME_KIND_MAFIA,
        price_text=price_text,
    )
    await state.clear()
    ph = html.escape(price_text) if price_text else "<i>не указана</i>"
    await send_main_menu_message(
        message,
        "<b>✅ Партия внесена в книгу</b>\n"
        f"<code>ID {game_id}</code>\n"
        f"{html.escape(data['title'])} · "
        f"{html.escape(to_user_datetime(data['game_date_iso']))} · "
        f"{html.escape(direction_to_human(data['direction']))} · "
        f"мест: <b>{data['capacity']}</b>\n"
        f"💰 стоимость: {ph}",
    )


@ROUTER.message(F.text.in_({BTN_ADMIN_NEW_MASTERCLASS, LEGACY_ADMIN_NEW_MASTERCLASS}))
async def admin_add_masterclass_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await message.answer(html_access_denied())
        return
    await state.set_state(AdminCreateMasterclass.title)
    await message.answer(
        "<b>➕ Новый мастер-класс</b>\nКак назовём событие?",
        reply_markup=ReplyKeyboardRemove(),
    )


@ROUTER.message(AdminCreateMasterclass.title)
async def admin_mc_title(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await state.clear()
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("⚠️ Название не может быть пустым.")
        return
    await state.update_data(title=title)
    await state.set_state(AdminCreateMasterclass.date)
    await message.answer(
        "📆 Укажите <b>дату и время</b> занятия:\n<code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n"
        "<i>Пример:</i> <code>25.05.2026 14:00</code>",
    )


@ROUTER.message(AdminCreateMasterclass.date)
async def admin_mc_date(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await state.clear()
        return
    raw = (message.text or "").strip()
    try:
        dt = datetime.strptime(raw, DATE_INPUT_FORMAT)
    except ValueError:
        await message.answer("⚠️ Формат не тот. Нужно: <code>25.05.2026 19:00</code>")
        return
    if dt <= datetime.now():
        await message.answer("⚠️ Дата должна быть <b>в будущем</b>.")
        return
    await state.update_data(game_date_iso=dt.strftime(DB_DATE_FORMAT))
    await state.set_state(AdminCreateMasterclass.capacity)
    await message.answer("🪑 Сколько <b>мест</b>? (число)")


@ROUTER.message(AdminCreateMasterclass.capacity)
async def admin_mc_capacity(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await state.clear()
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("⚠️ Введите целое число, например <code>20</code>.")
        return
    capacity = int(raw)
    if capacity <= 0:
        await message.answer("⚠️ Мест должно быть больше нуля.")
        return
    await state.update_data(capacity=capacity)
    await state.set_state(AdminCreateMasterclass.price)
    await message.answer(
        "💰 Укажите <b>стоимость участия</b> (или <code>-</code>, если не хотите указывать).",
    )


@ROUTER.message(AdminCreateMasterclass.price)
async def admin_mc_price(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await state.clear()
        return
    raw_ln = (message.text or "").strip().lower()
    price_text = ""
    if raw_ln not in {"", "-", "нет", "no", "n/a"}:
        price_text = (message.text or "").strip()

    data = await state.get_data()
    game_id = await DB.add_game(
        title=data["title"],
        game_date_iso=data["game_date_iso"],
        direction=MASTERCLASS_DIRECTION_STUB,
        capacity=int(data["capacity"]),
        kind=GAME_KIND_MASTERCLASS,
        price_text=price_text,
    )
    await state.clear()
    ph = html.escape(price_text) if price_text else "<i>не указана</i>"
    await send_main_menu_message(
        message,
        "<b>✅ Мастер-класс добавлен</b>\n"
        f"<code>ID {game_id}</code>\n"
        f"{html.escape(data['title'])} · "
        f"{html.escape(to_user_datetime(data['game_date_iso']))} · "
        f"мест: <b>{data['capacity']}</b>\n"
        f"💰 стоимость: {ph}",
    )


@ROUTER.message(F.text.in_({BTN_ADMIN_PHOTOS, LEGACY_ADMIN_PHOTOS}))
async def admin_upload_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await message.answer(html_access_denied())
        return

    games = await DB.get_past_games(now_iso())
    if not games:
        await message.answer("📜 <i>Архив пуст — не к чему прикрепить фото.</i>")
        return

    await state.clear()
    await message.answer(
        "<b>📷 Досье</b>\nВыберите прошлую партию:",
        reply_markup=admin_upload_pick_game_kb(games),
    )


@ROUTER.callback_query(F.data.startswith("upload_pick:"))
async def admin_upload_pick(call: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(call.from_user):
        await call.answer("🚫 Чужакам сюда нельзя.", show_alert=True)
        return
    game_id = int(call.data.split(":")[1])
    game = await DB.get_game(game_id)
    if not game:
        await call.answer("Игра не найдена.", show_alert=True)
        return

    await state.set_state(AdminUploadPhotos.waiting_photos)
    await state.update_data(game_id=game_id)
    await call.message.answer(
        f"📷 <b>Досье:</b> {html.escape(game['title'])}\n"
        f"<i>{html.escape(to_user_datetime(game['game_date']))}</i>\n\n"
        f"Снимки можно слать подряд, затем — «{BTN_FINISH_UPLOAD}».",
        disable_web_page_preview=True,
        reply_markup=finish_upload_kb(),
    )
    await call.answer()


@ROUTER.message(AdminUploadPhotos.waiting_photos, F.photo)
async def admin_save_photo(message: Message, state: FSMContext) -> None:
    if not await is_admin(message.from_user):
        await message.answer(html_access_denied())
        return
    data = await state.get_data()
    game_id = data.get("game_id")
    if not game_id:
        await message.answer("👆 Сначала выберите запись в архиве.")
        return

    file_id = message.photo[-1].file_id
    await DB.add_photo(game_id=game_id, file_id=file_id)
    await message.answer("📎 <i>Снимок в досье.</i>")


@ROUTER.message(AdminUploadPhotos.waiting_photos, F.text.in_({BTN_FINISH_UPLOAD, LEGACY_FINISH_UPLOAD}))
async def admin_finish_upload(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_main_menu_message(message, "✅ <b>Досье закрыто.</b>")


@ROUTER.message(AdminUploadPhotos.waiting_photos, F.text.in_({BTN_CANCEL, LEGACY_CANCEL}))
async def admin_cancel_any(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_main_menu_message(message, "<i>Шаг отменён.</i>")


@ROUTER.message(AdminUploadPhotos.waiting_photos)
async def admin_waiting_only_photo(message: Message) -> None:
    await message.answer(
        f"📷 Жду фото, «{BTN_FINISH_UPLOAD}» / «{LEGACY_FINISH_UPLOAD}» "
        f"или «{BTN_CANCEL}» / «{LEGACY_CANCEL}».",
        parse_mode=None,
    )


@ROUTER.message()
async def fallback(message: Message) -> None:
    await send_main_menu_message(
        message,
        "🎭 <b>За столом говорят только через меню.</b>\n"
        "Выберите кнопку снизу, <code>/menu</code> или <code>/start</code>.\n\n"
        "<i>Обновляли бота на сервере, а текст и кнопки как раньше? "
        "Нужен перезапуск процесса после выката (например</i> <code>docker compose up -d --build</code><i>). "
        "Проверка версии:</i> <code>/version</code>",
    )


async def main() -> None:
    global DB, SETTINGS
    SETTINGS = load_settings()
    DB = Database(SETTINGS.db_path)
    await DB.init()
    print(f"mafia-telegram-bot start MENU_BUILD_TAG={MENU_BUILD_TAG} db={SETTINGS.db_path!r}")

    bot = Bot(
        token=SETTINGS.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(ROUTER)
    dp.message.middleware(TrackUsersMiddleware())
    dp.callback_query.middleware(TrackUsersMiddleware())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
