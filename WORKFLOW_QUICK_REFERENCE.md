# 📊 WorkDesk System - Quick Reference Index

## 📁 Files Created

1. **WORKFLOW_DIAGRAM.mmd** - Mermaid diagram (visual flowchart of all workflows)
2. **COMPLETE_WORKFLOW_DOCUMENTATION.md** - This comprehensive guide

---

## 🎯 13 Major Workflows (Quick Links)

### 1️⃣ System Setup & Onboarding
- **Entry**: Admin creates organization
- **Steps**: Create Org → Users → Contacts → Services → SLA Policies
- **Output**: Ready for operations
- **Key Tables**: `organizations`, `users`, `contacts`, `addresses`, `services`, `sla_policies`

### 2️⃣ Authentication & Session Management
- **Entry**: User login
- **Steps**: Credentials → Hash check → JWT tokens → Session storage → Token refresh
- **Security**: Bcrypt hashing, token rotation, reuse detection
- **Key Tables**: `user_sessions`, `login_history`

### 3️⃣ Organization & User Management
- **Entry**: Admin manages users
- **Access Control**: Role-scoped (Admin → All, Staff → Assigned orgs, Customer → Own org)
- **CRUD**: Create, read, update, soft-delete users
- **Key Tables**: `users`, `teams`, `team_members`, `staff_org_assignments`

### 4️⃣ Helpdesk - Ticket Management
- **Entry**: Customer creates ticket or email arrives
- **Workflow**: Create → Validate → Auto-assign → OPEN → WAITING → RESOLVED → CLOSED
- **SLA**: Priority-based deadlines with pause logic
- **Auto-Assignment**: Score-based (workload + skill + online status)
- **Key Tables**: `tickets`, `ticket_replies`, `ticket_activities`, `ticket_attachments`

### 5️⃣ Email Integration
- **Inbound**: IMAP polling (5-min intervals) → Parse → Thread → Create ticket or add reply
- **Outbound**: Agent sends reply → Queue in `email_outbox` → Celery drains with retry logic
- **Threading**: Message-ID mapping for conversation threads
- **Key Tables**: `email_log`, `email_threads`, `email_outbox`

### 6️⃣ Subscription & Billing
- **Workflow**: Create plan → Create subscription → Daily renewal check → Auto-generate invoice
- **Invoice States**: Draft → Pending → Paid/Overdue → Closed
- **Payment**: Record payment → Check if fully/partially paid
- **Key Tables**: `subscription_plans`, `subscriptions`, `invoices`, `invoice_payments`, `invoice_number_seq`

### 7️⃣ SEO Project & Task Management
- **Entry**: Admin/Staff creates project
- **Tasks**: Add tasks → Assign → Update status → Track progress
- **Progress**: Calculated from task completion (excludes cancelled)
- **Visibility**: Staff can hide internal notes from customers
- **Key Tables**: `projects`, `project_tasks`, `project_documents`

### 8️⃣ Real-Time Notifications
- **Sources**: Ticket assigned, SLA breached, payment due, etc.
- **Channels**: In-app (Socket.IO) + Email (outbox queue)
- **Priority Queue**: SLA emails first, then billing, then general
- **Key Tables**: `notifications`

### 9️⃣ File Management
- **Avatars**: Upload with validation (MIME, magic bytes, ≤2MB) → Store on disk → Metadata in DB
- **Attachments**: Upload to ticket (≤10MB) → Validate → Store → Serve with scoping check
- **Storage**: `FILES_ROOT/avatars/{user_id}` and `FILES_ROOT/tickets/{ticket_id}`
- **Key Tables**: `ticket_attachments`

### 🔟 Analytics & Reporting
- **Dashboard**: Ticket counts, SLA compliance, agent performance, revenue
- **Trends**: Time series (daily/weekly/monthly), status/priority breakdown
- **Operations**: `/health` (liveness), `/ready` (dependencies), `/metrics` (Prometheus)
- **Key Tables**: All tables (aggregated queries)

### 1️⃣1️⃣ Ticket Transfer & Escalation
- **Entry**: Agent requests to transfer ticket to another agent
- **States**: Pending → Approve/Reject → Execute → Activity logged
- **Notifications**: Both agents notified
- **Key Tables**: `ticket_transfer_requests`, `ticket_activities`

