#!/bin/bash
set -e
echo "=== STARTING CELERY WORKER + BEAT ==="
celery -A app.tasks.celery_app worker --beat --loglevel=info --concurrency=1 --pool=solo
