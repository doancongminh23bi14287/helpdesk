# Helpdesk Phase 1 — Foundation Design

**Date:** 2026-05-26  
**Scope:** Phase 1 of 4 (Foundation). No tickets, SLA, or email logic.  
**Source of truth:** `PLAN.md` (spec) + `SCHEMA.sql` (database) in repo root.

---

## 1. What We Are Building

A FastAPI backend foundation for a multi-organization B2B helpdesk system. Phase 1 delivers:

- Full Docker Compose stack (backend + MariaDB + Redis, fully containerized)
- All SQLAlchemy models matching SCHEMA.sql exactly
- JWT auth (login / refresh / me / logout)
- RBAC guards and org-scope query filters
- CRUD for Organizations and Users
- Seed data (admin, 2 staff, 3 client orgs × 2 services × 2 customers)

Phase 2 (tickets), Phase 3 (SLA/email/smart features), Phase 4 (frontend) are explicitly out of scope here.

---

## 2. Repository Layout

```
helpdesk-system/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, router registration
│   │   ├── config.py            # Settings via python-dotenv
│   │   ├── database.py          # SQLAlchemy engine + SessionLocal + Base
│   │   ├── seed.py              # Idempotent seed script
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── organization.py
│   │   │   ├── user.py
│   │   │   ├── team.py          # Team, TeamMember, StaffOrgAssignment
│   │   │   ├── service.py       # Service, ServiceCategory
│   │   │   ├── sla.py           # SlaPolicy
│   │   │   ├── ticket.py        # Ticket, TicketReply, TicketActivity
│   │   │   └── notification.py  # Notification, EmailLog
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── organization.py
│   │   │   └── user.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── organizations.py
│   │   │   └── users.py
│   │   └── core/
│   │       ├── security.py      # JWT create/decode, bcrypt
│   │       ├── deps.py          # get_current_user, require_admin, require_staff_or_admin
│   │       └── permissions.py   # org_scope_filter(query, user)
│   ├── alembic/
│   │   └── versions/            # baseline migration only
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                    # existing React/Vite (untouched in Phase 1)
├── docker-compose.yml
├── .env                         # gitignored; secrets for local dev
├── PLAN.md
└── SCHEMA.sql
```

---

## 3. Docker Compose (Full Containerize — Option B)

All three services run on a private bridge network `helpdesk-net`.

| Service | Image | Host port | Internal port | Notes |
|---------|-------|-----------|---------------|-------|
| `db` | mariadb:10.11 | **3307** | 3306 | Named volume `helpdesk_db_data`; utf8mb4 |
| `redis` | redis:7-alpine | **6380** | 6379 | |
| `backend` | `./backend` Dockerfile | **8001** | 8001 | depends_on db + redis; uvicorn |

Port choices avoid Frappe (MariaDB on 3306, Redis on 6379/13000/11000, FastAPI on 8000).

**DB_URL inside the container:**
```
mysql+pymysql://helpdesk:helpdesk_pass@db:3306/helpdesk_db
```

**DB_URL for local bare uvicorn:**
```
mysql+pymysql://helpdesk:helpdesk_pass@127.0.0.1:3307/helpdesk_db
```

Both are satisfied by a single `.env` with `DB_URL` swapped per context (container vs. host).

---

## 4. Database

- Database name: `helpdesk_db`, charset `utf8mb4`, collation `utf8mb4_unicode_ci`
- `SCHEMA.sql` is applied once to create all tables
- Alembic is initialized and the schema is **stamped as the baseline** (no auto-generated migration for existing tables — migrations are for future changes only)
- Tables: `organizations`, `users`, `teams`, `team_members`, `staff_org_assignments`, `service_categories`, `services`, `sla_policies`, `tickets`, `ticket_replies`, `ticket_activities`, `notifications`, `email_log`

---

## 5. SQLAlchemy Models

One file per logical group, all inheriting from a shared `Base` in `database.py`.  
Model class names are singular; table names are plural (matching SCHEMA.sql).

