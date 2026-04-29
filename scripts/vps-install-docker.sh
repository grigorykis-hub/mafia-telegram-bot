#!/usr/bin/env bash
# Установка Docker + плагина compose на Ubuntu/Debian (один раз на чистом VPS).
set -euo pipefail

if command -v docker >/dev/null 2>&1; then
  echo "Docker уже установлен."
  docker --version
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
echo "Готово. Дальше: скопируйте папку бота на сервер, создайте .env, выполните:"
echo "  cd /путь/к/проекту && docker compose up -d --build"
