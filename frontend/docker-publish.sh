#!/bin/bash
set -euo pipefail

SPA_OUT="${SPA_OUT:-/out/spa}"
LANDING_OUT="${LANDING_OUT:-/out/landing}"

mkdir -p "$SPA_OUT" "$LANDING_OUT"
find "$SPA_OUT" -mindepth 1 -delete 2>/dev/null || true
find "$LANDING_OUT" -mindepth 1 -delete 2>/dev/null || true
cp -a /opt/spa/. "$SPA_OUT/"
cp -a /opt/landing/. "$LANDING_OUT/"
echo "Published SPA to $SPA_OUT and landing to $LANDING_OUT"
