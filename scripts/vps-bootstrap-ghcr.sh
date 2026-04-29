#!/usr/bin/env bash
# Автономный запуск на чистом VPS (Ubuntu/Debian) без клонирования репозитория:
#   sudo BOT_TOKEN='токен' ADMIN_IDS='123' bash vps-bootstrap-ghcr.sh
# Или заранее положите в /opt/mafia-bot/.env (chmod 600) и запустите скрипт без переменных.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/mafia-bot}"
IMAGE="${IMAGE:-ghcr.io/grigorykis-hub/mafia-telegram-bot:latest}"
COMPOSE_URL="${COMPOSE_URL:-https://raw.githubusercontent.com/grigorykis-hub/mafia-telegram-bot/main/docker-compose.image.example.yml}"

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Запустите от root: sudo BOT_TOKEN='…' ADMIN_IDS='…' $0"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Устанавливаю Docker…"
  curl -fsSL https://get.docker.com | sh
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

if [[ ! -f .env ]]; then
  if [[ -z "${BOT_TOKEN:-}" || -z "${ADMIN_IDS:-}" ]]; then
    echo "Нет файла $INSTALL_DIR/.env и не заданы BOT_TOKEN / ADMIN_IDS."
    echo "Пример: sudo BOT_TOKEN='…' ADMIN_IDS='123' ADMIN_USERNAMES='name' $0"
    exit 1
  fi
  umask 077
  {
    echo "BOT_TOKEN=${BOT_TOKEN}"
    echo "ADMIN_IDS=${ADMIN_IDS}"
    echo "ADMIN_USERNAMES=${ADMIN_USERNAMES:-}"
    echo "DB_PATH=/data/mafia_bot.db"
  } > .env
fi

echo "Качаю docker-compose с GitHub…"
curl -fsSL -o docker-compose.yml "$COMPOSE_URL"

export IMAGE
if ! docker compose pull; then
  echo "Если ошибка pull: образ GHCR приватный — выполните docker login ghcr.io (PAT с read:packages) или сделайте пакет Public."
  exit 1
fi

docker compose up -d
echo ""
echo "Готово. Сервис: $INSTALL_DIR"
echo "Логи:     cd $INSTALL_DIR && docker compose logs -f"
echo "Остановить домашний/Mac-бот с тем же токеном, иначе Conflict в Telegram."
