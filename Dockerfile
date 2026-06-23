# Запуск 24/7 в облаке или на VPS (пока компьютер выключен — бот работает на сервере).
FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/data/opc_bot.db
ENV WEBAPP_PORT=8080

RUN mkdir -p /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py database.py main.py theme.py web_server.py ./
COPY webapp ./webapp/

EXPOSE 8080

CMD ["python", "main.py"]
