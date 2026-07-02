#!/bin/sh
set -e

echo "[startup] Running database migrations..."
alembic upgrade head

echo "[startup] Running bootstrap seed..."
python -m app.seed

echo "[startup] Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
