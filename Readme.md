# VSRALA

Сервис для велотренировок (аналог Strava): загрузка GPX/FIT, карта трека, лента активности.

## Структура репозитория

```
backend/          # Django: API, admin, Celery
frontend/
  app/            # React SPA (Vite)
  landing/        # статический SEO-лендинг
nginx/            # reverse proxy / TLS
docker-compose.yml
scripts/          # Let's Encrypt helpers
```

## Архитектура

- **Лендинг** (`/`) — статическая HTML-страница (SEO)
- **Приложение** — React SPA: `/feed/`, `/activities/…`, `/people/…`, `/routes/…`, `/settings/`, `/login/`
- **Backend** — Django: `/api/`, `/admin/`, media/static
- **nginx** — маршрутизация, TLS, раздача SPA/landing

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Открыть: http://localhost — лендинг; приложение: http://localhost/feed/

Создать пользователя:

```bash
docker compose exec backend python manage.py createsuperuser
```

## Деплой на сервер (домен + HTTPS)

Домен задаётся только в `.env` на сервере — в репозиторий его класть не нужно.

### 1. DNS

Создайте A-запись (и при необходимости AAAA) на IP сервера:

```
your-domain.example  →  <IP сервера>
```

Дождитесь распространения DNS (`dig +short your-domain.example`).

### 2. Сервер

Нужны Docker и Docker Compose plugin. Откройте порты **80** и **443**.

```bash
git clone <url-репозитория> vsrala
cd vsrala
cp .env.example .env
```

Заполните `.env`:

```env
DOMAIN=your-domain.example
CERTBOT_EMAIL=you@example.com
ENABLE_SSL=0
ENABLE_LEGACY_UI=0

DEBUG=0
SECRET_KEY=<длинная-случайная-строка>
ALLOWED_HOSTS=your-domain.example,backend,nginx

POSTGRES_PASSWORD=<надёжный-пароль>
```

`CSRF_TRUSTED_ORIGINS` подставится из `DOMAIN` автоматически.

### 3. Первый запуск и сертификат

```bash
chmod +x scripts/init-letsencrypt.sh
./scripts/init-letsencrypt.sh
```

Скрипт:

1. Поднимет стек по HTTP
2. Получит сертификат Let's Encrypt (webroot)
3. Пропишет `ENABLE_SSL=1` в `.env`
4. Перезапустит nginx с HTTPS и включит автообновление сертификатов

Проверка: https://your-domain.example

Автообновление сертификатов (раз в неделю):

```bash
chmod +x scripts/renew-certs.sh
crontab -e
# добавить:
0 3 * * 1 cd /path/to/vsrala && ./scripts/renew-certs.sh >> /var/log/vsrala-certbot.log 2>&1
```

Для тестового прогона Let's Encrypt (без лимитов rate-limit):

```bash
STAGING=1 ./scripts/init-letsencrypt.sh
```

После успешного staging удалите тестовый сертификат и запустите скрипт без `STAGING`:

```bash
docker compose --profile ssl run --rm --entrypoint certbot certbot delete --cert-name "$DOMAIN"
./scripts/init-letsencrypt.sh
```

### 4. Смена домена

1. Новая DNS A-запись
2. В `.env`: новый `DOMAIN`, `ALLOWED_HOSTS`, `ENABLE_SSL=0`
3. Снова `./scripts/init-letsencrypt.sh`

### 5. Обычный перезапуск после обновления кода

```bash
git pull
docker compose up -d --build
```

## Запуск для разработки (без полного Docker UI)

### Backend

```bash
cd backend
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
cd ..
docker compose up -d database redis
cd backend
python manage.py migrate
python manage.py runserver
```

API: http://127.0.0.1:8000/api/  
По умолчанию `ENABLE_LEGACY_UI=1` — старые Django-шаблоны доступны с runserver (для тестов).

### Frontend (React SPA)

```bash
cd frontend/app
npm install   # Node ≥ 20
npm run dev
```

Vite: http://127.0.0.1:5173 — проксирует `/api` и `/media` на Django `:8000`.

Или из корня: `npm run dev:app`.

### Celery

```bash
cd backend
celery -A vsrala worker -l info
celery -A vsrala beat -l info
```

### Тесты

```bash
cd backend
python manage.py test -v2
```

После входа в SPA: **Загрузить** → файл `.gpx` или `.fit`.

Подключение Intervals.icu / Garmin: **Настройки** в приложении.
