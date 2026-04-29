# Telegram-бот для набора игроков в Мафию

**Репозиторий:** https://github.com/grigorykis-hub/mafia-telegram-bot  

**Готовый Docker-образ (GHCR):** `ghcr.io/grigorykis-hub/mafia-telegram-bot:latest` — после первого успешного **Actions → Publish Docker image** пакет появится в GitHub → **Packages**. Чтобы тянуть образ на VPS без `docker login`, откройте пакет → **Package settings** → **Change package visibility** → **Public** (или выполните `docker login ghcr.io` с Personal Access Token, scope `read:packages`).

Бот позволяет:
- показывать в главном меню предстоящие игры, прошедшие игры и календарь;
- записывать участников на выбранную игру;
- показывать список уже записанных участников и свободные места;
- администратору добавлять новые игры;
- администратору загружать фото для прошедших игр.

## 1) Установка

```bash
git clone https://github.com/grigorykis-hub/mafia-telegram-bot.git
cd mafia-telegram-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Настройка

1. Скопируйте `.env.example` в `.env`
2. Заполните:
   - `BOT_TOKEN` — токен Telegram-бота (из BotFather)
   - `ADMIN_IDS` — числовой id через запятую (например `123,456`)
   - `ADMIN_USERNAMES` — логины Telegram **без** `@`, через запятую (например `Grigory_K`). Если указано, кнопка **«Админ-панель»** и права админа есть только у тех, чей id есть в `ADMIN_IDS` **и** username совпадает с одним из значений. Если переменную оставить пустой, проверяется только `ADMIN_IDS`.
   - `DB_PATH` — путь к sqlite. **Локально:** `mafia_bot.db`. **В Docker** задавать не обязательно: в образе уже `/data/mafia_bot.db` через `docker-compose.yml`.

## 3) Запуск

```bash
source .venv/bin/activate
python main.py
```

Или одной командой:

```bash
chmod +x run.sh
./run.sh
```

## Пользовательские сценарии

- **Предстоящие игры**: кнопки только для дат в будущем.
- **Карточка игры**: показывает количество участников, свободные места и список участников (имя + `@username`, если есть).
- **Прошедшие игры**: отображаются игры с датой в прошлом, можно открыть и посмотреть фото.
- **Календарь игр**: у каждой предстоящей игры — дата, время, **свободно X из Y мест**, название и тип стола.

## Админские сценарии

- Кнопка **Админ-панель** доступна главному админу из `.env` (`ADMIN_IDS` + при необходимости `ADMIN_USERNAMES`), а также пользователям, которых добавили через **«Добавить админа»** (по совпадению username в Telegram).
- **Добавить игру**:
  1. название;
  2. дата/время (`ДД.ММ.ГГГГ ЧЧ:ММ`);
  3. направление (`Взрослая`/`Детская`);
  4. количество мест.
- **Загрузить фото**:
  1. выбрать прошедшую игру;
  2. отправить фото (можно несколько);
  3. нажать `Завершить загрузку`.
- **Добавить админа**: ввод логина без `@`; человек получит админ-панель, когда откроет бота с аккаунта с этим username (учёт ведётся по логину в БД).
- **Сделать рассылку**: текст до 4096 символов — всем пользователям из базы «кто хотя раз писал боту / нажимал кнопки». В конце показывается статистика доставки.

## 4) Автономно 24/7 (обязательно вне вашего Mac)

**Почему «не работает само»:** Docker на домашнем компьютере останавливается вместе с Mac. Автономность — это **тот же бот, но на чужом сервере в интернете**, который не выключается ночью.

**Правило:** в один момент должен работать **только один** процесс с вашим `BOT_TOKEN` (иначе Telegram вернёт `Conflict`). Остановите бота на Mac, когда подняли облако/VPS.

---

### Вариант 1 — Railway (удобнее всего с GitHub)

1. Зайдите на [railway.app](https://railway.app), войдите через GitHub.
2. **New project** → **Deploy from GitHub repo** → выберите `grigorykis-hub/mafia-telegram-bot`.
3. Откройте сервис → **Variables** и добавьте:
   - `BOT_TOKEN`
   - `ADMIN_IDS`
   - `ADMIN_USERNAMES` (если используете у себя в `.env`)
   - `DB_PATH` = `/data/mafia_bot.db`
4. **Volumes** → **Add volume** → mount path: **`/data`** (иначе база пропадёт при каждом деплое).
5. Дождитесь деплоя, проверьте бота в Telegram.

В репозитории есть `railway.toml` (сборка из `Dockerfile`).

---

### Вариант 2 — VPS одной командой (образ с GHCR)

На **Ubuntu/Debian** с root (подставьте свои значения):

```bash
sudo BOT_TOKEN='ваш_токен' ADMIN_IDS='57004117' ADMIN_USERNAMES='Grigory_K' \
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/grigorykis-hub/mafia-telegram-bot/main/scripts/vps-bootstrap-ghcr.sh)"
```

Скрипт ставит Docker (если нет), создаёт `/opt/mafia-bot/.env`, тянет `docker-compose.image.example.yml` и запускает контейнер. Если `docker pull` падает — сделайте пакет **GHCR public** или `docker login ghcr.io`.

Локальная копия скрипта: `scripts/vps-bootstrap-ghcr.sh`.

---

### Вариант 3 — свой VPS вручную

**Из исходников:**  
`git clone https://github.com/grigorykis-hub/mafia-telegram-bot.git && cd mafia-telegram-bot` → `cp .env.example .env` → `docker compose up -d --build`. Логи: `docker compose logs -f` или `make logs`.

**Только готовый образ (GHCR):** в каталоге с `.env`:

```bash
export IMAGE=ghcr.io/grigorykis-hub/mafia-telegram-bot:latest
docker compose -f docker-compose.image.example.yml up -d
```

Обновление: `make pull-up-image` (после `export IMAGE=...`). Пакет на GitHub Container Registry сделайте **Public** или выполните `docker login ghcr.io`.

---

### Вариант 4 — Render.com

В корне `render.yaml` (worker + Docker + диск). **Бесплатный план Render не подходит для background workers** — нужен платный инстанс. Blueprint → репозиторий → задайте секреты `BOT_TOKEN`, `ADMIN_IDS`, `ADMIN_USERNAMES`.

---

### Вариант 5 — Fly.io

В корне `fly.toml`. Кратко: `fly auth login` → `fly apps create …` → `fly volumes create mafia_data --size 1` → `fly secrets set …` → `fly deploy`. Имя приложения в `fly.toml` должно совпадать с созданным.

---

## Примечания

- Прошедшие даты автоматически исчезают из кнопок **Предстоящие игры** и появляются в **Прошедшие игры**.
- База — SQLite, локально в файле `mafia_bot.db` (или в `DB_PATH`); в Docker по умолчанию — `/data/mafia_bot.db` на томе.
