#!/bin/sh
set -e

echo "Waiting for backend API..."
until curl -sf "http://backend:8000/health" >/dev/null 2>&1; do
  echo "  backend:8000 not ready yet, retrying in 2s..."
  sleep 2
done
echo "Backend is ready."

exec "$@"
