#!/usr/bin/env bash
# Обновление сертификатов Let's Encrypt и reload nginx.
# Удобно повесить на cron, например: 0 3 * * 1 /path/to/vsrala/scripts/renew-certs.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

docker compose --profile ssl run --rm --entrypoint certbot certbot renew \
  --webroot \
  -w /var/www/certbot

docker compose exec nginx nginx -s reload
echo "Certificates renewed (if due) and nginx reloaded."