| File | Models |
|------|--------|
| `organization.py` | `Organization` |
| `user.py` | `User` |
| `team.py` | `Team`, `TeamMember`, `StaffOrgAssignment` |
| `service.py` | `ServiceCategory`, `Service` |
| `sla.py` | `SlaPolicy` |
| `ticket.py` | `Ticket`, `TicketReply`, `TicketActivity` |
| `notification.py` | `Notification`, `EmailLog` |

All models are imported in `models/__init__.py` so Alembic can discover them.

---

## 6. Auth

| Endpoint | Method | Auth required | Description |
|----------|--------|---------------|-------------|
| `/api/auth/login` | POST | No | `{email, password}` → `{access_token, refresh_token, token_type}` |
| `/api/auth/refresh` | POST | No | `{refresh_token}` → `{access_token}` |
| `/api/auth/me` | GET | Yes (access token) | `{id, email, full_name, role, org_id}` |
| `/api/auth/logout` | POST | Yes | Client-side drop only in Phase 1; Redis blacklist deferred to Phase 3 |

- Algorithm: HS256
- Access token TTL: 30 minutes
- Refresh token TTL: 7 days
- Password hashing: `passlib[bcrypt]` with `CryptContext(schemes=["bcrypt"])`

---

## 7. RBAC

### Guards (`core/deps.py`)

```python
get_current_user(token)            # raises 401 if missing/invalid/inactive
require_admin(user)                # raises 403 if role != admin
require_staff_or_admin(user)       # raises 403 if role == customer
```

### Org-scope filter (`core/permissions.py`)

```python
org_scope_filter(query, user) -> query
```

| Role | Filter applied |
|------|---------------|
| admin | none — sees everything |
| staff | `org_id IN (staff_org_assignments WHERE user_id = me)` |
| customer | `org_id = user.org_id` |

Every list endpoint calls this helper as its first query step.

---

## 8. Organizations & Users CRUD

### Organizations

| Method | Path | Guard | Notes |
|--------|------|-------|-------|
| GET | `/api/organizations` | authenticated | Scoped by role |
| POST | `/api/organizations` | admin | |
| GET | `/api/organizations/{id}` | authenticated | Scope-checked |
| PUT | `/api/organizations/{id}` | admin | |
| GET | `/api/organizations/{id}/services` | authenticated | All roles need this for ticket form dropdown |

### Users

| Method | Path | Guard | Notes |
|--------|------|-------|-------|
| GET | `/api/users` | admin | |
| POST | `/api/users` | admin | Password hashed on create |
| PUT | `/api/users/{id}` | admin | |

---

## 9. Seed Data

Script: `backend/app/seed.py`. Idempotent (safe to re-run).

| Entity | Count | Details |
|--------|-------|---------|
| PROVIDER org | 1 | From SCHEMA.sql seed; created if absent |
| Admin | 1 | `admin@osd.vn` / `admin123`, role=admin |
| Staff | 2 | `staff1@osd.vn`, `staff2@osd.vn` / `staff123` |
| Client orgs | 3 | Cong ty A (CTY-A), Cong ty B (CTY-B), Cong ty C (CTY-C) |
| Services per org | 2 | 1 saas + 1 hosting each = 6 total |
| Customers per org | 2 | e.g. `a1@cty-a.vn`, `a2@cty-a.vn` = 6 total |

---

## 10. CORS

`main.py` configures `CORSMiddleware` to allow:
- `http://localhost:5173` (React/Vite dev server)
- `http://localhost:8001` (self, for Swagger)

Methods: all. Headers: all. Credentials: true.

---

## 11. Key Decisions

| Decision | Rationale |
|----------|-----------|
| Full containerize (option B) | Isolates helpdesk_db from Frappe; self-contained for thesis demo |
| MariaDB on host port 3307 | Avoids conflict with Frappe on 3306 |
| Redis on host port 6380 | Avoids Frappe Redis on 6379/13000/11000 |
| Backend on port 8001 | Frappe occupies 8000 |
| Alembic baseline stamp | SCHEMA.sql is ground truth; Alembic manages only future changes |
| Stateless logout Phase 1 | Redis blacklist deferred to Phase 3 (not needed until multi-device/security audit) |
| Soft delete only | `is_deleted=1` on tickets; admin-only; no hard deletes anywhere |
| Status default = Open | Fixes the empty-status bug from email piping (enforced at model level) |
