#!/bin/sh
# Wrapper for the presentation stack: ./demo/compose.sh up -d --build | down -v | ps | logs -f api
cd "$(dirname "$0")/.." || exit 1
exec docker compose -p sensoria-demo --env-file demo/.env.demo \
  -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.demo.yml "$@"
