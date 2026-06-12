# Operations

## Local Development
- Backend local: `cd backend && source venv/bin/activate && uvicorn app.main:application --host 0.0.0.0 --port 8001 --reload`.
- Celery local: `celery -A app.tasks.celery_app worker --loglevel=info` and `celery -A app.tasks.celery_app beat --loglevel=info`.
- Frontend: `cd frontend && npm run dev`.
- Docker DB/Redis can remain running while backend runs locally.

## Deployment Checklist
- Set `ENV=production`.
- Set a unique `JWT_SECRET` of at least 32 characters.
- Set explicit `DATABASE_URL` or `DB_URL`.
- Set explicit Redis config.
- Set `CORS_ORIGINS` to trusted origins only.
- Configure SMTP/IMAP or set `EMAIL_FEATURES_ENABLED=false`.
- Run `alembic upgrade head`.
- Start backend, Celery worker, and Celery beat.
- Verify `/health`, `/ready`, and `/metrics`.

## Monitoring
- `/health`: process is alive.
- `/ready`: database, Redis, email outbox, and SMTP config checks.
- `/metrics`: Prometheus metrics including HTTP request count/duration and email outbox gauges.

## CI
- GitHub Actions workflow is in `.github/workflows/ci.yml`.
- Backend job runs pytest, Alembic upgrade, and backend Docker build.
- Frontend job runs Vitest and Vite build.
