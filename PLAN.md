# Helpdesk & Client Management System — Build Plan

> Full rebuild. FastAPI + MariaDB + React. Multi-organization B2B helpdesk.
> This document is the single source of truth for the build. Build phase by phase.

---

## 1. Project Overview

A B2B helpdesk and client management platform for a company that provides services
(SaaS, web hosting, etc.) to **multiple client organizations**. Each client organization
has its own services, its own users, and its own tickets — fully isolated from other clients.

**Core principle:** Everything flows through **Tickets**. A ticket always belongs to an
**Organization** and references a **Service** of that organization.

### Goals
- Manage many client organizations from one system (multi-tenant by organization)
- Role-based access: Admin (full), Staff (team scope), Customer (own org only)
- Ticket lifecycle with SLA monitoring and auto-assignment
- Email piping: emails to ticket@osd.vn auto-create tickets
- Clean RESTful API, JWT auth, consistent design

### Non-goals (Future Work)
- Payment gateway integration / invoicing automation
- White-label per organization
- Public knowledge base / SEO content

---

## 2. Tech Stack

| Layer        | Technology                              |
|--------------|------------------------------------------|
| Frontend     | React 18 + Vite + Tailwind CSS           |
| Backend      | FastAPI + Python 3.12                     |
| ORM          | SQLAlchemy 2.x + Alembic (migrations)     |
| Database     | MariaDB 10.11                             |
| Auth         | JWT (access + refresh tokens), bcrypt     |
| Cache/Queue  | Redis + Celery (+ Celery Beat for cron)   |
| Email piping | IMAP poller as a Celery Beat task         |
| Realtime     | Socket.IO (python-socketio)               |
| Deploy       | Docker Compose                            |
| API docs     | Auto Swagger (FastAPI /docs)              |

---

## 3. Roles & Permissions

Three roles. A `Customer` must never see internal data (agents, SLA config, other orgs).

| Capability                    | Admin | Staff       | Customer    |
|-------------------------------|-------|-------------|-------------|
| Create ticket                 | yes   | yes         | yes         |
| View own tickets              | yes   | yes         | yes         |
| View all tickets              | yes   | team only   | no          |
| Reply to ticket               | yes   | yes         | yes         |
| Change status / priority      | yes   | yes         | no          |
| Assign agent                  | yes   | self only   | no          |
| See internal agent info       | yes   | yes         | no          |
| Manage users                  | yes   | no          | no          |
| Manage organizations          | yes   | no          | no          |
| Configure SLA                 | yes   | no          | no          |
| System-wide reports           | yes   | team only   | no          |
| Manage services/subscriptions | yes   | view only   | own only    |
| View billing / cost           | yes   | no          | own only    |

**Scoping rule (enforced in every query):**
- Customer: `WHERE org_id = current_user.org_id`
- Staff: `WHERE org_id IN (assigned orgs) OR assignee_id = current_user.id`
- Admin: no scope filter

---

## 4. Multi-Organization Data Model

```
Organization (đơn vị)
   |-- 1:N --> Services (gói dịch vụ: saas / hosting)
   |-- 1:N --> Users (admin / staff / customer)
   |-- 1:N --> Tickets

Ticket (trung tâm)
   |-- org_id      (FK -> Organization)  REQUIRED
   |-- service_id  (FK -> Service)       REQUIRED (which package the ticket is about)
   |-- raised_by   (FK -> User)
   |-- assignee_id (FK -> User, nullable)
   |-- 1:N --> Ticket Replies
   |-- 1:N --> Ticket Activities (audit log)
```

**Ticket creation form requires:**
1. Organization (đơn vị)
2. Service (gói dịch vụ — dropdown filtered by chosen organization)
3. Ticket type, priority, subject, description

When the user picks an Organization, the Service dropdown must filter to only that org's services.

---

## 5. Ticket Status Workflow (State Machine)

Five statuses. Default on creation is always **Open** (this fixes the empty-status bug
from email piping).

```
Open  --agent takes-->  In Progress  --agent replies-->  Waiting
                             |                               |
                             | agent resolves                | customer replies (reopen)
                             v                               v
                         Resolved  <----------------- In Progress
                             |
                             | after 3 days OR customer confirms
                             v
                          Closed
                             |
                             | reopen (admin / new reply)
                             v
                           Open
```

