# Удобные команды на сервере (из папки проекта, где есть .env)

.PHONY: up down logs pull-up pull-up-image

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

pull-up:
	docker compose pull && docker compose up -d

# Требует в окружении IMAGE=ghcr.io/владелец/репо:latest и файл .env
pull-up-image:
	docker compose -f docker-compose.image.example.yml pull && docker compose -f docker-compose.image.example.yml up -d
