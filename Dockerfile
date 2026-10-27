FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        zlib1g \
        libpq5 \
        postgresql-client \
        fonts-dejavu-core \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# Beat from main: official PyPI still pins Django<6.1; --no-deps keeps celery stable.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps \
        "django-celery-beat @ git+https://github.com/celery/django-celery-beat.git@c962a182c21d499f206866f0b37765989410065f"

COPY . .

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
