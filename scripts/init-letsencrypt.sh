#!/usr/bin/env bash
# Первичный выпуск Let's Encrypt сертификата и включение HTTPS.
# Требования: DNS A-запись DOMAIN уже указывает на этот сервер, порты 80/443 открыты.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Файл .env не найден. Скопируйте .env.example и заполните DOMAIN / CERTBOT_EMAIL."
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

DOMAIN="${DOMAIN:-}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
RSA_KEYSIZE="${RSA_KEYSIZE:-4096}"
STAGING="${STAGING:-0}"

if [[ -z "$DOMAIN" || "$DOMAIN" == "localhost" ]]; then
  echo "Задайте реальный DOMAIN в .env (не localhost)."
  exit 1
fi

if [[ -z "$CERTBOT_EMAIL" || "$CERTBOT_EMAIL" == "admin@example.com" ]]; then
  echo "Задайте реальный CERTBOT_EMAIL в .env."
  exit 1
fi

echo "==> Домен: ${DOMAIN}"
echo "==> Email: ${CERTBOT_EMAIL}"

# Временно поднимаем стек без SSL, чтобы ACME challenge был доступен.
export ENABLE_SSL=0
docker compose up -d --build

echo "==> Ждём готовности nginx..."
sleep 5

STAGING_ARG=()
if [[ "$STAGING" == "1" ]]; then
  echo "==> Режим staging (тестовые сертификаты Let's Encrypt)"
  STAGING_ARG=(--staging)
fi

echo "==> Запрос сертификата..."
docker compose --profile ssl run --rm --entrypoint certbot certbot certonly \
  --webroot \
  -w /var/www/certbot \
  "${STAGING_ARG[@]}" \
  --email "$CERTBOT_EMAIL" \
  -d "$DOMAIN" \
  --agree-tos \
  --no-eff-email \
  --rsa-key-size "$RSA_KEYSIZE" \
  --force-renewal

# Включаем SSL в .env
if grep -q '^ENABLE_SSL=' .env; then
  sed -i.bak 's/^ENABLE_SSL=.*/ENABLE_SSL=1/' .env
  rm -f .env.bak
else
  echo 'ENABLE_SSL=1' >> .env
fi

export ENABLE_SSL=1
echo "==> Перезапуск nginx с HTTPS..."
docker compose up -d nginx

echo "==> Готово: https://${DOMAIN}"
echo "Автообновление сертификатов: добавьте в cron:"
echo "  0 3 * * 1 cd ${ROOT_DIR} && ./scripts/renew-certs.sh"
