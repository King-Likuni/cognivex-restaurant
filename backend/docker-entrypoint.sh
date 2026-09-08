#!/usr/bin/env sh
set -eu

command="${1:-api}"

run_migrations() {
  if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python -m alembic upgrade head
  fi
}

run_seed() {
  if [ "${RUN_INITIAL_DATA:-0}" = "1" ]; then
    python -m app.initial_data
  fi
}

if [ "$command" = "api" ]; then
  run_migrations
  run_seed
  exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}"
fi

if [ "$command" = "migrate" ]; then
  exec python -m alembic upgrade head
fi

if [ "$command" = "seed" ]; then
  exec python -m app.initial_data
fi

exec "$@"