### 1️⃣2️⃣ Compliance & Security
- **RBAC**: Admin (platform) | Staff (org-scoped) | Customer (org-only)
- **Scoping**: Every query filtered by `org_id`
- **Tokens**: 30-min access, 7-day refresh, reuse detection
- **Audit**: Login history, ticket activities, role-based access logs
- **Validation**: Pydantic schemas, magic bytes, parameterized SQL
- **Key Tables**: `login_history`, `ticket_activities`, `user_sessions`

### 1️⃣3️⃣ System Operations
- **Backups**: Daily at 2 AM UTC (script: `scripts/backup_db.sh`)
- **Restore**: From local or S3 backup
- **Migrations**: Alembic (SQLAlchemy) for schema changes
- **Deployment**: Docker Compose + Nginx + Prometheus monitoring

---

## 🏗️ Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                      │
│      React 18 + Vite + Zustand + Tailwind + Radix UI      │
│                   (Role-aware routing)                     │
└────────────┬───────────────────────────────────────────────┘
             │
┌────────────▼───────────────────────────────────────────────┐
│                 NGINX REVERSE PROXY                        │
│           (SSL/TLS, Load balancing, WebSocket)            │
└────────────┬───────────────────────────────────────────────┘
             │
    ┌────────┴────────┬────────────┐
    │                 │            │
┌───▼────────┐  ┌────▼─────┐  ┌──▼────────┐
│  FastAPI   │  │  Celery  │  │  Celery  │
│  (App API) │  │  Worker  │  │   Beat   │
│ Socket.IO  │  │ (Tasks)  │  │(Schedule)│
└───┬────────┘  └────┬─────┘  └──┬───────┘
    │                │           │
    └────────────────┼───────────┘
                     │
         ┌───────────┼──────────┐
         │           │          │
    ┌────▼───┐  ┌───▼──┐  ┌───▼──┐
    │MariaDB │  │Redis │  │SMTP/ │
    │        │  │Cache │  │IMAP  │
    │ (Data) │  │ Pub  │  │(Ext.)│
    └────────┘  │ Sub  │  └──────┘
               └──────┘

Background: Celery tasks for:
  - Email polling (5-min)
  - SLA checking (5-min)
  - Subscription renewal (daily)
  - Outbox draining (5-min)
  - Invoice generation
  - Notification sending
```

---

## 📊 Data Model (31 Tables)

| Category | Tables |
|----------|--------|
| **Identity & Access** | `organizations`, `users`, `user_sessions`, `login_history`, `teams`, `team_members`, `staff_org_assignments` |
| **CRM** | `contacts`, `addresses` |
| **Helpdesk** | `tickets`, `ticket_replies`, `ticket_activities`, `ticket_attachments`, `ticket_transfer_requests`, `sla_policies` |
| **Email** | `email_log`, `email_threads`, `email_outbox` |
| **Catalog** | `service_categories`, `services`, `items` |
| **Subscriptions** | `subscription_plans`, `subscriptions` |
| **Billing** | `invoices`, `invoice_lines`, `invoice_payments`, `invoice_number_seq` |
| **Projects** | `projects`, `project_tasks`, `project_documents` |
| **Notifications** | `notifications` |

---

## 🔐 Security Features

- ✅ **RBAC**: Admin | Staff (org-scoped) | Customer (org-only)
- ✅ **Org Isolation**: Every query filtered by `org_id` at query layer
- ✅ **Password Hashing**: Bcrypt with 12 rounds
- ✅ **Token Security**: JWT HS256, 30-min access, 7-day refresh
- ✅ **Reuse Detection**: Refresh token replay → revoke all sessions
- ✅ **Session Tracking**: IP, User-Agent, JTI stored for anomaly detection
- ✅ **File Validation**: MIME type + magic bytes + size limit
- ✅ **SQL Injection Prevention**: SQLAlchemy ORM + parameterized queries
- ✅ **Audit Logging**: Login history, ticket activities, role-based access

---

## ⚙️ Key Celery Background Tasks

| Task | Interval | Purpose |
|------|----------|---------|
| `email_poller` | 5 min | Fetch & process inbound emails (IMAP) |
| `sla_checker` | 5 min | Monitor SLA deadlines, send notifications |
| `outbox_drain` | 5 min | Send queued emails with exponential backoff |
| `subscription_checker` | Daily @ 2 AM | Renew subscriptions, generate invoices |
| `invoice_expiry_checker` | Daily @ 3 AM | Send overdue reminders |
| `health_check` | 60 sec | System health metrics |

---

## 📡 Real-Time Communication

**Socket.IO + Redis Pub/Sub**:
1. Celery task publishes to Redis channel: `channel:notification`
2. FastAPI Socket.IO server subscribes to Redis
3. Server broadcasts to user room: `/user/{user_id}`
4. Frontend receives & updates UI

**Events**:
- ✅ Ticket assigned
- ✅ SLA approaching / breached
- ✅ Customer replied
- ✅ Task assigned
- ✅ Invoice due

---

## 🎯 API Endpoint Categories

### Auth
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/auth/me/avatar`
- `DELETE /api/auth/me/avatar`

