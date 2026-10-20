#!/usr/bin/env bash
# Probe the public site and the deep health endpoint; exit 1 on any problem.
# Run from cron every few minutes, e.g.:  */5 * * * * /opt/sensoria/scripts/uptime-check.sh
# Optional: ALERT_WEBHOOK (POSTed the message), BASE_URL (default https://$DOMAIN).
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a
BASE="${BASE_URL:-https://${DOMAIN:-localhost}}"
fail=0
report() {
  echo "ALERT: $1" >&2
  [ -n "${ALERT_WEBHOOK:-}" ] && curl -fsS -m 10 -X POST -H 'Content-Type: text/plain' --data "SENSORIA: $1" "$ALERT_WEBHOOK" > /dev/null || true
  fail=1
}
code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$BASE/" || echo 000)
[ "$code" = "200" ] || report "strona główna zwróciła $code"
body=$(curl -s -m 15 -w '\n%{http_code}' "$BASE/api/health/deep" || echo -e '\n000')
code=$(echo "$body" | tail -n1)
[ "$code" = "200" ] || report "health/deep zwróciło $code: $(echo "$body" | head -n1 | cut -c1-200)"
exit $fail