### Status definitions
| Status      | Meaning                          | Who sets it          |
|-------------|----------------------------------|----------------------|
| Open        | Newly created, unhandled         | System (on create)   |
| In Progress | Agent actively working           | Staff / Admin        |
| Waiting     | Agent replied, awaiting customer | Staff / Admin        |
| Resolved    | Solved, pending closure          | Staff / Admin        |
| Closed      | Fully closed                     | System / Admin       |

### Transition rules
- Email piping and portal creation -> always `Open`.
- Customer **cannot** set status directly. Customer reply on `Waiting`/`Resolved` -> auto `In Progress` (reopen).
- `Resolved` -> `Closed` automatically after 3 days (Celery Beat job) if no customer reply.
- Every status change is logged to `ticket_activities` (actor, from, to, timestamp).

---

## 6. Ticket CRUD Standard

**CREATE** — status default = `Open`. Required: org_id, service_id, subject. Source recorded (portal / email).

**READ** — always filtered by role scope (see section 3). Customer sees only own org.

**UPDATE** — Staff/Admin only for status/priority/assignee. Customer can only add replies.

**DELETE** — Admin only. Soft delete (`is_deleted = 1`), never hard delete.

---

## 7. API Endpoints (RESTful)

### Auth
```
POST   /api/auth/login          { email, password } -> { access_token, refresh_token }
POST   /api/auth/logout
POST   /api/auth/refresh        { refresh_token } -> { access_token }
GET    /api/auth/me             -> current user + role + org
```

### Organizations (admin)
```
GET    /api/organizations              list
POST   /api/organizations              create
GET    /api/organizations/{id}         detail
PUT    /api/organizations/{id}         update
GET    /api/organizations/{id}/services   services of this org (for ticket form dropdown)
```

### Tickets
```
GET    /api/tickets                    list (role-scoped, supports filters: status, priority, org_id)
POST   /api/tickets                    create (requires org_id, service_id, subject)
GET    /api/tickets/{id}               detail (with replies + activities)
PUT    /api/tickets/{id}               update status/priority/assignee (staff/admin)
DELETE /api/tickets/{id}               soft delete (admin)
POST   /api/tickets/{id}/replies       add reply (auto-reopen logic applies)
POST   /api/tickets/{id}/assign        assign agent (admin / staff-self)
GET    /api/tickets/{id}/sla           SLA status { state, percent_remaining, hours_remaining }
```

### Services
```
GET    /api/services                   my services (role-scoped)
GET    /api/services/categories        service categories list
GET    /api/services/{id}              detail
POST   /api/services/{id}/renew        request renewal -> creates a ticket type=renewal
POST   /api/services                   create (admin)
PUT    /api/services/{id}              update (admin)
```

### Users (admin)
```
GET    /api/users                      list
POST   /api/users                      create (assign role + org)
PUT    /api/users/{id}                 update
```

### SLA (admin)
```
GET    /api/sla/policies               list policies
PUT    /api/sla/policies/{id}          update thresholds
```

### Analytics
```
GET    /api/analytics/summary          dashboard summary (role-scoped)
GET    /api/analytics/tickets          trends, status breakdown, priority breakdown
GET    /api/analytics/agents           agent workload + SLA compliance (admin/staff)
```

### Notifications
```
GET    /api/notifications              my notifications
PUT    /api/notifications/{id}/read    mark read
```

**Naming consistency rule:** all paths are resource-based and plural. No RPC-style names like
`customer_portal_app.api.get_ticket_detail`. Frontend calls map 1:1 to these paths.

---

## 8. Email Piping (Pipemail)

When a customer emails **ticket@osd.vn**, the system pulls the email via IMAP and creates a ticket.

### IMAP config
```
Email:    ticket@osd.vn
Password: Minh@20042026
Server:   mail.osd.vn
Port:     993
SSL:      yes
Webmail:  https://mail.osd.vn/
```

### Flow
1. Celery Beat task runs every 1-2 minutes -> connect IMAP (mail.osd.vn:993 SSL).
2. Fetch UNSEEN emails from INBOX.
3. For each email:
   - Match sender email to a User -> resolve org_id and raised_by.
   - If sender unknown: create ticket under a default "Unassigned" org OR flag for admin.
   - Parse subject -> ticket subject; body -> description.
   - Create ticket with **status = Open** (never empty), source = "email".
   - If subject references an existing ticket id -> append as reply instead of new ticket.
   - Mark email as SEEN.
4. Log result to a processing table for audit.

### Critical fix
The old system created email tickets with empty status. **Always set status = "Open"** on email-created tickets.

