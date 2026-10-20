#!/usr/bin/env bash
# Production deploy on the VPS: pull, build, migrate, restart, verify. Rolls forward only —
# schema downgrades are never run automatically.
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f docker-compose.yml)

[ -f .env ] || { echo "Brak pliku .env" >&2; exit 2; }
echo "[1/6] Kopia zapasowa przed wdrożeniem"
[ -x scripts/backup.sh ] && scripts/backup.sh || echo "Pomijam kopię (brak scripts/backup.sh)" >&2
echo "[2/6] Pobranie kodu"
git fetch --prune origin
git merge --ff-only "origin/${DEPLOY_BRANCH:-main}"
echo "[3/6] Budowa obrazów"
"${COMPOSE[@]}" build --pull
echo "[4/6] Migracje bazy"
"${COMPOSE[@]}" up -d db
"${COMPOSE[@]}" run --rm --no-deps api alembic upgrade head
echo "[5/6] Uruchomienie"
"${COMPOSE[@]}" up -d
echo "[6/6] Kontrola zdrowia"
for _ in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" 2>/dev/null; then
    echo "OK — wdrożenie zakończone."
    exit 0
  fi
  sleep 3
done
echo "API nie odpowiada po wdrożeniu — sprawdź: docker compose logs api" >&2
exit 1
