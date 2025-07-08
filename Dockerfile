FROM python:3.10-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем requirements.txt из корня
COPY requirements.txt /app/

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект в контейнер
COPY . /app/

# Переменные окружения
ENV PYTHONUNBUFFERED=1

# Порт приложения
EXPOSE 8000

# Команда запуска (пример)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
