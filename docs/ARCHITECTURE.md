# CustomerHub Architecture

## Overview

CustomerHub (WorkDesk) is a multi-organization B2B client support and billing
platform for a service-delivery company managing many client organizations from
one system. It combines a helpdesk (tickets, SLA, email piping), subscription
billing (plans, invoices, payments), and SEO project delivery tracking behind a
role-aware portal (Admin / Staff / Customer). Every record is isolated per
organization; customers only ever see their own organization's data.

## Layer Map

| Layer | Responsibility | Key files |
|-------|----------------|-----------|
| Presentation | React 18 + Vite SPA; role-aware routing, lazy-loaded pages, shared Axios client with token refresh | `frontend/src/App.jsx`, `frontend/src/api/client.js`, `frontend/src/pages/` |
| Application | FastAPI routers (RBAC + scoping) and domain services (state transitions, billing, storage) | `backend/app/main.py`, `backend/app/api/`, `backend/app/services/`, `backend/app/core/scoping.py` |
| Background | Celery worker + beat: IMAP polling, SLA checks, invoice generation, outbox draining | `backend/app/tasks/celery_app.py`, `backend/app/tasks/` |
| Data | SQLAlchemy models + Alembic migrations on MariaDB; Redis for cache, locks, rate limits, pub/sub | `backend/app/models/`, `backend/alembic/`, `backend/app/core/redis_client.py` |
| Integration | SMTP/IMAP email, Socket.IO realtime, Prometheus metrics, local file storage | `backend/app/services/email_sender.py`, `backend/app/services/email_piping.py`, `backend/app/socketio_server.py`, `backend/app/services/storage.py` |

## Core Workflows

### A. Customer Onboarding & Service Activation
Admin creates an organization, its users, contacts, and addresses, then
activates services or subscriptions for it (the Setup Wizard chains these
steps). All later records (tickets, invoices, projects) hang off the `org_id`
created here. Key files: `backend/app/api/organizations.py`, `users.py`,
`services.py`, `subscriptions.py`; `frontend/src/pages/admin/SetupWizard.jsx`.

### B. Support & SLA Resolution
Tickets enter via the portal or IMAP email piping, always with status `Open`.
Auto-assignment scores staff by workload, skill match, and online status under
a Redis lock; SLA deadlines are computed from per-priority policies, paused
while `Waiting` on the customer, and checked by a 5-minute Celery beat task
that notifies before and after breach. Key files: `backend/app/api/tickets.py`,
`services/auto_assign.py`, `services/sla_monitor.py`, `tasks/sla_checker.py`,
`services/email_piping.py`.

### C. Subscription Renewal & Billing
Daily beat tasks roll subscription periods, warn about upcoming expiry, and
auto-generate draft invoices from each subscription's plan or item pricing.
Invoice emails are written to the `email_outbox` table and drained by a
separate task with retry/backoff, so billing commits never block on SMTP. Key
files: `backend/app/tasks/subscription_checker.py`, `tasks/invoice_tasks.py`,
`services/invoice_service.py`, `services/billing.py`, `services/outbox_service.py`.

### D. Management Monitoring
Admin/staff dashboards aggregate ticket volume, SLA compliance, agent
performance, and revenue. Operations endpoints (`/health`, `/ready`,
`/metrics`) expose liveness, dependency readiness (DB, Redis, SMTP, outbox
staleness), and Prometheus metrics. Key files:
`backend/app/api/analytics.py`, `backend/app/main.py`,
`frontend/src/pages/admin/AnalyticsDashboard.jsx`, `SystemStatusPage.jsx`,
`EmailOutboxPage.jsx`.

## Key Design Decisions

| Decision | Why | Trade-off |
|----------|-----|-----------|
| FastAPI + SQLAlchemy | Async-capable API with auto OpenAPI docs; typed request/response schemas via Pydantic | Smaller ecosystem than Django; auth/admin built by hand |
| Central scoping module (`core/scoping.py`) | One audited place for org-level row filtering; routers cannot drift into ad-hoc (insecure) filters | Every new resource must be wired through it |
| Email outbox pattern (`email_outbox` table) | Invoice emails survive SMTP outages; retry with exponential backoff; no email lost on rollback | Delivery is eventually-consistent (up to one beat interval late) |
| Redis lock for auto-assignment | Prevents two concurrent ticket creations in one org from double-assigning the same least-loaded agent | Brief serialization of assignment per org; lock TTL must outlive the scoring query |
| Refresh-token session rotation + reuse detection | Each refresh issues a new token and revokes the old; a replayed old token revokes all sessions (theft assumed) | More DB writes per refresh; clients must always store the newest token |
| SLA pause accumulator (`sla_paused_at` / `sla_paused_total_seconds`) | Time waiting on the customer doesn't count against the agent's SLA; deadlines shift by accumulated pause | Extra state transitions to maintain on every status change |
| Magic-byte upload validation (libmagic) | Declared MIME alone is spoofable; content sniffing blocks disguised executables/SVG | Allow-list must be maintained; `python-magic` native dependency |
| Redis pub/sub → Socket.IO bridge | Celery workers (separate processes) publish notifications that the API process forwards to user rooms | One more moving part; messages are fire-and-forget (no replay) |

## Data Model (31 tables)

**Identity & access**
- `organizations` — client companies; the tenancy root
- `users` — admin / staff / customer accounts (bcrypt, avatar metadata)
- `user_sessions` — refresh-token sessions (hash, jti, IP, UA, revocation)
- `login_history` — login audit trail
- `teams`, `team_members` — staff team grouping
- `staff_org_assignments` — which staff serve which organizations

**CRM**
- `contacts` — people at client organizations
- `addresses` — postal addresses per organization

**Helpdesk**
- `tickets` — core ticket with status, priority, SLA timestamps, pause accumulator
- `ticket_replies` — conversation thread (public + internal notes)
- `ticket_activities` — status/assignment audit log
- `ticket_attachments` — file metadata (bytes live on disk)
- `ticket_transfer_requests` — staff-to-staff handoff approvals
- `sla_policies` — response/resolution hours per priority

**Email**
- `email_log` — every inbound/outbound message processed
- `email_threads` — Message-ID threading map for email piping
- `email_outbox` — queued outbound emails with retry state

**Catalog & subscriptions**
- `service_categories`, `services` — services delivered per organization
- `items` — sellable items with pricing and tax rate
- `subscription_plans` — recurring plan definitions
- `subscriptions` — active org subscriptions (plan- or item-based)

**Billing**
- `invoices`, `invoice_lines` — invoice header and lines
- `invoice_payments` — recorded payments per invoice
- `invoice_number_seq` — gap-free invoice numbering

**Projects (SEO delivery)**
- `projects`, `project_tasks`, `project_documents` — org-scoped delivery work with customer-visible progress

**Notifications**
- `notifications` — per-user in-app notifications (mirrored to Socket.IO)

## Running the System

Development (details in [README.md](../README.md)):

```bash
docker-compose up -d                  # MariaDB, Redis, Celery worker/beat
cd backend && source venv/bin/activate
alembic upgrade head
uvicorn app.main:application --port 8001 --reload
cd ../frontend && npm install && npm run dev
```

Tests: `cd backend && pytest tests/ -v` and `cd frontend && npm test && npm run build`.

Production: `docker-compose.prod.yml` + `nginx/nginx.conf`; `ENV=production`
enforces secure config at startup (`backend/app/config.py`). See also
`docs/OPERATIONS.md`, `docs/SECURITY.md`, `docs/BACKUP.md`, `docs/API_SCOPING.md`.