---

## 9. Smart Features

### Auto-assignment Engine
On ticket create, if no assignee, compute best agent by weighted score:
- Workload (40%): fewer open tickets -> higher score
- Skill match (40%): agent resolved same ticket_type/priority before
- Online status (20%): active session in last 30 min
Assign highest-scoring agent. Log to ticket_activities.

### SLA Monitoring
- `sla_policies` defines response/resolution **hours** per priority.
- On ticket create, compute `response_by` and `resolution_by` timestamps.
- Celery Beat task every 5 min: check open tickets.
  - <= 20% time remaining -> notify assignee (amber)
  - breached -> notify admin/manager (red), escalate.

### SLA thresholds (default)
| Priority | Response | Resolution |
|----------|----------|------------|
| Urgent   | 15 min   | 2 h        |
| High     | 1 h      | 8 h        |
| Medium   | 4 h      | 24 h       |
| Low      | 8 h      | 72 h       |

---

## 10. Ticket Types

`ticket_type` enum: Bug, Incident, Question, Unspecified, Service SaaS, Service Hosting, Renewal

---

## 11. Project Structure

```
helpdesk-system/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry
│   │   ├── config.py               # settings (env)
│   │   ├── database.py             # SQLAlchemy engine/session
│   │   ├── models/                 # SQLAlchemy models
│   │   │   ├── organization.py
│   │   │   ├── user.py
│   │   │   ├── service.py
│   │   │   ├── ticket.py
│   │   │   ├── sla.py
│   │   │   └── notification.py
│   │   ├── schemas/                # Pydantic schemas
│   │   ├── api/                    # route handlers
│   │   │   ├── auth.py
│   │   │   ├── organizations.py
│   │   │   ├── tickets.py
│   │   │   ├── services.py
│   │   │   ├── users.py
│   │   │   ├── sla.py
│   │   │   └── analytics.py
│   │   ├── core/
│   │   │   ├── security.py         # JWT, password hashing
│   │   │   ├── deps.py             # dependencies (get_current_user, role guards)
│   │   │   └── permissions.py      # role-scope query filters
│   │   ├── services/               # business logic
│   │   │   ├── auto_assign.py
│   │   │   ├── sla_monitor.py
│   │   │   └── email_piping.py
│   │   └── tasks/                  # Celery tasks
│   │       ├── celery_app.py
│   │       ├── email_poller.py
│   │       └── sla_checker.py
│   ├── alembic/                    # migrations
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                       # existing React + Vite (adapt API calls)
│   └── src/...
│
├── docker-compose.yml
└── .env
```

---

## 12. Build Roadmap (4 months)

### Phase 1 — Foundation (Month 1)
- Project skeleton, Docker Compose (MariaDB, Redis, backend)
- SQLAlchemy models + Alembic migrations (all tables)
- JWT auth (login, refresh, me), bcrypt password hashing
- Role-based dependency guards + org-scope query filters
- CRUD: Organizations, Users
- Seed script: 1 admin, demo orgs, demo services, demo users

### Phase 2 — Ticket System (Month 2)
- Ticket CRUD with role scoping
- Replies + activities (audit log)
- Status state machine + transition rules
- Email piping (IMAP poller, Celery Beat) -> create tickets (status=Open)
- Ticket form: org + service dependent dropdown

### Phase 3 — Smart Features (Month 3)
- Auto-assignment engine
- SLA policies + monitor (Celery Beat) + escalation
- Notifications (Socket.IO realtime + persisted)
- Services management + renewal -> ticket

### Phase 4 — Frontend + Polish (Month 4)
- Adapt React frontend to new REST API (1:1 path mapping)
- 3 role-based views (admin / staff / customer)
- Analytics dashboard
- Testing (pytest backend, manual E2E)
- Docker deploy + thesis documentation

---

## 13. Key Decisions Log

- Status default = Open everywhere (fixes empty-status email bug).
- Multi-tenancy by organization (org_id on tickets, services, users).
- Ticket requires org_id + service_id at creation.
- Customer cannot change status; reply auto-reopens.
- Soft delete only.
- RESTful resource paths, no RPC-style endpoints.
- JWT instead of session cookies (stateless, easier for separate frontend).
- SLA stored in **hours** (DECIMAL) — business-friendly; Urgent response = 0.25h (15 min). Configurable later in admin UI.
- Default admin account: admin@osd.vn / admin123 (placeholder — change later in production).
