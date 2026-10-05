#!/bin/sh
set -e

DOMAIN="${DOMAIN:-localhost}"
ENABLE_SSL="${ENABLE_SSL:-0}"
TEMPLATE_DIR="/etc/nginx/templates"
CONF_DIR="/etc/nginx/conf.d"

mkdir -p "$CONF_DIR"

if [ "$ENABLE_SSL" = "1" ]; then
  CERT_PATH="/etc/letsencrypt/live/${DOMAIN}"
  if [ ! -f "${CERT_PATH}/fullchain.pem" ] || [ ! -f "${CERT_PATH}/privkey.pem" ]; then
    echo "SSL enabled, but certificates for ${DOMAIN} are missing."
    echo "Run: ./scripts/init-letsencrypt.sh"
    exit 1
  fi
  echo "Configuring nginx with HTTPS for ${DOMAIN}"
  envsubst '${DOMAIN}' < "${TEMPLATE_DIR}/https.conf.template" > "${CONF_DIR}/default.conf"
else
  echo "Configuring nginx with HTTP for ${DOMAIN}"
  envsubst '${DOMAIN}' < "${TEMPLATE_DIR}/http.conf.template" > "${CONF_DIR}/default.conf"
fi

exec nginx -g 'daemon off;'
