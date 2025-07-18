Демонстрация проекта (через ngrok, временный публичный доступ):
[https://39c0f3fd26cb.ngrok-free.app](https://20f6c32f4132.ngrok-free.app)

# Инструкция по запуску проекта `books_site`

Все команды выполнять из корневой папки проекта (там, где находится `manage.py`).
Перед запуском убедитесь, что активировано виртуальное окружение, установлены все зависимости из requirements.txt и выполнена миграция базы данных
 

## Сбор данных и заполнение бд

Для сбора данных с логированием выполняются два основных шага:
1) запуск Scrapy-паука books.py для парсинга книг:
```bash
cd scraper/parsing_books/spiders
scrapy crawl books
```
2) запуск скрипта reviews.py для парсинга отзывов:
```bash
python3 reviews.py
```
Запускайте эти команды из папки scraper/parsing_books/spiders, чтобы корректно работали импорты и настройки Scrapy.

Далее из корневой папки проекта на основе полученных данных (в формате json) происходит создание записей в базе данных: 
```bash
python3 import_books.py
python3 import_reviews.py
python3 user_preferences.py
```

Для удобства и автоматизации эти шаги объединены в кастомную Django-команду parsing, которую можно запускать из корня проекта:
```bash
python manage.py parsing
```

## Индексация поисковых запросов

Для обновления поискового индекса используется Django Haystack, чтобы пересоздать индекс и обновить данные для поиска, выполните команду:
```bash
python manage.py rebuild_index
```

## Создание рекомендаций
Сгенерируйте рекомендательные модели для пользователей с помощью:
```bash
python manage.py generate_recommendations
```

## Расчет метрик
Выполните подсчёт метрик:
```bash
python manage.py calculate_metrics
```

## Запуск сервер разработки
Запустите локальный сервер Django:
```bash
python manage.py runserver
```
