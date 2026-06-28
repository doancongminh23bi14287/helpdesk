#!/bin/bash
set -e

echo "=== STARTING DEPLOY ==="
echo "Current dir: $(pwd)"
echo "Files: $(ls -la)"
echo "PORT: ${PORT:-NOT_SET}"
echo "PYTHONPATH: ${PYTHONPATH:-NOT_SET}"

echo "=== RUNNING MIGRATIONS ==="
alembic upgrade head

echo "=== MIGRATIONS DONE ==="
echo "=== STARTING UVICORN ==="
exec uvicorn app.main:application --host 0.0.0.0 --port "${PORT:-9000}" --log-level debug