### Organizations & Users
- `GET/POST /api/organizations`
- `GET/PUT /api/organizations/{id}`
- `GET /api/organizations/{id}/services`
- `GET/POST /api/users`
- `PUT /api/users/{id}`

### Tickets
- `GET/POST /api/tickets`
- `GET/PUT /api/tickets/{id}`
- `POST /api/tickets/{id}/replies`
- `POST /api/tickets/{id}/attachments`
- `GET /api/tickets/{id}/attachments`
- `POST /api/tickets/{id}/assign`
- `GET /api/tickets/{id}/sla`

### Subscriptions & Billing
- `GET/POST /api/subscriptions`
- `GET/POST /api/subscription_plans`
- `GET/POST /api/invoices`
- `POST /api/invoices/{id}/payments`

### Projects
- `GET/POST /api/projects`
- `GET/POST /api/projects/{id}/tasks`
- `PATCH /api/project-tasks/{id}/status`

### Notifications
- `GET /api/notifications`
- `PUT /api/notifications/{id}/read`

### Analytics
- `GET /api/analytics/summary`
- `GET /api/analytics/tickets`
- `GET /api/analytics/agents`

### System
- `GET /health`
- `GET /ready`
- `GET /metrics`

---

## 🚀 Quick Start Commands

### Development
```bash
# Start services
docker-compose up -d

# Run migrations
cd backend && alembic upgrade head

# Start backend
uvicorn app.main:application --host 0.0.0.0 --port 8001 --reload

# Start frontend
cd frontend && npm install && npm run dev
```

### Testing
```bash
# Backend tests
cd backend && pytest tests/ -v

# Frontend tests
cd frontend && npm test
```

### Production
```bash
# Start with prod compose
docker-compose -f docker-compose.prod.yml up -d

# Check health
curl http://localhost/health
curl http://localhost/ready
```

---

## 📈 Key Metrics to Monitor

- **Tickets**: Created/day, resolved/day, SLA compliance %
- **Agents**: Workload %, SLA compliance %, avg response time
- **Email**: Inbound/day, outbound success rate, outbox queue length
- **Billing**: Invoices created/month, payment success rate, overdue count
- **System**: DB latency, Redis latency, queue depth, error rate, uptime

---

## 🔗 Related Documentation

- `docs/ARCHITECTURE.md` - Detailed system architecture
- `docs/API_SCOPING.md` - API data isolation patterns
- `docs/SECURITY.md` - Security implementation details
- `docs/BACKUP.md` - Backup & restore procedures
- `docs/OPERATIONS.md` - Operations & troubleshooting

---

## 📞 Support

For questions about specific workflows, refer to:
1. **WORKFLOW_DIAGRAM.mmd** - Visual representation
2. **COMPLETE_WORKFLOW_DOCUMENTATION.md** - Detailed documentation (this file)
3. **Actual source code** in `/backend/app/` and `/frontend/src/`

---

**System Version**: 1.0 (June 2026)  
**Last Updated**: June 12, 2026  
**Status**: Complete & Production-Ready ✅
