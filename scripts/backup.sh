#!/usr/bin/env bash
# Encrypted backup of PostgreSQL + private uploads, optionally copied to Google Drive via rclone.
#
# Required in the root .env (or the environment):
#   POSTGRES_USER, POSTGRES_DB, COMPOSE_PROJECT_NAME
#   BACKUP_PASSPHRASE_FILE  path to a file holding the encryption passphrase (chmod 600)
# Optional:
#   BACKUP_DIR              local directory (default: ./backups)
#   RCLONE_REMOTE           e.g. gdrive:sensoria-backups  (skipped when empty)
#   BACKUP_LOCAL_DAYS       keep local copies this long (default 7)
#   BACKUP_REMOTE_DAYS      keep remote copies this long (default 30)
#   BACKUP_PING_URL         GET after success (dead-man's-switch monitor)
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

: "${POSTGRES_USER:?}" "${POSTGRES_DB:?}" "${BACKUP_PASSPHRASE_FILE:?Ustaw BACKUP_PASSPHRASE_FILE}"
PROJECT="${COMPOSE_PROJECT_NAME:-sensoria}"
DIR="${BACKUP_DIR:-./backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$DIR"
[ -r "$BACKUP_PASSPHRASE_FILE" ] || { echo "Brak dostępu do $BACKUP_PASSPHRASE_FILE" >&2; exit 2; }

echo "[1/5] Zrzut bazy danych"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner > "$WORK/db.dump"
[ -s "$WORK/db.dump" ] || { echo "Pusty zrzut bazy — przerywam" >&2; exit 3; }

echo "[2/5] Archiwum prywatnych plików"
docker run --rm -v "${PROJECT}_uploads_data:/data:ro" -v "$WORK:/out" alpine:3.20 \
  tar -C /data -czf /out/uploads.tar.gz .

echo "[3/5] Pakowanie i szyfrowanie (AES-256)"
tar -C "$WORK" -cf "$WORK/bundle.tar" db.dump uploads.tar.gz
OUT="$DIR/sensoria-${STAMP}.tar.enc"
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -in "$WORK/bundle.tar" -out "$OUT" \
  -pass "file:$BACKUP_PASSPHRASE_FILE"
( cd "$DIR" && shasum -a 256 "$(basename "$OUT")" > "$(basename "$OUT").sha256" )

echo "[4/5] Kopia zdalna"
if [ -n "${RCLONE_REMOTE:-}" ]; then
  rclone copy "$OUT" "$RCLONE_REMOTE" --checksum
  rclone copy "$OUT.sha256" "$RCLONE_REMOTE" --checksum
  rclone delete "$RCLONE_REMOTE" --min-age "${BACKUP_REMOTE_DAYS:-30}d"
else
  echo "RCLONE_REMOTE nie jest ustawione — kopia tylko lokalna." >&2
fi

echo "[5/5] Czyszczenie starych kopii lokalnych"
find "$DIR" -name 'sensoria-*.tar.enc*' -mtime "+${BACKUP_LOCAL_DAYS:-7}" -delete

[ -n "${BACKUP_PING_URL:-}" ] && curl -fsS -m 10 --retry 3 "$BACKUP_PING_URL" > /dev/null || true
echo "OK: $OUT ($(du -h "$OUT" | cut -f1))"
