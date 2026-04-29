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
- **Календарь игр**: список дат и времени ближайших игр.

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

## 4) Автономно 24/7 (полный цикл)

Пока бот крутится только на вашем ПК, при выключении компьютера он **не отвечает**. Нужен **сервер в сети** и **один** запущенный экземпляр с вашим `BOT_TOKEN`.

### Шаг A — свой VPS (Ubuntu) + Docker Compose (рекомендуется)

1. Арендуйте VPS, подключитесь по SSH.
2. Один раз поставьте Docker (или выполните скрипт):
   ```bash
   chmod +x scripts/vps-install-docker.sh
   ./scripts/vps-install-docker.sh
   ```
3. Скопируйте папку на сервер, например: `git clone https://github.com/grigorykis-hub/mafia-telegram-bot.git && cd mafia-telegram-bot`.
4. На сервере: `cp .env.example .env` и заполните `BOT_TOKEN`, `ADMIN_IDS`, при необходимости `ADMIN_USERNAMES`.
5. Запуск в фоне + автоперезапуск после ребута:
   ```bash
   docker compose up -d --build
   ```
6. Логи: `docker compose logs -f` или `make logs`.
7. **Остановите** бота на домашнем ПК — иначе два процесса с одним токеном дадут ошибку `Conflict`.

База SQLite хранится в Docker-томе `mafia_sqlite` → файл `/data/mafia_bot.db` внутри контейнера.

### Шаг B — образ из GHCR (без сборки на сервере)

1. В репозитории уже есть workflow **Publish Docker image**; при каждом push в `main` (изменения в `Dockerfile`, `docker-compose*.yml`, `requirements.txt`, `**.py`) образ публикуется в **GHCR**.
2. Образ: **`ghcr.io/grigorykis-hub/mafia-telegram-bot:latest`**. Для `docker pull` без логина сделайте пакет **Public** (GitHub → **Packages** → пакет → **Package settings**) или один раз: `docker login ghcr.io` (PAT с `read:packages`).
3. На VPS: скопируйте `.env.example` в `.env`, заполните секреты, затем:
   ```bash
   export IMAGE=ghcr.io/grigorykis-hub/mafia-telegram-bot:latest
   docker compose -f docker-compose.image.example.yml up -d
   ```
   Обновление: `export IMAGE=ghcr.io/grigorykis-hub/mafia-telegram-bot:latest && make pull-up-image`.

### Шаг C — Render.com

В корне есть `render.yaml` (Background **Worker** + Docker + диск для SQLite). В панели Render создайте **Blueprint**, привяжите репозиторий, задайте секреты `BOT_TOKEN`, `ADMIN_IDS`, `ADMIN_USERNAMES`. Тариф `starter` в примере может быть платным — при необходимости поменяйте план в файле под ваш аккаунт.

### Шаг D — Fly.io

Файл `fly.toml` — шаблон. Команды: `fly launch`, `fly volumes create mafia_data --size 1`, `fly secrets set ...`, `fly deploy`. Подробности: https://fly.io/docs

---

**Кратко:** автономность = процесс на **чужом всегда включённом компьютере** (VPS/облако), не правка кода бота.

## Примечания

- Прошедшие даты автоматически исчезают из кнопок **Предстоящие игры** и появляются в **Прошедшие игры**.
- База — SQLite, локально в файле `mafia_bot.db` (или в `DB_PATH`); в Docker по умолчанию — `/data/mafia_bot.db` на томе.
