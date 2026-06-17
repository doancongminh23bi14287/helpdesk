# CustomerHub

Customer portal and helpdesk system for hosting providers. CustomerHub gives your clients a single place to open support tickets, track subscriptions and invoices, and follow project progress — while your staff gets a unified queue with auto-assignment, SLA monitoring, and email-to-ticket piping.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, SQLAlchemy, Alembic |
| Database | MariaDB 10.11 |
| Cache / Queue | Redis 7, Celery |
| Real-time | Socket.IO |
| Frontend | React 18, Vite, Zustand, Tailwind CSS, Radix UI |
| Auth | JWT (access + refresh tokens), bcrypt |

---

## Quick Start (Development)

**Prerequisites:** Docker, Docker Compose v2, Python 3.12, Node.js 20

```bash
# 1. Clone and enter the repo
git clone <repo-url> customerhub && cd customerhub

# 2. Start database and Redis
docker compose up -d

# 3. Apply migrations
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# 4. Seed development data
python scripts/seed_base.py

# 5. Start the API (hot-reload)
uvicorn app.main:application --host 0.0.0.0 --port 8001 --reload &

# 6. Start the frontend (new terminal)
cd ../frontend
npm install && npm run dev
```

Frontend: http://localhost:5173
API docs: http://localhost:8001/docs

---

## Environment Variables

Copy `.env.prod.example` to `.env.prod` and fill in real values before deploying.

Key variables:

| Variable | Purpose |
|---|---|
| `ENV` | `development` or `production` |
| `DB_URL` | SQLAlchemy connection string |
| `JWT_SECRET` | Signing key — min 32 chars in production |
| `REDIS_HOST` / `REDIS_PORT` | Redis connection |
| `CORS_ORIGINS` | Comma-separated allowed origins (no `*` in production) |
| `FRONTEND_URL` | Public URL of the React app |
| `EMAIL_FEATURES_ENABLED` | Set `true` to enable IMAP polling and SMTP delivery |
| `FILES_ROOT` | Absolute path for uploaded file storage |

See [`.env.prod.example`](.env.prod.example) for the full list with comments.

---

## Production Deploy

See [`scripts/deploy.sh`](scripts/deploy.sh) for the full automated deploy flow:

1. `git pull`
2. `npm ci && npm run build` — build frontend, copy to `/var/www/customerhub`
3. `pip install -r requirements.txt` — sync Python deps
4. `alembic upgrade head` — run any pending migrations
5. `docker compose -f docker-compose.prod.yml up -d --build backend celery_worker celery_beat`
6. `nginx -s reload`

Nginx config lives in [`nginx/nginx.conf`](nginx/nginx.conf) — HTTP with SSL block commented and ready for Let's Encrypt.

```bash
# First-time server setup
cp .env.prod.example .env.prod
# Edit .env.prod with real values, then:
bash scripts/deploy.sh
```

---

## Default Credentials (Development Only)

These accounts are created by `python scripts/seed_base.py`. Do not use in production.

| Role | Email | Password |
|---|---|---|
| Admin | ticket@osd.vn | [YOUR_ADMIN_PASSWORD] |
| Staff | staff1@osd.vn | staff123 |
| Staff | staff2@osd.vn | staff123 |
| Customer | acm12112005@gmail.com | customer123 |
| Customer | minhdc.23bi14287@usth.edu.vn | [YOUR_ADMIN_PASSWORD] |

---

## API Docs

Interactive Swagger UI: http://localhost:8001/docs

Readiness check: http://localhost:8001/ready (reports DB, Redis, SMTP, email outbox status)

---

## Running Tests

```bash
# Backend
cd backend
source venv/bin/activate
pytest tests/ -v

# Frontend
cd frontend
npm test
npm run build
```

---

## Project Structure

```
customerhub/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers
│   │   ├── core/         # Security helpers
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # Business logic
│   │   ├── tasks/        # Celery tasks and beat schedule
│   │   ├── config.py     # Environment variable loading
│   │   ├── database.py   # Engine and session factory
│   │   └── main.py       # FastAPI app entrypoint
│   ├── alembic/          # Database migrations
│   ├── scripts/          # seed_base.py, deploy.sh, backup helpers
│   ├── tests/            # pytest test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/          # Axios API client modules
│   │   ├── components/   # Shared UI components
│   │   ├── hooks/        # Custom React hooks
│   │   ├── pages/        # Route-level page components
│   │   └── main.jsx      # React entrypoint
│   └── package.json
├── nginx/
│   └── nginx.conf        # Production Nginx config
├── docker-compose.yml       # Development stack
├── docker-compose.prod.yml  # Production stack (no dev mounts)
├── .env.prod.example        # Production env template
└── SCHEMA.sql               # Reference DDL (migrations are authoritative)
```

---

## License

MIT
