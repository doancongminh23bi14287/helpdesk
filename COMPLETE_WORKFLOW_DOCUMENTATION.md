# 🎯 WorkDesk Helpdesk System - Complete Workflow Documentation

> **Complete Top-to-Bottom Use Case Analysis**  
> Created: June 12, 2026 | System: FastAPI + React + MariaDB + Redis + Celery

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [1️⃣ System Setup & Onboarding](#1️⃣-system-setup--onboarding)
3. [2️⃣ Authentication & Session Management](#2️⃣-authentication--session-management)
4. [3️⃣ Organization & User Management](#3️⃣-organization--user-management)
5. [4️⃣ Helpdesk - Ticket Management](#4️⃣-helpdesk---ticket-management)
6. [5️⃣ Email Integration](#5️⃣-email-integration)
7. [6️⃣ Subscription & Billing](#6️⃣-subscription--billing)
8. [7️⃣ SEO Project & Task Management](#7️⃣-seo-project--task-management)
9. [8️⃣ Real-Time Notifications](#8️⃣-real-time-notifications)
10. [9️⃣ File Management](#9️⃣-file-management)
11. [🔟 Analytics & Reporting](#🔟-analytics--reporting)
12. [1️⃣1️⃣ Ticket Transfer & Escalation](#1️⃣1️⃣-ticket-transfer--escalation)
13. [1️⃣2️⃣ Compliance & Security](#1️⃣2️⃣-compliance--security)
14. [1️⃣3️⃣ System Operations](#1️⃣3️⃣-system-operations)

---

## System Overview

### Core Principles
- **Multi-Tenant SaaS**: Complete data isolation per organization (`org_id`)
- **Role-Based Access**: Admin (platform-wide) | Staff (org-scoped) | Customer (org-only)
- **Async Operations**: Celery background tasks for email, billing, SLA monitoring
- **Real-Time Updates**: Socket.IO + Redis pub/sub for instant notifications
- **Reliability**: Email outbox pattern, token rotation, SLA pause logic

### Technology Stack
| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + Vite + Zustand + Tailwind + Radix UI |
| **Backend** | FastAPI + SQLAlchemy + Pydantic + Alembic |
| **Database** | MariaDB (primary) + Redis (cache, locks, pub/sub) |
| **Background** | Celery + Celery Beat (scheduled tasks) |
| **Realtime** | Socket.IO + Redis pub/sub bridge |
| **Infrastructure** | Docker Compose, Nginx, Prometheus, SMTP/IMAP |

### Data Model (31 Tables)
**Identity**: `organizations`, `users`, `user_sessions`, `login_history`, `teams`, `team_members`, `staff_org_assignments`  
**CRM**: `contacts`, `addresses`  
**Helpdesk**: `tickets`, `ticket_replies`, `ticket_activities`, `ticket_attachments`, `ticket_transfer_requests`, `sla_policies`  
**Email**: `email_log`, `email_threads`, `email_outbox`  
**Catalog**: `service_categories`, `services`, `items`, `subscription_plans`, `subscriptions`  
**Billing**: `invoices`, `invoice_lines`, `invoice_payments`, `invoice_number_seq`  
**Projects**: `projects`, `project_tasks`, `project_documents`  
**Notifications**: `notifications`

---

## 1️⃣ System Setup & Onboarding

### Flow Overview
```
Admin Creates Org → Users → Contacts/Addresses → Services → SLA Policies → Ready
```

### Step-by-Step Process

#### 1.1 Create Organization
**Endpoint**: `POST /api/organizations`  
**Auth**: Admin only

```json
{
  "name": "Acme Corp",
  "code": "ACME",
  "industry": "Technology",
  "country": "USA"
}
```

**What happens**:
- ✅ Create `Organization` record in MariaDB
- ✅ Set default `status = 'active'`
- ✅ All future records inherit this `org_id`

#### 1.2 Create Users
**Endpoint**: `POST /api/users`  
**Auth**: Admin only

```json
{
  "email": "admin@acme.com",
  "password": "SecurePass123!",
  "full_name": "Jane Admin",
  "role": "admin|staff|customer",
  "org_id": 1
}
```

**What happens**:
- ✅ Hash password with bcrypt
- ✅ Check email uniqueness (409 if duplicate)
- ✅ Create `user_sessions` record for first login
- ✅ Create default `avatar_color` (fallback if no avatar)

#### 1.3 Create Contacts & Addresses
**Endpoints**: `POST /api/contacts`, `POST /api/addresses`

```json
// Contact
{
  "org_id": 1,
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@acme.com",
  "phone": "+1-555-0100"
}

// Address
{
  "org_id": 1,
  "contact_id": 1,
  "type": "billing|shipping",
  "street": "123 Business Ave",
  "city": "New York"
}
```

**Use cases**:
- ✅ Send invoices to billing address
- ✅ Assign phone for support calls
- ✅ Track customer location

#### 1.4 Configure Services
**Endpoint**: `POST /api/services`  
**Auth**: Admin only

```json
{
  "org_id": 1,
  "category_id": 1,
  "name": "Web Hosting",
  "description": "Cloud hosting service",
  "renewal_period_days": 30
}
```

**Services enable**:
- ✅ Ticket routing (support tickets belong to services)
- ✅ Skill-based auto-assignment
- ✅ Billing tracking per service

#### 1.5 Setup SLA Policies
**Endpoint**: `PUT /api/sla/policies/{id}`  
**Auth**: Admin only

```json
{
  "priority": "HIGH",
  "response_hours": 2,
  "resolution_hours": 24
}
```

**Impact**:
- ✅ SLA deadlines calculated per ticket priority
- ✅ Breach monitoring every 5 minutes
- ✅ Agent notifications before/after breach

---

## 2️⃣ Authentication & Session Management

### Complete Auth Flow

```
User Input → Verify Credentials → Issue Tokens → Create Session → User Context
```

### Step 1: Login
**Endpoint**: `POST /api/auth/login`

```json
{
  "email": "admin@acme.com",
  "password": "SecurePass123!"
}
```

**Backend Process**:
1. Query user by email
2. Compare password hash (bcrypt verify)
3. **If valid**: Generate tokens
4. **If invalid**: Return 401 Unauthorized

### Step 2: Token Generation
**Algorithm**: HS256 (HMAC SHA-256)

```
access_token:
  - TTL: 30 minutes
  - Contains: user_id, role, org_id, email
  - Used for API requests

refresh_token:
  - TTL: 7 days
  - Single-use (revokes old on refresh)
  - Stored in database for reuse detection
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Step 3: Session Storage
**Table**: `user_sessions`

```sql
INSERT INTO user_sessions (
  user_id, refresh_token_hash, jti, ip_address, user_agent, created_at, expires_at
) VALUES (1, '$2b$12$...', 'uuid-v4', '192.168.1.100', 'Mozilla/5.0...', NOW(), NOW() + 7 DAYS);
```

**Security Features**:
- ✅ Token hash stored (not plaintext)
- ✅ IP & User-Agent captured (anomaly detection)
- ✅ JTI (unique token ID) for revocation

### Step 4: User Context Extraction
**Endpoint**: `GET /api/auth/me`

```json
{
  "id": 1,
  "email": "admin@acme.com",
  "full_name": "Jane Admin",
  "role": "admin",
  "org_id": 1,
  "avatar_url": "/files/avatars/1/uuid.jpg",
  "avatar_color": "bg-blue-500",
  "theme": "dark",
  "language": "en"
}
```

### Step 5: Token Refresh
**Endpoint**: `POST /api/auth/refresh`

```json
{
  "refresh_token": "eyJ..."
}
```

**Process**:
1. Verify refresh token signature
2. Look up session in DB
3. Check if already revoked (reuse detection)
4. **If replayed (revoked)**: Revoke ALL sessions (assumed theft)
5. **If valid**: Issue NEW access_token + NEW refresh_token
6. Revoke old refresh_token

### Step 6: Logout
**Endpoint**: `POST /api/auth/logout`  
**Client-side**: Drop token from localStorage

**Backend** (Phase 3+):
- ✅ Add to Redis blacklist
- ✅ Revoke all sessions for that user

### Step 7: Profile Management
**Avatar Upload**: `POST /api/auth/me/avatar`

```
Multipart form-data:
  file: <image file>

Validations:
  - MIME type check (image/jpeg, image/png, image/webp)
  - Magic bytes verification (libmagic)
  - Max size: 2 MB
  - Reject: SVG, EXE, scripts
```

**Storage**:
- File saved to: `FILES_ROOT/avatars/{user_id}/{uuid}.{ext}`
- Database stores only: `avatar_path`, `avatar_mime`, `avatar_size`, `updated_at`

**Avatar Fallback**:
- If no image: Display user initials + `avatar_color` (selectable)

---

## 3️⃣ Organization & User Management

### Role-Scoped Organization Access
**Endpoint**: `GET /api/organizations`

```
Admin:    View ALL organizations
Staff:    View organizations they're assigned to (via staff_org_assignments)
Customer: View only their org_id
```

### User CRUD (Admin Only)

#### List Users
**Endpoint**: `GET /api/users`
```json
[
  {
    "id": 1,
    "email": "admin@acme.com",
    "full_name": "Jane Admin",
    "role": "admin",
    "org_id": 1,
    "created_at": "2026-06-01T10:00:00Z"
  }
]
```

#### Create User
**Endpoint**: `POST /api/users`
- ✅ Admin sets `role` and `org_id`
- ✅ Password hashed immediately
- ✅ No password returned in response

#### Update User
**Endpoint**: `PUT /api/users/{id}`
- ✅ Admin can update role, org_id, name, phone
- ✅ Email change blocked (requires identity verification)

#### Soft Delete
**Endpoint**: `DELETE /api/users/{id}`
- ✅ Set `is_deleted = true` (data preserved)
- ✅ User cannot login

### Team Management
**Endpoints**: `POST /api/teams`, `POST /api/teams/{id}/members`

```json
{
  "org_id": 1,
  "name": "Support Team A",
  "description": "Handles Web Hosting tickets"
}
```

**Use Case**:
- ✅ Organize staff by expertise/region
- ✅ Skill-based auto-assignment queries team_members
- ✅ Workload calculated per team

### Staff-Org Assignments
**Table**: `staff_org_assignments`

```json
{
  "user_id": 5,
  "org_id": 1,
  "assigned_at": "2026-06-01T10:00:00Z"
}
```

**Purpose**:
- ✅ Staff can work for multiple orgs
- ✅ Queries filtered by this table
- ✅ Org-level isolation enforced

---

## 4️⃣ Helpdesk - Ticket Management

### Complete Ticket Lifecycle

```
Create → Validate → Auto-Assign → OPEN → Work → WAITING → Resolve → CLOSED
```

### 4.1 Ticket Creation

**Endpoint**: `POST /api/tickets`

```json
{
  "org_id": 1,
  "service_id": 5,
  "title": "Website down - urgent",
  "description": "Homepage not loading for past 30 mins",
  "priority": "HIGH|MEDIUM|LOW",
  "contact_id": 1,
  "type": "incident|request|renewal"
}
```

**Validation**:
- ✅ `org_id` scoped access check
- ✅ `service_id` belongs to org
- ✅ `contact_id` belongs to org
- ✅ `priority` in valid set

**Defaults**:
- Status: `OPEN`
- Assignee: `null` (awaiting auto-assignment)
- Created: Current timestamp
- SLA deadline: Calculated below

### 4.2 Auto-Assignment Engine

**Trigger**: On ticket creation  
**Lock**: Redis lock (prevents double-assignment)

```
Lock Key: locks:auto_assign:{org_id}
TTL: 10 seconds (must complete scoring within this time)
```

**Scoring Algorithm**:

```python
score = (
  agent_workload * 0.4 +          # % of max capacity
  (1 - skill_match) * 0.3 +       # 0 if skill match, 1 if no match
  (1 - is_online) * 0.3           # 0 if online, 1 if offline
)

# Lowest score wins (best availability + skill + online)
best_agent = agents.sort_by(score)[0]
```

**Input Data**:
- Active ticket count per agent → workload %
- Agent skills vs ticket service → skill match
- Agent `last_activity_at` → online status

**Output**:
- ✅ Store `assignee_id`
- ✅ Create `ticket_activity` record
- ✅ Send Socket.IO notification to agent
- ✅ In-app notification created

### 4.3 Ticket State Machine

#### 🟢 OPEN State
- **Entry**: Ticket created or reopened
- **Auto-assigned**: Awaiting agent response
- **SLA**: Count down from response_hours

**Allowed Transitions**:
- ➜ 🟡 WAITING (agent marks issue resolved)
- ➜ ⚫ CLOSED (skip to closed, rare)

#### 🟡 WAITING State
- **Entry**: Agent marks "waiting for customer"
- **SLA**: Paused (customer must respond)
- **Duration**: Agent sets pause_hours (default 48h)

**SLA Pause Logic**:
```python
# When status changes to WAITING
sla_paused_at = now()
pause_duration = customer_response_timeout

# When status changes back to OPEN
sla_paused_total_seconds += (now() - sla_paused_at).total_seconds()
deadline = original_deadline + sla_paused_total_seconds
```

**Allowed Transitions**:
- ➜ 🟢 OPEN (customer replies)
- ➜ 🔵 RESOLVED (agent confirms resolution)

#### 🔵 RESOLVED State
- **Entry**: Agent marks issue fixed + customer confirms
- **SLA**: Achieved (if within deadline)
- **Duration**: 7 days until auto-close

**Allowed Transitions**:
- ➜ 🟢 OPEN (customer reopens)
- ➜ ⚫ CLOSED (auto-close after 7 days)

#### ⚫ CLOSED State
- **Entry**: Auto-close or manual close
- **Final**: No further changes
- **Archive**: Data preserved forever

**Allowed Transitions**:
- ➜ 🟢 OPEN (reopen if customer comments)

### 4.4 SLA Monitoring

**Scheduler**: Celery Beat task runs every 5 minutes

```python
def sla_checker():
    # For each org with open tickets
    for org in organizations:
        for ticket in org.tickets.filter(status='OPEN'):
            
            # Read SLA policy
            sla_policy = ticket.service.sla_policy
            deadline = ticket.created_at + sla_policy.response_hours
            deadline += ticket.sla_paused_total_seconds
            
            # Check status
            time_remaining = deadline - now()
            
            if time_remaining < 0:
                # 🚨 BREACHED
                notify_admin(ticket, "SLA_BREACHED")
                ticket.sla_breached = True
                
            elif time_remaining < 2 hours:
                # 🔔 APPROACHING
                notify_agent(ticket, "SLA_APPROACHING", time_remaining)
                
            else:
                # ✅ OK - store % remaining
                pct = time_remaining / (sla_policy.response_hours * 3600)
                redis.set(f"sla:{ticket.id}:pct_remaining", pct)
```

**Notifications**:
- **2 hours before breach**: Agent notified
- **At breach time**: Admin + agent notified
- **Every breach**: Logged for analytics

### 4.5 Ticket Replies & Communication

**Endpoint**: `POST /api/tickets/{id}/replies`

```json
{
  "content": "Issue resolved - see attached logs",
  "is_internal": false,
  "attachments": [1, 2, 3]
}
```

**What happens**:
1. ✅ Create `TicketReply` record
2. ✅ If `is_internal=false`: Send email to customer
3. ✅ Add `ticket_reply_id` to `email_outbox` (for retry)
4. ✅ Create `ticket_activity` for audit
5. ✅ Auto-reopen if ticket was CLOSED

**Email Outbox Pattern**:
- Write to `email_outbox` table (transaction-safe)
- Separate Celery task drains outbox
- Retry with exponential backoff
- No email lost on app crash

---

## 5️⃣ Email Integration

### 5.1 Inbound Email (IMAP Piping)

**Scheduler**: Celery Beat, 5-minute interval

```python
def email_poller_task():
    imap = IMAP4_SSL(host='mail.example.com')
    imap.login(SMTP_USER, SMTP_PASS)
    imap.select('INBOX')
    
    status, data = imap.search(None, 'UNSEEN')
    
    for email_id in data[0].split():
        status, msg = imap.fetch(email_id, '(RFC822)')
        process_email(msg)
```

### 5.2 Email Parsing & Threading

**Headers Extracted**:
- `From`: Sender email
- `Subject`: Thread subject
- `Message-ID`: Unique identifier
- `In-Reply-To`: Links to previous message
- `References`: Full thread chain

**Threading Logic**:

```python
# Try to find existing ticket
reply_to_msg_id = msg['In-Reply-To']  # e.g., <ticket-12345@example.com>

existing_thread = db.query(EmailThread).filter(
    EmailThread.message_id == reply_to_msg_id
).first()

if existing_thread:
    # REPLY to existing ticket
    ticket = existing_thread.ticket
    create_ticket_reply(ticket, msg)
    email_log.ticket_id = ticket.id
    
else:
    # NEW ticket
    ticket = create_ticket(
        org_id=1,  # inferred from domain/config
        title=msg['Subject'],
        description=msg.body,
        contact_id=get_or_create_contact(msg['From']),
        type='incident'
    )
    email_log.ticket_id = ticket.id

# Log thread mapping
email_thread = EmailThread(
    message_id=msg['Message-ID'],
    ticket_id=ticket.id,
    received_at=now()
)
db.add(email_thread)
```

**Auto-Reopen Logic**:
```python
if ticket.status == 'CLOSED' and msg_from_customer:
    ticket.status = 'OPEN'  # Reopen
    notify_agent()
```

### 5.3 Email Logging

**Table**: `email_log`
```sql
INSERT INTO email_log (
  ticket_id, direction, from_addr, to_addr, subject,
  message_id, in_reply_to, body, received_at
) VALUES (...);
```

**Use Cases**:
- ✅ Full email audit trail
- ✅ Debug threading issues
- ✅ Compliance/GDPR retention

### 5.4 Outbound Email (SMTP via Celery)

**Trigger**: Agent sends reply, system sends notification

**Endpoint**: `POST /api/tickets/{id}/replies`

```python
# 1. Create reply record
reply = TicketReply(ticket_id=id, content=content, ...)
db.add(reply)
db.flush()

# 2. Queue for outbound
if not is_internal:
    email_outbox = EmailOutbox(
        ticket_id=id,
        recipient=ticket.contact.email,
        subject=f"Re: {ticket.title}",
        body=render_template(reply),
        attempts=0,
        next_retry_at=now(),
        status='pending'
    )
    db.add(email_outbox)

db.commit()
```

**Beat Task: Outbox Drain**

```python
def drain_outbox_task():
    pending = db.query(EmailOutbox).filter(
        EmailOutbox.status == 'pending',
        EmailOutbox.next_retry_at <= now(),
        EmailOutbox.attempts < 5
    ).all()
    
    for email in pending:
        try:
            send_smtp(
                to=email.recipient,
                subject=email.subject,
                body=email.body,
                from_addr='support@example.com'
            )
            email.status = 'sent'
            email.sent_at = now()
            
        except SMTPException as e:
            email.attempts += 1
            email.next_retry_at = now() + exp_backoff(email.attempts)
            # 60s, 300s, 900s, 1800s, 3600s
            
    db.commit()
```

**Guarantees**:
- ✅ No email lost on app crash (stored in DB)
- ✅ Automatic retry with backoff
- ✅ Max 5 attempts (then mark failed)

---

## 6️⃣ Subscription & Billing

### 6.1 Service Catalog

**Tables**: `items`, `service_categories`

```json
{
  "id": 1,
  "name": "Web Hosting - Premium",
  "unit_price": 99.99,
  "tax_rate": 0.10,
  "billing_period": "monthly",
  "renewal_period_days": 30
}
```

### 6.2 Subscription Plans

**Endpoint**: `POST /api/subscription_plans`

```json
{
  "org_id": 1,
  "name": "Starter Plan",
  "description": "For small businesses",
  "items": [1, 2, 3],
  "total_price": 299.99,
  "tax_rate": 0.10,
  "billing_period": "monthly",
  "renewal_period_days": 30,
  "auto_renew": true
}
```

### 6.3 Create Subscription

**Endpoint**: `POST /api/subscriptions`

```json
{
  "org_id": 1,
  "plan_id": 1,
  "billing_cycle_start": "2026-06-12",
  "due_days": 30,
  "tax_rate": 0.10,
  "status": "active"
}
```

**Storage**:
```sql
INSERT INTO subscriptions (
  org_id, plan_id, billing_cycle_start, 
  billing_cycle_end, due_days, tax_rate, 
  auto_renew, status, created_at
) VALUES (...);
```

### 6.4 Daily Subscription Renewal Task

**Scheduler**: Celery Beat, daily at 2 AM UTC

```python
def subscription_checker_task():
    for sub in db.query(Subscription).filter(
        Subscription.status == 'active'
    ):
        today = date.today()
        cycle_end = sub.billing_cycle_end
        
        # Check expiry warning (7 days before)
        if (cycle_end - today).days == 7:
            send_email(
                to=sub.org.primary_contact.email,
                template='subscription_expiry_warning',
                context={'subscription': sub, 'days': 7}
            )
        
        # Check renewal date
        if today >= cycle_end:
            # AUTO-RENEW
            new_start = cycle_end + timedelta(days=1)
            new_end = new_start + timedelta(days=sub.plan.renewal_period_days)
            
            sub.billing_cycle_start = new_start
            sub.billing_cycle_end = new_end
            
            # GENERATE INVOICE
            invoice = Invoice(
                org_id=sub.org_id,
                subscription_id=sub.id,
                status='draft',
                issue_date=today,
                due_date=today + timedelta(days=sub.due_days)
            )
            
            # Add invoice lines (from plan items)
            for item in sub.plan.items:
                invoice_line = InvoiceLine(
                    invoice_id=invoice.id,
                    item_id=item.id,
                    quantity=1,
                    unit_price=item.unit_price,
                    tax_rate=item.tax_rate
                )
                db.add(invoice_line)
            
            # Calculate total
            invoice.total_amount = sum(
                line.quantity * line.unit_price * (1 + line.tax_rate)
                for line in invoice.lines
            )
            
            db.add(sub)
            db.add(invoice)
            db.commit()
```

### 6.5 Invoice State Machine

#### 📄 Draft
- **Entry**: Auto-created by subscription_checker
- **Action**: Admin can edit/delete
- **Manual**: Send to customer or mark sent

#### 💰 Pending
- **Entry**: Admin marks "sent to customer"
- **Email**: Sent via outbox (retry logic)
- **Wait**: Customer payment

#### ✅ Paid
- **Entry**: Payment recorded (via API or manual)
- **Amount**: >= Invoice total
- **Archive**: Locked (no edits)

#### 🔴 Overdue
- **Entry**: Due date passed, no payment
- **Reminder**: Sent daily for 14 days
- **Action**: Escalate to collections

#### ❌ Cancelled
- **Entry**: Admin cancels
- **Reason**: Logged in notes

### 6.6 Payment Recording

**Endpoint**: `POST /api/invoices/{id}/payments`

```json
{
  "amount": 299.99,
  "payment_date": "2026-06-15",
  "payment_method": "bank_transfer|credit_card|check",
  "reference": "TXN-12345",
  "notes": "Customer called to confirm"
}
```

**Process**:
```python
payment = InvoicePayment(
    invoice_id=id,
    amount=amount,
    payment_date=payment_date,
    payment_method=payment_method,
    reference=reference,
    recorded_at=now(),
    recorded_by=current_user_id
)
db.add(payment)

# Check if fully paid
total_paid = sum(p.amount for p in invoice.payments)

if total_paid >= invoice.total_amount:
    invoice.status = 'paid'
    notify_customer("Payment received - thank you!")
    
elif total_paid > 0:
    invoice.status = 'partially_paid'
    remaining = invoice.total_amount - total_paid
    notify_customer(f"Partial payment received. Outstanding: ${remaining}")

db.commit()
```

### 6.7 Invoice Number Generation

**Table**: `invoice_number_seq`

```python
def generate_invoice_number(org_id):
    seq = db.query(InvoiceNumberSeq).filter(
        InvoiceNumberSeq.org_id == org_id
    ).with_for_update().first()  # Row lock
    
    if not seq:
        seq = InvoiceNumberSeq(org_id=org_id, next_number=1001)
        db.add(seq)
    
    invoice_number = f"INV-{org_id}-{seq.next_number}"
    seq.next_number += 1
    db.commit()
    
    return invoice_number
```

**Gap-Free**: Uses row-level locking to ensure no gaps in numbering

---

## 7️⃣ SEO Project & Task Management

### 7.1 Create Project

**Endpoint**: `POST /api/projects`

```json
{
  "org_id": 1,
  "name": "Q3 SEO Campaign",
  "description": "Optimize homepage, blog",
  "start_date": "2026-06-15",
  "end_date": "2026-09-15",
  "customer_visible": true,
  "status": "planned"
}
```

### 7.2 Add Tasks

**Endpoint**: `POST /api/projects/{id}/tasks`

```json
{
  "project_id": 1,
  "title": "Keyword research",
  "description": "Target 50 keywords",
  "assigned_to": 5,
  "status": "backlog",
  "due_date": "2026-06-30",
  "estimated_hours": 16,
  "priority": "HIGH"
}
```

**Status Values**:
- `backlog`: Not started
- `in_progress`: Being worked on
- `done`: Completed
- `cancelled`: Skipped

### 7.3 Progress Calculation

**Formula**:
```python
total_tasks = len(project.tasks.filter(status != 'cancelled'))
completed_tasks = len(project.tasks.filter(status == 'done'))

progress_pct = (completed_tasks / total_tasks) * 100
```

**Customer View**:
```json
{
  "id": 1,
  "name": "Q3 SEO Campaign",
  "progress": 35,  # % only, no task details
  "start_date": "2026-06-15",
  "end_date": "2026-09-15",
  "tasks": [
    {
      "title": "Keyword research",
      "status": "done",
      "due_date": "2026-06-30"
    }
  ]
}
```

### 7.4 Internal Notes (Staff Only)

**Endpoint**: `POST /api/project-tasks/{id}/notes`

```json
{
  "content": "Client asked for 10 more keywords - added to scope",
  "visible_to_customer": false
}
```

**Use Case**: Track changes, decisions, blockers without exposing to customer

---

## 8️⃣ Real-Time Notifications

### 8.1 Notification Creation

**Source Events**:
- ✅ Ticket assigned to agent
- ✅ Customer replied to ticket
- ✅ SLA approaching / breached
- ✅ Invoice due
- ✅ Subscription expiring
- ✅ Task assigned
- ✅ Project shared

**Database Record**:
```sql
INSERT INTO notifications (
  user_id, org_id, type, title, message,
  related_resource_type, related_resource_id,
  read_at, created_at
) VALUES (
  5, 1, 'ticket_assigned', 
  'New ticket assigned',
  'Ticket #1234: Website down',
  'ticket', 1234,
  NULL, NOW()
);
```

### 8.2 In-App Notifications (Socket.IO)

**Frontend Subscribe** (on login):
```javascript
socket.emit('join_room', `/user/${current_user.id}`);
```

**Backend Publish** (on event):
```python
# In sla_checker, auto_assign, etc.
sio.emit('notification', 
    data={
        'id': notification.id,
        'type': 'sla_approaching',
        'message': 'SLA deadline in 30 minutes',
        'ticket_id': 1234
    },
    to=f'/user/{agent.id}'
)
```

**Frontend Receive**:
```javascript
socket.on('notification', (data) => {
  addNotification(data);  // Update React state
  showToast(data.message);
});
```

### 8.3 Email Notifications (Priority Queue)

**Email Outbox Queue Priority**:
1. **SLA Breach** (critical)
2. **Payment/Invoice** (important)
3. **General** (normal)

**Queue Processing**:
```python
def send_notifications_task():
    # SLA emails first
    sla_emails = db.query(EmailOutbox).filter(
        EmailOutbox.type == 'sla_breach'
    ).order_by(EmailOutbox.created_at).limit(10)
    
    # Then billing
    billing_emails = db.query(EmailOutbox).filter(
        EmailOutbox.type == 'invoice'
    ).order_by(EmailOutbox.created_at).limit(10)
    
    # Then general
    general_emails = db.query(EmailOutbox).filter(
        EmailOutbox.type == 'general'
    ).order_by(EmailOutbox.created_at).limit(10)
```

### 8.4 Notification List API

**Endpoint**: `GET /api/notifications?limit=20&offset=0`

```json
{
  "total": 42,
  "unread": 5,
  "notifications": [
    {
      "id": 1,
      "type": "ticket_assigned",
      "title": "New ticket assigned",
      "message": "Ticket #1234: Website down",
      "read": false,
      "created_at": "2026-06-12T14:30:00Z",
      "related_resource": {
        "type": "ticket",
        "id": 1234,
        "url": "/tickets/1234"
      }
    }
  ]
}
```

**Mark as Read**: `PUT /api/notifications/{id}/read`

---

## 9️⃣ File Management

### 9.1 Avatar Upload

**Endpoint**: `POST /api/auth/me/avatar`

**Multipart Form**:
```
Content-Type: multipart/form-data
file: [binary image data]
```

**Validation Pipeline**:

1. **MIME Type Check**:
   - Expected: `image/jpeg`, `image/png`, `image/webp`
   - Reject: `image/svg+xml`, `application/x-executable`

2. **Magic Bytes Verification** (libmagic):
   - JPEG: `FF D8 FF E0`
   - PNG: `89 50 4E 47`
   - WebP: `52 49 46 46 ... 57 45 42 50`
   - Reject if mismatch (disguised malware)

3. **Size Check**:
   - Max: 2 MB (2097152 bytes)
   - Reject if larger

**Storage Process**:
```python
# 1. Generate unique filename
file_uuid = str(uuid.uuid4())
file_ext = mimetypes.guess_extension(file.content_type)
filename = f"{file_uuid}{file_ext}"

# 2. Save to disk
file_path = f"{FILES_ROOT}/avatars/{current_user.id}/{filename}"
os.makedirs(os.path.dirname(file_path), exist_ok=True)

with open(file_path, 'wb') as f:
    f.write(file.file.read())

# 3. Update user metadata (NOT base64 in DB)
current_user.avatar_path = file_path
current_user.avatar_mime = file.content_type
current_user.avatar_size = len(file.file.read())
current_user.avatar_updated_at = now()

db.commit()
```

**Response**:
```json
{
  "avatar_url": "/files/avatars/5/a1b2c3d4-e5f6-7890.jpg",
  "avatar_mime": "image/jpeg",
  "avatar_size": 102400
}
```

**Delete Avatar**: `DELETE /api/auth/me/avatar`
- ✅ Remove file from disk (best-effort)
- ✅ Clear `avatar_path`, `avatar_mime`, `avatar_size`
- ✅ Keep `avatar_color` for fallback initials

### 9.2 Ticket Attachments

**Endpoint**: `POST /api/tickets/{id}/attachments`

**Multipart Form**:
```
Content-Type: multipart/form-data
file: [binary file data]
```

**Validation**:
- ✅ Allowed types: PDF, JPEG, PNG, DOCX, XLSX
- ✅ Max size: 10 MB per file
- ✅ Scan for malware (optional, via ClamAV)

**Storage**:
```python
file_path = f"{FILES_ROOT}/tickets/{ticket.id}/{uuid}.{ext}"

attachment = TicketAttachment(
    ticket_reply_id=reply_id,
    file_path=file_path,
    original_filename=file.filename,
    mime_type=file.content_type,
    file_size=len(file.file.read()),
    uploaded_at=now()
)
db.add(attachment)
db.commit()
```

**Serve Attachments**:
**Endpoint**: `GET /api/tickets/{id}/attachments/{attachment_id}`
- ✅ Check user org_id matches ticket org_id
- ✅ Return file with correct Content-Type
- ✅ Log download for audit

---

## 🔟 Analytics & Reporting

### 10.1 Admin Dashboard Summary

**Endpoint**: `GET /api/analytics/summary`

```json
{
  "tickets": {
    "total_open": 42,
    "total_waiting": 8,
    "total_resolved": 120,
    "avg_resolution_hours": 18.5
  },
  "sla": {
    "compliance_pct": 94.2,
    "breached_this_month": 5,
    "approaching": 3
  },
  "agents": {
    "total": 10,
    "online": 7,
    "avg_workload_pct": 65
  },
  "revenue": {
    "invoices_sent": 25,
    "invoices_paid": 22,
    "outstanding": 14250.00,
    "overdue": 3200.00
  },
  "projects": {
    "active": 8,
    "completed_this_month": 2
  }
}
```

**Query Logic**:
```python
@app.get("/api/analytics/summary")
def get_analytics_summary(db, user: User = Depends(require_admin)):
    today = date.today()
    month_start = today.replace(day=1)
    
    # Ticket counts
    total_open = db.query(Ticket).filter(
        Ticket.status == 'OPEN'
    ).count()
    
    # SLA compliance
    breached = db.query(Ticket).filter(
        Ticket.sla_breached == True,
        Ticket.created_at >= month_start
    ).count()
    
    # Revenue
    paid_invoices = db.query(Invoice).filter(
        Invoice.status == 'paid',
        Invoice.paid_date >= month_start
    ).all()
    total_paid = sum(inv.total_amount for inv in paid_invoices)
    
    return {
        "tickets": {...},
        "sla": {...},
        "revenue": {"invoices_paid_amt": total_paid}
    }
```

### 10.2 Ticket Trends

**Endpoint**: `GET /api/analytics/tickets?period=weekly`

```json
{
  "period": "weekly",
  "data": [
    {
      "date": "2026-06-08",
      "created": 15,
      "resolved": 12,
      "breached": 1
    },
    {
      "date": "2026-06-15",
      "created": 18,
      "resolved": 16,
      "breached": 0
    }
  ],
  "status_breakdown": {
    "open": 42,
    "waiting": 8,
    "resolved": 5,
    "closed": 240
  },
  "priority_breakdown": {
    "HIGH": 12,
    "MEDIUM": 28,
    "LOW": 65
  }
}
```

### 10.3 Agent Performance

**Endpoint**: `GET /api/analytics/agents`

```json
{
  "agents": [
    {
      "id": 5,
      "name": "John Doe",
      "tickets_assigned": 42,
      "tickets_resolved": 38,
      "avg_resolution_hours": 16.2,
      "sla_compliance_pct": 96.4,
      "current_workload_pct": 72,
      "status": "online"
    }
  ]
}
```

### 10.4 System Health Checks

**Endpoint**: `GET /health`
```json
{
  "status": "ok",
  "timestamp": "2026-06-12T15:30:00Z"
}
```

**Endpoint**: `GET /ready`
```json
{
  "status": "ready",
  "checks": {
    "database": {
      "status": "ok",
      "latency_ms": 2
    },
    "redis": {
      "status": "ok",
      "latency_ms": 1
    },
    "smtp": {
      "status": "ok",
      "configured": true
    },
    "email_outbox": {
      "status": "ok",
      "pending_count": 5,
      "oldest_pending_age_seconds": 300
    }
  }
}
```

**Endpoint**: `GET /metrics`
- Prometheus metrics format
- Counters: tickets_created, emails_sent, invoices_generated
- Gauges: active_users, queue_length, db_connections
- Histograms: response_time, sla_breach_count

---

## 1️⃣1️⃣ Ticket Transfer & Escalation

### 11.1 Create Transfer Request

**Endpoint**: `POST /api/ticket-transfer-requests`

```json
{
  "ticket_id": 1234,
  "from_agent_id": 5,
  "to_agent_id": 7,
  "reason": "Need expert on SSL certs - assigning to Sarah",
  "priority": "HIGH"
}
```

**Storage**:
```sql
INSERT INTO ticket_transfer_requests (
  ticket_id, from_agent_id, to_agent_id,
  reason, status, created_at
) VALUES (...);
```

### 11.2 Approval Workflow

**Pending State**:
- ✅ Created and awaiting recipient approval
- ✅ Recipient notified via Socket.IO + email
- ✅ Ticket remains with current assignee

**Approve Request**: `PUT /api/ticket-transfer-requests/{id}`
```json
{
  "action": "approve"
}
```

**Process**:
```python
req = db.query(TicketTransferRequest).get(id)

if action == 'approve':
    # Update ticket
    req.ticket.assignee_id = req.to_agent_id
    req.status = 'accepted'
    
    # Create activity log
    activity = TicketActivity(
        ticket_id=req.ticket_id,
        type='transferred',
        changed_from=req.from_agent_id,
        changed_to=req.to_agent_id,
        created_by=current_user_id,
        notes=f"Transferred from {from_agent.name} to {to_agent.name}"
    )
    
    # Notify both agents
    notify_agent(req.from_agent_id, "Ticket transferred out")
    notify_agent(req.to_agent_id, "Ticket transferred to you")
    
elif action == 'reject':
    req.status = 'rejected'
    notify_agent(req.from_agent_id, "Transfer rejected")

db.commit()
```

---

## 1️⃣2️⃣ Compliance & Security

### 12.1 Role-Based Access Control (RBAC)

**Three Roles**:

| Role | Scope | Permissions |
|------|-------|-------------|
| **Admin** | Platform-wide | Create orgs, users; manage SLA; view all analytics |
| **Staff** | Assigned orgs | Handle tickets, create projects, view org analytics |
| **Customer** | Own org only | View own tickets, projects, invoices |

**Enforcement**: Every query uses `org_scope_filter()`

```python
# core/permissions.py
def org_scope_filter(query, model, user):
    if user.role == 'admin':
        return query  # Admin sees all
    
    if user.role == 'customer':
        return query.filter(model.org_id == user.org_id)
    
    if user.role == 'staff':
        # Only orgs assigned to this staff
        assigned_orgs = db.query(StaffOrgAssignment.org_id).filter(
            StaffOrgAssignment.user_id == user.id
        ).subquery()
        return query.filter(model.org_id.in_(assigned_orgs))
    
    return query
```

### 12.2 Token Rotation & Reuse Detection

**Refresh Token Process**:

1. **Old token**: `refresh_token_v1` stored in `user_sessions`
2. **Client sends**: `refresh_token_v1` to `/api/auth/refresh`
3. **Backend checks**: Is `refresh_token_v1` still valid?
   - **If Yes**: Issue `refresh_token_v2` + new `access_token`
   - **Revoke**: `refresh_token_v1` (mark as used)

4. **If client replays** `refresh_token_v1`:
   - Backend detects: "This token already used!"
   - **SECURITY ALERT**: Assume theft detected
   - **Action**: Revoke ALL sessions for that user
   - Force re-login

**Implementation**:
```python
@router.post("/api/auth/refresh")
def refresh_token(payload: RefreshRequest, db: Session):
    # 1. Verify JWT signature
    decoded = jwt.decode(payload.refresh_token, SECRET_KEY, HS256)
    user_id = decoded['sub']
    old_jti = decoded['jti']  # unique token ID
    
    # 2. Look up session
    session = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.jti == old_jti
    ).first()
    
    if not session:
        raise HTTPException(401, "Invalid refresh token")
    
    # 3. Check if already revoked (reuse!)
    if session.revoked_at is not None:
        # SECURITY: Revoke ALL sessions
        db.query(UserSession).filter(
            UserSession.user_id == user_id
        ).update({'revoked_at': now()})
        db.commit()
        raise HTTPException(401, "Token reuse detected - all sessions revoked")
    
    # 4. Issue new tokens
    new_jti = str(uuid.uuid4())
    new_access = create_access_token(user_id, new_jti)
    new_refresh = create_refresh_token(user_id, new_jti)
    
    # 5. Create new session + revoke old
    session.revoked_at = now()
    
    new_session = UserSession(
        user_id=user_id,
        jti=new_jti,
        refresh_token_hash=hash_token(new_refresh),
        ip_address=request.client.host,
        user_agent=request.headers.get('User-Agent')
    )
    db.add(new_session)
    db.commit()
    
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer"
    }
```

### 12.3 Password Hashing

**Algorithm**: Bcrypt (slow, resistant to GPU cracking)

```python
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Default: 12, can increase for future
)

# Hash on create
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# Verify on login
def verify_password(password: str, hash: str) -> bool:
    return pwd_context.verify(password, hash)
```

### 12.4 Audit Logging

**Table**: `login_history`
```sql
INSERT INTO login_history (
  user_id, ip_address, user_agent, 
  login_status, login_time
) VALUES (
  5, '192.168.1.100', 'Mozilla/5.0...',
  'success', NOW()
);
```

**Table**: `ticket_activities`
```sql
INSERT INTO ticket_activities (
  ticket_id, activity_type, old_value, new_value,
  created_by, created_at, notes
) VALUES (
  1234, 'status_changed', 'OPEN', 'WAITING',
  5, NOW(), 'Agent marked resolved'
);
```

### 12.5 Data Validation

**Layer 1: Pydantic Schemas**
```python
class TicketCreate(BaseModel):
    org_id: int
    service_id: int
    title: str = Field(..., min_length=5, max_length=200)
    priority: Literal['HIGH', 'MEDIUM', 'LOW']
    
    @validator('title')
    def title_no_sql(cls, v):
        if any(x in v.lower() for x in ['drop', 'delete', 'exec']):
            raise ValueError('Invalid title')
        return v
```

**Layer 2: Magic Bytes (Files)**
```python
import magic

def validate_file(file):
    mime = magic.from_buffer(file.read(), mime=True)
    if mime not in ALLOWED_MIMES:
        raise ValueError(f"File type {mime} not allowed")
    
    file.seek(0)
```

**Layer 3: SQLAlchemy (SQL Injection)**
- ✅ Parameterized queries (automatic with ORM)
- ✅ No string concatenation in SQL

---

## 1️⃣3️⃣ System Operations

### 13.1 Database Backups

**Script**: `scripts/backup_db.sh`

```bash
#!/bin/bash
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Full dump
mysqldump -u$MYSQL_USER -p$MYSQL_PASS \
  --single-transaction --quick --lock-tables=false \
  helpdesk > $BACKUP_DIR/helpdesk_$TIMESTAMP.sql

# Compress
gzip $BACKUP_DIR/helpdesk_$TIMESTAMP.sql

# Upload to S3
aws s3 cp $BACKUP_DIR/helpdesk_$TIMESTAMP.sql.gz \
  s3://my-backups/helpdesk/
```

**Schedule**: Daily at 2 AM UTC (via cron)

### 13.2 Restore from Backup

**Script**: `scripts/restore_db.sh`

```bash
#!/bin/bash
BACKUP_FILE=$1

# Download from S3 if needed
if [[ $BACKUP_FILE == s3://* ]]; then
  aws s3 cp $BACKUP_FILE ./backup.sql.gz
  BACKUP_FILE="./backup.sql.gz"
fi

# Decompress
gunzip $BACKUP_FILE

# Restore
mysql -u$MYSQL_USER -p$MYSQL_PASS helpdesk < ${BACKUP_FILE%.gz}
```

### 13.3 Database Migrations

**Tool**: Alembic (SQLAlchemy migration framework)

**Upgrade Head** (apply all pending migrations):
```bash
cd backend
alembic upgrade head
```

**Create Migration** (after schema change):
```bash
alembic revision --autogenerate -m "add customer_phone to contacts"
```

**Downgrade** (revert one migration):
```bash
alembic downgrade -1
```

### 13.4 Deployment

**Development**:
```bash
docker-compose up -d  # MariaDB, Redis, Celery, etc.
cd backend && uvicorn app.main:application --reload
cd frontend && npm run dev
```

**Production** (`docker-compose.prod.yml`):
```yaml
version: '3.9'

services:
  mariadb:
    image: mariadb:latest
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: helpdesk
    volumes:
      - mariadb_data:/var/lib/mysql

  redis:
    image: redis:latest
    volumes:
      - redis_data:/data

  backend:
    build: ./backend
    environment:
      ENV: production
      DATABASE_URL: mysql+pymysql://...
      REDIS_URL: redis://redis:6379
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery:
    build: ./backend
    command: celery -A app.tasks.celery_app worker -l info
    restart: always

  celery-beat:
    build: ./backend
    command: celery -A app.tasks.celery_app beat -l info
    restart: always

  frontend:
    build: ./frontend
    restart: always

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    restart: always

volumes:
  mariadb_data:
  redis_data:
```

**Environment Variables** (`backend/.env`):
```bash
ENV=production
DATABASE_URL=mysql+pymysql://user:pass@mariadb:3306/helpdesk
REDIS_URL=redis://redis:6379
SMTP_HOST=mail.example.com
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USER=support@example.com
SMTP_PASS=***
SECRET_KEY=***
JWT_ALGORITHM=HS256
```

### 13.5 Monitoring & Alerts

**Prometheus Metrics** (`/metrics`):
- Counters: `tickets_created_total`, `emails_sent_total`
- Gauges: `active_users`, `queue_length_outbox`
- Histograms: `http_request_duration_seconds`, `sla_breach_count`

**Grafana Dashboards**:
1. System Health (CPU, Memory, DB connections)
2. Ticket Pipeline (Created, Resolved, Breached)
3. Agent Performance (Workload, SLA compliance)
4. Revenue Tracking (Invoices, Payments, Outstanding)

**AlertManager Rules**:
- ✅ Database unavailable
- ✅ Redis queue backlog > 1000
- ✅ Email outbox > 500 pending
- ✅ SLA breach rate > 10%
- ✅ Error rate > 1%

---

## Summary Table: All Workflows

| # | Workflow | Trigger | Key Tables | Key Processes | End State |
|---|----------|---------|-----------|----------------|-----------|
| **1** | Org Setup | Admin | organizations, users | Create org → users → services → SLA | Ready |
| **2** | Auth | User login | user_sessions, login_history | Login → Hash check → Tokens → Session | Authenticated |
| **3** | Org Mgmt | Admin | users, teams, staff_org_assignments | CRUD users → Team mgmt → Assign staff | Users managed |
| **4** | Tickets | Customer/Email | tickets, ticket_replies, ticket_activities | Create → Auto-assign → OPEN → WAITING → CLOSED | Resolved |
| **5** | Email | System | email_log, email_threads, email_outbox | IMAP poll → Parse → Thread → Reply/Send | Email logged |
| **6** | Billing | System | subscriptions, invoices, invoice_payments | Renewal → Generate → Draft → Pending → Paid | Paid/Overdue |
| **7** | Projects | Staff | projects, project_tasks, project_documents | Create → Add tasks → Track progress → Complete | Completed |
| **8** | Notifications | Events | notifications | Event → Create notification → Socket.IO → UI | User notified |
| **9** | Files | User | ticket_attachments | Upload → Validate → Store → Serve | Stored |
| **10** | Analytics | Dashboard | All tables | Query → Aggregate → Report | Dashboard |
| **11** | Transfer | Staff | ticket_transfer_requests | Request → Pending → Approve → Reassign | Reassigned |
| **12** | Security | System | login_history, ticket_activities | Tokens → Reuse detection → Audit log | Secure |
| **13** | Operations | Admin | All tables | Backup → Restore → Migrate → Deploy | Running |

---

## 🎉 Complete System Flow

```
┌─────────────┐
│   Start     │
└──────┬──────┘
       │
       ├──→ System Setup (1)
       │     └──→ Auth (2)
       │           └──→ Org Mgmt (3)
       │                 ├──→ Tickets (4)
       │                 │     ├──→ Email (5)
       │                 │     └──→ Notifications (8)
       │                 ├──→ Billing (6)
       │                 │     └──→ Notifications (8)
       │                 ├──→ Projects (7)
       │                 ├──→ Files (9)
       │                 ├──→ Analytics (10)
       │                 ├──→ Transfer (11)
       │                 ├──→ Security (12)
       │                 └──→ Operations (13)
       │
       └──→ 🎉 Live System
            └──→ Continuous: Celery tasks, Socket.IO updates, API requests
```

---

## Key Design Patterns

| Pattern | Implementation | Benefit |
|---------|----------------|---------|
| **Email Outbox** | Write to DB, separate drain task | No email lost on app crash |
| **SLA Pause** | Accumulate pause time | Fair SLA calculation |
| **Redis Lock** | Distributed lock for auto-assign | No double-assignment |
| **Token Rotation** | New token on refresh | Reuse detection |
| **Org Scoping** | Every query filtered by org_id | Complete tenant isolation |
| **Celery Beat** | Scheduled background tasks | Billing, SLA, email processing |
| **Socket.IO Bridge** | Redis pub/sub → Socket.IO rooms | Real-time updates |
| **Role Permissions** | Dependency injection + scoping | RBAC enforcement |

---

## Infrastructure Components

```
┌──────────────────────────────────────────────────────┐
│                  Frontend (React)                    │
│  - React 18 + Vite + Zustand + Tailwind + Radix UI  │
│  - Real-time Socket.IO connection                    │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│          Nginx Reverse Proxy (Port 80/443)          │
│  - SSL/TLS termination                               │
│  - Load balancing                                    │
│  - WebSocket upgrade for Socket.IO                   │
└──────────────────────┬───────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐  ┌───▼──────┐  ┌───▼──────┐
│  FastAPI      │  │ Celery   │  │ Celery   │
│  (8 workers)  │  │ Worker   │  │ Beat     │
│  - API        │  │ - Tasks  │  │ - Sched  │
│  - Socket.IO  │  │ - Async  │  │ - Timers │
└───────┬──────┘  └───┬──────┘  └───┬──────┘
        │             │              │
        └─────────────┼──────────────┘
                      │
        ┌─────────────┼──────────────┐
        │             │              │
    ┌───▼───┐   ┌────▼────┐   ┌────▼────┐
    │MariaDB │   │  Redis  │   │  SMTP/  │
    │(M-M    │   │  Cache  │   │  IMAP   │
    │Repl)   │   │  Locks  │   │  (Ext.) │
    └────────┘   │  Pub/Sub│   └─────────┘
                 └────────┘
```

---

**Document Updated**: June 12, 2026  
**Version**: 1.0  
**Status**: Complete

