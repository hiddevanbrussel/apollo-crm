#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-true}" = "true" ]; then
  echo "Running bootstrap seed..."
  python -m app.seed
else
  echo "SEED_ON_START is false; skipping bootstrap."
fi

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
