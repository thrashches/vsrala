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

Создать суперпользователя:

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
