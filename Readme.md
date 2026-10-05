# VSRALA

Сервис для велотренировок (аналог Strava): загрузка GPX/FIT, карта трека, лента активности.

## Docker Compose

Полный стек: nginx, backend (Django), PostgreSQL, Redis, Celery (worker + beat).

```bash
cp .env.example .env
docker compose up --build
```

Открыть: http://localhost

Создать пользователя:

```bash
docker compose exec backend python manage.py createsuperuser
```

## Запуск dev-сервера (без Docker)

Создаём venv (Python 3.9+):

```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

Сборка CSS (Tailwind):

```bash
npm install
npm run build:css
```

Для разработки стилей: `npm run watch:css`.

Redis (брокер Celery):

```bash
docker compose up -d redis
```

Миграции и сервер:

```bash
python manage.py migrate
python manage.py runserver
```

В отдельных терминалах — worker и beat для синхронизации Intervals.icu:

```bash
celery -A vsrala worker -l info
celery -A vsrala beat -l info
```

Тесты:

```bash
python manage.py test -v2
```

Создать пользователя:

```bash
python manage.py createsuperuser
```

После входа: **Загрузить** → файл `.gpx` или `.fit`.

Подключение Intervals.icu: **Настройки** → API-ключ из Developer Settings на intervals.icu.
При первом подключении скачиваются тренировки за последние 6 месяцев; далее — каждые 15 минут проверяются новые.
