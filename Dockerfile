# Запуск бота 24/7 в облаке или на VPS (пока компьютер выключен — бот работает на сервере).
FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONUNBUFFERED=1
# SQLite на отдельном томе, чтобы база не терялась при пересборке контейнера
ENV DB_PATH=/data/opc_bot.db

RUN mkdir -p /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py database.py main.py theme.py ./

CMD ["python", "main.py"]
