# WorkDesk

Client Support & Workload Management System for service delivery teams.

## Features
- Multi-organisation B2B ticket management with org-level isolation
- Score-based auto-assignment (workload + skill + online status)
- Four-state SLA monitoring with Redis-backed deduplication
- Subscription billing with configurable tax rates
- SEO project and task management with customer-visible progress
- IMAP email-to-ticket piping with header threading
- Real-time notifications via Socket.IO + Redis pub/sub
- Role-aware React portal (Admin / Staff / Customer)
- Profile management with avatar upload (JPG / PNG / WebP, max 2 MB),
  fallback initials with selectable color, and local theme/language
  preferences

## Profile & Avatar
Users manage their own profile at `/profile` from the top-right avatar menu.

- `PATCH /api/auth/me` updates `full_name`, `phone`, `avatar_color` for the
  logged-in user only. `email`, `role`, and `org_id` are blocked at the schema
  layer so the endpoint cannot be used for privilege escalation.
- `POST /api/auth/me/avatar` accepts `multipart/form-data` with a single
  `file` field. Images are validated by declared MIME, magic bytes, and size
  (2 MB hard cap); SVG and unrelated content types are rejected.
- Files are stored under `FILES_ROOT/avatars/{user_id}/{uuid}.{ext}` — the
  user table stores only metadata (path, mime, size, updated_at). No raw
  bytes or base64 are persisted in the database.
- `DELETE /api/auth/me/avatar` removes the file (best-effort) and clears the
  metadata while preserving the user's chosen `avatar_color`.

## Stack
Backend: FastAPI · SQLAlchemy · Alembic · MariaDB · Redis · Celery
Frontend: React 18 · Vite · Zustand · Tailwind · Radix UI

## Quick Start (Development)

### Prerequisites
- Docker + Docker Compose
- Python 3.12
- Node.js 20

### Start
    cp .env.example .env
    # Edit .env with your values
    docker-compose up -d
    cd backend && source venv/bin/activate
    alembic upgrade head
    uvicorn app.main:application --host 0.0.0.0 --port 8001 --reload &
    cd ../frontend && npm install && npm run dev

### Email delivery
Outbound ticket emails are sent by the backend process. Invoice emails are queued
in `email_outbox` and require the Celery worker and beat services from
`docker-compose.yml`.

For Docker development, copy `backend/.env.docker.example` to
`backend/.env.docker` and set these values:

    SMTP_HOST=mail.example.com
    SMTP_PORT=465
    SMTP_USE_SSL=true
    SMTP_USER=support@example.com
    SMTP_PASS=your-smtp-password
    ADMIN_NOTIFICATION_EMAIL=admin@example.com

Check `/ready`: it reports `smtp_config` errors and stale `email_outbox` rows.

### Run Tests
    cd backend && source venv/bin/activate
    pytest tests/ -v

    cd ../frontend
    npm test
    npm run build

### CI
GitHub Actions workflow: `.github/workflows/ci.yml`.
It runs backend tests, Alembic upgrade, frontend tests/build, and backend Docker build.

### Monitoring
- `/health`: process liveness.
- `/ready`: database, Redis, email outbox, and SMTP config readiness.
- `/metrics`: Prometheus metrics.

### SEO Project & Task Management
- Admin/staff: `/projects` and `/projects/:id` manage SEO projects, tasks, assignment, status, internal notes, and customer visibility.
- Customer: `/projects` is read-only and shows only customer-visible projects/tasks.
- API endpoints:
  - `GET/POST /api/projects`
  - `GET/PATCH/DELETE /api/projects/{id}`
  - `GET/POST /api/projects/{id}/tasks`
  - `GET/PATCH/DELETE /api/project-tasks/{id}`
  - `PATCH /api/project-tasks/{id}/status`
- Progress rule: cancelled tasks are excluded; completed active tasks determine project progress.
- Current limitations: no timesheet, Gantt chart, payroll, or accounting-grade project costing.

### Operations Docs
- `docs/ARCHITECTURE.md`
- `docs/API_SCOPING.md`
- `docs/SECURITY.md`
- `docs/OPERATIONS.md`
- `docs/BACKUP.md`

## Production Deployment
See docker-compose.prod.yml and nginx/nginx.conf.
Set ENV=production in your .env — the app will refuse to
start with insecure default secrets.
Set `CORS_ORIGINS` to explicit trusted origins; wildcard CORS is rejected in production.

## Demo Accounts (Development Only)

> These credentials exist **only after running the seed script** against a local
> database. They are local-only fixtures — not production secrets. If a login
> fails it usually means the database has not been seeded yet.

Seed the local database from the backend venv:

```bash
cd /home/acm/helpdesk-system/backend
source venv/bin/activate
python -m app.seed
```

The script is idempotent — re-running it will not duplicate rows. It
creates the provider organisation, a Vietnamese client organisation
(Aloha Vietnam Travel), one admin, a few staff, two customer users, and
sample services / subscriptions / invoices used by the SEO Client &
Support Platform demo.

| Role     | Email              | Password    | Notes                              |
|----------|--------------------|-------------|------------------------------------|
| Admin    | admin@osd.vn       | admin123    | Full access (admin sidebar)        |
| Staff    | staff1@osd.vn      | staff123    | Assigned-org tickets and projects  |
| Customer | tan@aloha-vn.vn    | customer123 | Aloha Vietnam Travel customer view |

⚠️ These passwords are **for local development only**. Change them before
any production deployment and never commit real production secrets.
