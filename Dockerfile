FROM python:3.12-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN python -m venv venv && \
    . venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Создание директории для БД
RUN mkdir -p /app/data

# Запуск бота
CMD ["venv/bin/python", "-m", "bot.main"]
