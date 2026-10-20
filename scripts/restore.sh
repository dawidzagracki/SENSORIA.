#!/usr/bin/env bash
# Restore an encrypted backup. By default it only restores into a scratch database and verifies it;
# restoring over the live database needs --apply and CONFIRM_RESTORE=yes.
#
# Usage: scripts/restore.sh <plik.tar.enc | remote:sciezka/plik.tar.enc> [--apply]
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a
: "${POSTGRES_USER:?}" "${POSTGRES_DB:?}" "${BACKUP_PASSPHRASE_FILE:?}"
SRC="${1:?Podaj plik kopii}"
APPLY="${2:-}"
PROJECT="${COMPOSE_PROJECT_NAME:-sensoria}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [[ "$SRC" == *:* && ! -f "$SRC" ]]; then
  rclone copy "$SRC" "$WORK" && rclone copy "$SRC.sha256" "$WORK" 2>/dev/null || true
  FILE="$WORK/$(basename "$SRC")"
else
  FILE="$SRC"
  [ -f "$SRC.sha256" ] && cp "$SRC.sha256" "$WORK/"
fi
if [ -f "$FILE.sha256" ] || [ -f "$WORK/$(basename "$FILE").sha256" ]; then
  echo "Weryfikacja sumy kontrolnej…"
  ( cd "$(dirname "$FILE")" && shasum -a 256 -c "$(basename "$FILE").sha256" ) \
    || ( cd "$WORK" && shasum -a 256 -c "$(basename "$FILE").sha256" )
else
  echo "UWAGA: brak pliku .sha256 — pomijam weryfikację sumy." >&2
fi

echo "Odszyfrowanie…"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in "$FILE" -out "$WORK/bundle.tar" \
  -pass "file:$BACKUP_PASSPHRASE_FILE"
tar -C "$WORK" -xf "$WORK/bundle.tar"

SCRATCH="${POSTGRES_DB}_restore_check"
echo "Odtwarzanie do bazy kontrolnej $SCRATCH…"
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS \"$SCRATCH\"" -c "CREATE DATABASE \"$SCRATCH\""
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$SCRATCH" --no-owner --exit-on-error < "$WORK/db.dump"
echo "Kontrola: wersja migracji i liczba zamówień"
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$SCRATCH" -Atc \
  "SELECT 'alembic', version_num FROM alembic_version UNION ALL SELECT 'orders', count(*)::text FROM orders UNION ALL SELECT 'products', count(*)::text FROM products"

if [ "$APPLY" = "--apply" ]; then
  [ "${CONFIRM_RESTORE:-}" = "yes" ] || { echo "Aby nadpisać produkcję ustaw CONFIRM_RESTORE=yes" >&2; exit 4; }
  echo "NADPISUJĘ bazę $POSTGRES_DB i pliki prywatne…"
  docker compose stop api web
  docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE \"$POSTGRES_DB\"" -c "CREATE DATABASE \"$POSTGRES_DB\""
  docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error < "$WORK/db.dump"
  docker run --rm -v "${PROJECT}_uploads_data:/data" -v "$WORK:/in:ro" alpine:3.20 \
    sh -c 'rm -rf /data/* /data/.[!.]* 2>/dev/null; tar -C /data -xzf /in/uploads.tar.gz && chown -R 10001:10001 /data'
  docker compose start api web
  echo "Przywrócono. Sprawdź /api/health/deep."
else
  docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE \"$SCRATCH\"" > /dev/null
  echo "Kopia jest poprawna (baza kontrolna usunięta). Aby przywrócić produkcję użyj --apply."
fi
