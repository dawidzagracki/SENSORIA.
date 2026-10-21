#!/bin/sh
# One command: build + start the presentation stack and fill it with demo data.
# Fresh start:  ./demo/compose.sh down -v && ./demo/start.sh
set -e
cd "$(dirname "$0")/.."
./demo/compose.sh up -d --build
python3 demo/seed_demo.py
