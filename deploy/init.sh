#!/bin/sh
set -eu

case "$SEED_DEMO_DATA" in
    true) : "${SEED_DEMO_PASSWORD:?Set SEED_DEMO_PASSWORD in .env or disable the demo seed}" ;;
    false) ;;
    *) echo 'SEED_DEMO_DATA must be true or false.' >&2; exit 1 ;;
esac

alembic upgrade head
if [ "$SEED_DEMO_DATA" = true ]; then
    exec python -m app.seed
fi
