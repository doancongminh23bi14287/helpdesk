#!/bin/bash
set -e
cd ~/helpdesk-system/backend
source venv/bin/activate 2>/dev/null || true

# Kill stale processes
pkill -f "celery -A app.tasks" 2>/dev/null || true
sleep 1

# Celery worker + beat
celery -A app.tasks.celery_app worker --loglevel=warning --detach \
  --logfile=/tmp/celery-worker.log --pidfile=/tmp/celery-worker.pid
celery -A app.tasks.celery_app beat --loglevel=warning --detach \
  --logfile=/tmp/celery-beat.log --pidfile=/tmp/celery-beat.pid

echo "Celery worker and beat started"

# FastAPI (foreground)
uvicorn app.main:application --host 0.0.0.0 --port 8001 --reload
