"""Тексты и подписи кнопок в духе «Мафии». Шрифт в Telegram задать нельзя — используем HTML и эмодзи."""

from __future__ import annotations

# Меняем при каждом значимом обновлении меню — по этой строке на /start видно, что деплой подтянул новый код.
MENU_BUILD_TAG = "hub-main-2026-05e"

# ——— Reply keyboard (точное совпадение в F.text) ———
BTN_MAFIA = "🎭 Мафия"
# Две подписи на главной: часть клиентов съедает длинный ряд — дублируем короче.
BTN_MASTERCLASS = "🎓 Мастер-классы"
BTN_MASTERCLASS_SHORT = "🎓 Мастер-класс"
BTN_CALENDAR = "📅 Календарь"
BTN_ADMIN = "🎩 Кабинет Дона"

BTN_UPCOMING = "🎴 Набор на стол"
BTN_PAST = "🌑 Архив партий"

BTN_BACK = "🏙 На площадь"
BTN_HOME_FROM_SECTION = BTN_BACK

BTN_ADMIN_NEW_GAME = "➕ Новая партия"
BTN_ADMIN_NEW_MASTERCLASS = "➕ Новый мастер-класс"
BTN_ADMIN_PHOTOS = "📷 Досье (фото)"
BTN_ADMIN_ADD_CAPO = "🤝 Вербовка"
BTN_ADMIN_BROADCAST = "📣 Созвать город"
BTN_ADMIN_NOTIFY_GAME = "📨 Рассылка участникам"

BTN_CANCEL = "✖️ Стоп"
BTN_FINISH_UPLOAD = "✅ Дело закрыто"

BTN_DIR_ADULT = "🎩 Взрослая"
BTN_DIR_CHILD = "🧒 Детская"

# Старые подписи до смены оформления (Telegram долго держит прошлую клавиатуру)
LEGACY_MAFIA = "Мафия"
LEGACY_MASTERCLASS = "Мастер-классы"
LEGACY_MASTERCLASS_ALT = "Мастер классы"
LEGACY_MASTERCLASS_SHORT = "Мастер класс"

LEGACY_UPCOMING = "Предстоящие игры"
LEGACY_PAST = "Прошедшие игры"
LEGACY_CALENDAR = "Календарь игр"
LEGACY_ADMIN = "Админ-панель"
LEGACY_BACK = "Назад в меню"

LEGACY_ADMIN_NEW_GAME = "Добавить игру"
LEGACY_ADMIN_NEW_MASTERCLASS = "Добавить мастер-класс"
LEGACY_ADMIN_PHOTOS = "Загрузить фото"
LEGACY_ADMIN_ADD_CAPO = "Добавить админа"
LEGACY_ADMIN_BROADCAST = "Сделать рассылку"

LEGACY_CANCEL = "Отмена"
LEGACY_FINISH_UPLOAD = "Завершить загрузку"
LEGACY_DIR_ADULT = "Взрослая"
LEGACY_DIR_CHILD = "Детская"


def is_cancel_text(text: str | None) -> bool:
    s = (text or "").strip()
    return s in (BTN_CANCEL, LEGACY_CANCEL)


def resolve_direction_choice(text: str | None) -> str | None:
    """'adult' | 'child' | None"""
    s = (text or "").strip()
    if s in (BTN_DIR_ADULT, LEGACY_DIR_ADULT):
        return "adult"
    if s in (BTN_DIR_CHILD, LEGACY_DIR_CHILD):
        return "child"
    return None


def divider() -> str:
    return "──────────────"


def html_banner() -> str:
    return (
        "<b>🎭 ЗА СТОЛОМ</b>\n"
        f"<code>{divider()}</code>\n"
        "<i>Город засыпает. Просыпается мафия…</i>"
    )


def html_welcome() -> str:
    return (
        f"{html_banner()}\n\n"
        "Добро пожаловать. Снизу кнопки: <b>Мафия</b>, <b>Мастер-класс</b>, <b>Календарь</b> "
        "(админам ещё <b>Кабинет Дона</b>).\n\n"
        "<i>Кнопки не обновились —</i> <code>/menu</code> <i>или</i> <code>/start</code>.\n"
        "<i>Отдельная проверка, что сервер обновлён:</i> <code>/version</code>\n\n"
        f"<b>Версия бота:</b> <code>{MENU_BUILD_TAG}</code>"
    )


def html_main_menu_hint() -> str:
    return "<b>🏙 Главная площадь</b>\n<i>Что делаем?</i>"


def html_pick_game() -> str:
    return "<b>🎴 Выберите партию</b>\n<code>— стол готов к набору —</code>"


def html_mafia_hub() -> str:
    return (
        "<b>🎭 Мафия</b>\n"
        "<code>──────────────</code>\n"
        "<i>Набор на стол или история городских игр.</i>"
    )


def html_masterclass_hub() -> str:
    return (
        "<b>🎓 Мастер-классы</b>\n"
        "<code>──────────────</code>\n"
        "<i>Выберите ближайшее занятие — запись как к столу.</i>"
    )


def html_no_masterclasses() -> str:
    return "🌙 <i>Мастер-классов пока не объявили — загляните позже.</i>"


def html_pick_masterclass() -> str:
    return "<b>🎓 Выберите мастер-класс</b>"


def html_no_upcoming() -> str:
    return "🌃 <i>Сейчас тихо: набора на стол нет.</i>"


def html_no_past() -> str:
    return "📜 <i>Архив пуст — прошлых записей ещё нет.</i>"


def html_pick_past() -> str:
    return "<b>🌑 Прошлая партия</b>\nВыберите запись из архива:"


def html_calendar_empty() -> str:
    return "📅 <i>В календаре пусто.</i>"


def html_access_denied() -> str:
    return "🚫 <b>Доступ закрыт.</b>\n<i>Сюда только свои.</i>"


def html_admin_panel() -> str:
    return (
        f"{html_banner()}\n\n"
        "<b>🎩 Кабинет Дона</b>\n"
        "<i>Распоряжайтесь.</i>"
    )


def format_calendar_header() -> str:
    return (
        "<b>📅 Календарь</b>\n"
        "<i>Игры мафии и мастер-классы; для каждого события — места, стоимость (если задана), тип.</i>"
    )


def format_game_card(
    *,
    title: str,
    lead_emoji: str = "🎴",
    when: str,
    type_line_html: str,
    count: int,
    free: int,
    price_line_html: str,
    participants_block: str,
) -> str:
    return (
        f"<b>{lead_emoji} {title}</b>\n"
        f"<code>{divider()}</code>\n"
        f"📆 <b>Когда:</b> {when}\n"
        f"{type_line_html}\n"
        f"💰 <b>Стоимость участия:</b> {price_line_html}\n"
        f"👥 <b>За столом:</b> {count}\n"
        f"🪑 <b>Свободно мест:</b> {free}\n\n"
        f"<b>Список записавшихся:</b>\n{participants_block}"
    )
