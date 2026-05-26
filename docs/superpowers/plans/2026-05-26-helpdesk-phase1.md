# Helpdesk Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully functional FastAPI + MariaDB foundation: JWT auth, RBAC with org-scoping, CRUD for Organizations and Users, seed data, and a Docker Compose stack that boots the whole thing.

**Architecture:** FastAPI on port 8001 with SQLAlchemy 2.x (sync ORM). MariaDB and Redis run in Docker containers (ports 3307 and 6380 to avoid Frappe conflicts). Development runs uvicorn directly against the Docker DB; the backend Dockerfile is for production deploys. All SQLAlchemy models match SCHEMA.sql exactly. Alembic is initialized but SCHEMA.sql is the bootstrap — Alembic only manages future changes.

**Tech Stack:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, PyMySQL, Alembic, python-jose (JWT), passlib[bcrypt], python-dotenv, pytest + httpx (tests).

**Spec:** `PLAN.md` sections 1–7, 11–12. `SCHEMA.sql` is the schema ground truth.

---

## File Map

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── seed.py
│   ├── models/
│   │   ├── __init__.py          ← imports every model (Alembic discovery)
│   │   ├── organization.py
│   │   ├── user.py
│   │   ├── team.py              ← Team, TeamMember, StaffOrgAssignment
│   │   ├── service.py           ← ServiceCategory, Service
│   │   ├── sla.py
│   │   ├── ticket.py            ← Ticket, TicketReply, TicketActivity
│   │   └── notification.py     ← Notification, EmailLog
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── organization.py
│   │   └── user.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── organizations.py
│   │   └── users.py
│   └── core/
│       ├── __init__.py
│       ├── security.py
│       ├── deps.py
│       └── permissions.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_security.py
│   ├── test_auth.py
│   ├── test_organizations.py
│   └── test_users.py
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_baseline.py
├── alembic.ini
├── requirements.txt
├── pytest.ini
├── .env                         ← gitignored (local dev, points to 127.0.0.1:3307)
├── .env.docker                  ← gitignored (container, points to db:3306)
└── Dockerfile
docker-compose.yml               ← repo root
.env                             ← repo root, feeds docker-compose secrets
.gitignore
```

---

### Task 1: Project scaffolding — directories, requirements, venv, gitignore

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Create: `.gitignore`

- [ ] **Step 1: Create directory tree**

```bash
cd ~/helpdesk-system
mkdir -p backend/app/{models,schemas,api,core}
mkdir -p backend/app/services backend/app/tasks
mkdir -p backend/tests
mkdir -p backend/alembic/versions
touch backend/app/__init__.py
touch backend/app/models/__init__.py
touch backend/app/schemas/__init__.py
touch backend/app/api/__init__.py
touch backend/app/core/__init__.py
touch backend/tests/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

```
# backend/requirements.txt
fastapi==0.115.5
uvicorn[standard]==0.32.1
sqlalchemy==2.0.36
pymysql==1.1.1
alembic==1.14.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.17
redis==5.2.0
celery==5.4.0
python-dotenv==1.0.1
python-socketio==5.11.4
email-validator==2.2.0
httpx==0.27.2
pytest==8.3.3
```

- [ ] **Step 3: Write pytest.ini**

```ini
# backend/pytest.ini
[pytest]
testpaths = tests
```

- [ ] **Step 4: Create and populate the venv**

```bash
cd ~/helpdesk-system/backend
python3.12 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```

Expected: pip prints "Successfully installed fastapi-0.115.5 ..." with no errors.

- [ ] **Step 5: Write .gitignore at repo root**

```
# .gitignore (repo root)
backend/venv/
__pycache__/
*.pyc
*.pyo
.env
.env.docker
*.egg-info/
.pytest_cache/
frontend/node_modules/
dist/
```

- [ ] **Step 6: Commit**

```bash
cd ~/helpdesk-system
git add backend/ .gitignore
git commit -m "feat: backend scaffolding — directory tree, requirements, venv"
```

---

### Task 2: Docker Compose + Dockerfile

**Files:**
- Create: `docker-compose.yml` (repo root)
- Create: `backend/Dockerfile`
- Create: `.env` (repo root, gitignored)
- Create: `backend/.env` (local dev, gitignored)
- Create: `backend/.env.docker` (container, gitignored)

- [ ] **Step 1: Write docker-compose.yml**

```yaml
# docker-compose.yml  (repo root)
version: "3.9"

services:
  db:
    image: mariadb:10.11
    container_name: helpdesk_db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: helpdesk_db
      MYSQL_USER: helpdesk
      MYSQL_PASSWORD: helpdesk_pass
    ports:
      - "3307:3306"
    volumes:
      - helpdesk_db_data:/var/lib/mysql
      - ./SCHEMA.sql:/docker-entrypoint-initdb.d/01_schema.sql:ro
    networks:
      - helpdesk-net
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uhelpdesk", "-phelpdesk_pass"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: helpdesk_redis
    restart: unless-stopped
    ports:
      - "6380:6379"
    networks:
      - helpdesk-net

  backend:
    build: ./backend
    container_name: helpdesk_backend
    restart: unless-stopped
    ports:
      - "8001:8001"
    env_file:
      - ./backend/.env.docker
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - helpdesk-net

volumes:
  helpdesk_db_data:

networks:
  helpdesk-net:
    driver: bridge
```

- [ ] **Step 2: Write backend/Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 3: Write backend/.env (local dev — uvicorn runs on host, DB in Docker)**

```
# backend/.env
DB_URL=mysql+pymysql://helpdesk:helpdesk_pass@127.0.0.1:3307/helpdesk_db
JWT_SECRET=dev-secret-change-in-production
JWT_ALGO=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

- [ ] **Step 4: Write backend/.env.docker (backend container — DB service name)**

```
# backend/.env.docker
DB_URL=mysql+pymysql://helpdesk:helpdesk_pass@db:3306/helpdesk_db
JWT_SECRET=dev-secret-change-in-production
JWT_ALGO=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

- [ ] **Step 5: Boot DB and Redis containers**

```bash
cd ~/helpdesk-system
docker compose up -d db redis
```

Wait for the health check to pass (about 20-30 seconds on first start while SCHEMA.sql is executed):

```bash
docker compose ps
# db should show "healthy"
docker compose logs db | tail -20
# should end with: "[Note] mariadbd: ready for connections."
```

- [ ] **Step 6: Verify DB and schema**

```bash
docker exec helpdesk_db mysql -uhelpdesk -phelpdesk_pass helpdesk_db -e "SHOW TABLES;"
```

Expected output includes all tables:
```
email_log
notifications
organizations
service_categories
services
sla_policies
staff_org_assignments
team_members
teams
ticket_activities
ticket_replies
tickets
users
```

- [ ] **Step 7: Create the test database**

```bash
docker exec helpdesk_db mysql -uroot -prootpass -e "
CREATE DATABASE IF NOT EXISTS helpdesk_test
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON helpdesk_test.* TO 'helpdesk'@'%';
FLUSH PRIVILEGES;
"
```

- [ ] **Step 8: Commit**

```bash
cd ~/helpdesk-system
git add docker-compose.yml backend/Dockerfile
git commit -m "feat: docker-compose with MariaDB:3307, Redis:6380, backend:8001"
```

---

### Task 3: config.py + database.py

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`

- [ ] **Step 1: Write config.py**

```python
# backend/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

DB_URL: str = os.getenv("DB_URL", "mysql+pymysql://helpdesk:helpdesk_pass@127.0.0.1:3307/helpdesk_db")
JWT_SECRET: str = os.getenv("JWT_SECRET", "changeme")
JWT_ALGO: str = os.getenv("JWT_ALGO", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
```

- [ ] **Step 2: Write database.py**

```python
# backend/app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import DB_URL

engine = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Verify import from venv**

```bash
cd ~/helpdesk-system/backend
venv/bin/python -c "from app.database import Base, get_db; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/app/database.py
git commit -m "feat: config and SQLAlchemy database layer"
```

---

### Task 4: SQLAlchemy models (all 13 tables)

**Files:**
- Create: `backend/app/models/organization.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/team.py`
- Create: `backend/app/models/service.py`
- Create: `backend/app/models/sla.py`
- Create: `backend/app/models/ticket.py`
- Create: `backend/app/models/notification.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: organization.py**

```python
# backend/app/models/organization.py
from sqlalchemy import BigInteger, Column, String, Text, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    contact_email = Column(String(255))
    phone = Column(String(50))
    status = Column(Enum("active", "inactive", "suspended"), nullable=False, default="active")
    notes = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: user.py**

```python
# backend/app/models/user.py
from sqlalchemy import BigInteger, Column, String, DateTime, Enum, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(Enum("admin", "staff", "customer"), nullable=False, default="customer")
    phone = Column(String(50))
    is_active = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 3: team.py**

```python
# backend/app/models/team.py
from sqlalchemy import BigInteger, Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class TeamMember(Base):
    __tablename__ = "team_members"

    team_id = Column(BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class StaffOrgAssignment(Base):
    __tablename__ = "staff_org_assignments"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
```

- [ ] **Step 4: service.py**

```python
# backend/app/models/service.py
from sqlalchemy import BigInteger, Column, String, Enum, Date, DateTime, DECIMAL, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)


class Service(Base):
    __tablename__ = "services"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    category_id = Column(BigInteger, ForeignKey("service_categories.id"))
    type = Column(Enum("saas", "hosting", "other"), nullable=False, default="saas")
    name = Column(String(200), nullable=False)
    domain = Column(String(255))
    status = Column(Enum("active", "inactive", "cancelled", "past_due"), nullable=False, default="active")
    start_date = Column(Date)
    expiry_date = Column(Date)
    disk_usage = Column(String(50))
    monthly_cost = Column(DECIMAL(15, 2), default=0)
    billing_cycle = Column(Enum("monthly", "quarterly", "yearly"), default="monthly")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 5: sla.py**

```python
# backend/app/models/sla.py
from sqlalchemy import BigInteger, Column, Enum, DECIMAL, DateTime
from sqlalchemy.sql import func
from app.database import Base


class SlaPolicy(Base):
    __tablename__ = "sla_policies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    priority = Column(Enum("Low", "Medium", "High", "Urgent"), nullable=False, unique=True)
    response_hours = Column(DECIMAL(5, 2), nullable=False)
    resolution_hours = Column(DECIMAL(5, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
```

- [ ] **Step 6: ticket.py**

```python
# backend/app/models/ticket.py
from sqlalchemy import BigInteger, Column, String, Text, Enum, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    service_id = Column(BigInteger, ForeignKey("services.id"))
    subject = Column(String(300), nullable=False)
    description = Column(Text)
    status = Column(
        Enum("Open", "In Progress", "Waiting", "Resolved", "Closed"),
        nullable=False, default="Open",
    )
    priority = Column(Enum("Low", "Medium", "High", "Urgent"), nullable=False, default="Medium")
    ticket_type = Column(
        Enum("Bug", "Incident", "Question", "Unspecified", "Service SaaS", "Service Hosting", "Renewal"),
        nullable=False, default="Unspecified",
    )
    source = Column(Enum("portal", "email", "phone", "manual"), nullable=False, default="portal")
    raised_by = Column(BigInteger, ForeignKey("users.id"))
    raised_by_email = Column(String(255))
    assignee_id = Column(BigInteger, ForeignKey("users.id"))
    team_id = Column(BigInteger, ForeignKey("teams.id"))
    response_by = Column(DateTime)
    resolution_by = Column(DateTime)
    first_responded_at = Column(DateTime)
    resolved_at = Column(DateTime)
    closed_at = Column(DateTime)
    sla_state = Column(Enum("green", "amber", "red", "breached"), default="green")
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class TicketReply(Base):
    __tablename__ = "ticket_replies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(BigInteger, ForeignKey("users.id"))
    author_email = Column(String(255))
    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, nullable=False, default=False)
    source = Column(Enum("portal", "email", "manual"), nullable=False, default="portal")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class TicketActivity(Base):
    __tablename__ = "ticket_activities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(BigInteger, ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    from_value = Column(String(100))
    to_value = Column(String(100))
    detail = Column(String(255))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
```

- [ ] **Step 7: notification.py**

```python
# backend/app/models/notification.py
from sqlalchemy import BigInteger, Column, String, Text, Enum, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text)
    type = Column(Enum("info", "sla", "assignment", "reply", "expiry"), nullable=False, default="info")
    ref_ticket_id = Column(BigInteger)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class EmailLog(Base):
    __tablename__ = "email_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(String(255), unique=True)
    from_email = Column(String(255))
    subject = Column(String(300))
    ticket_id = Column(BigInteger, ForeignKey("tickets.id"))
    action = Column(Enum("created", "appended", "skipped", "error"), nullable=False)
    detail = Column(String(255))
    processed_at = Column(DateTime, nullable=False, server_default=func.now())
```

- [ ] **Step 8: models/__init__.py — register all models with Base**

```python
# backend/app/models/__init__.py
from app.models.organization import Organization
from app.models.user import User
from app.models.team import Team, TeamMember, StaffOrgAssignment
from app.models.service import ServiceCategory, Service
from app.models.sla import SlaPolicy
from app.models.ticket import Ticket, TicketReply, TicketActivity
from app.models.notification import Notification, EmailLog

__all__ = [
    "Organization", "User",
    "Team", "TeamMember", "StaffOrgAssignment",
    "ServiceCategory", "Service",
    "SlaPolicy",
    "Ticket", "TicketReply", "TicketActivity",
    "Notification", "EmailLog",
]
```

- [ ] **Step 9: Verify all imports resolve**

```bash
cd ~/helpdesk-system/backend
venv/bin/python -c "from app.models import *; print('models OK')"
```

Expected: `models OK`

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/
git commit -m "feat: SQLAlchemy models — all 13 tables matching SCHEMA.sql"
```

---

### Task 5: Alembic init + baseline stamp

**Files:**
- Create: `backend/alembic.ini`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_baseline.py`

- [ ] **Step 1: Initialize Alembic**

```bash
cd ~/helpdesk-system/backend
venv/bin/alembic init alembic
```

Expected: creates `alembic.ini` and `alembic/` directory.

- [ ] **Step 2: Configure alembic.ini — set the URL placeholder**

In `backend/alembic.ini`, find and change:

```ini
sqlalchemy.url = driver://user:pass@localhost/dbname
```
to:
```ini
sqlalchemy.url = mysql+pymysql://helpdesk:helpdesk_pass@127.0.0.1:3307/helpdesk_db
```

- [ ] **Step 3: Replace alembic/env.py completely**

```python
# backend/alembic/env.py
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

load_dotenv()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override URL from environment so .env is the single source of truth
db_url = os.getenv("DB_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Import all models so Alembic can detect schema changes
import app.models  # noqa: F401 — registers all models with Base
from app.database import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Create the empty baseline migration**

```python
# backend/alembic/versions/0001_baseline.py
"""baseline

Revision ID: 0001
Revises:
Create Date: 2026-05-26
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # Schema already applied via SCHEMA.sql docker-entrypoint init


def downgrade() -> None:
    pass
```

- [ ] **Step 5: Stamp the database at the baseline**

```bash
cd ~/helpdesk-system/backend
venv/bin/alembic stamp 0001
```

Expected: `INFO  [alembic.runtime.migration] Running stamp_revision ...`

- [ ] **Step 6: Verify Alembic reports up-to-date**

```bash
venv/bin/alembic current
```

Expected: `0001 (head)`

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "feat: Alembic initialized, SCHEMA.sql stamped as baseline 0001"
```

---

### Task 6: Test infrastructure — conftest.py and helpers

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write conftest.py**

```python
# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = "mysql+pymysql://helpdesk:helpdesk_pass@127.0.0.1:3307/helpdesk_test"
engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    from app.database import Base
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Fresh session per test. Truncates all tables on teardown."""
    session = TestingSessionLocal()
    yield session
    session.close()
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for tbl in _get_sorted_tables():
            conn.execute(text(f"TRUNCATE TABLE `{tbl}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        conn.commit()


def _get_sorted_tables():
    from app.database import Base
    return [t.name for t in reversed(Base.metadata.sorted_tables)]


@pytest.fixture
def client(db):
    from app.main import app
    from app.database import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── shared data fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def provider_org(db):
    from app.models.organization import Organization
    org = Organization(name="OSD Provider", code="PROVIDER-TEST", status="active")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def admin_user(db, provider_org):
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        org_id=provider_org.id,
        email="admin@test.com",
        password_hash=hash_password("admin123"),
        full_name="Admin User",
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(client, admin_user):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def client_org(db):
    from app.models.organization import Organization
    org = Organization(name="Client Org A", code="CLT-TEST-A", status="active")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def customer_user(db, client_org):
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        org_id=client_org.id,
        email="customer@test.com",
        password_hash=hash_password("cust123"),
        full_name="Customer One",
        role="customer",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def customer_token(client, customer_user):
    r = client.post("/api/auth/login", json={"email": "customer@test.com", "password": "cust123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def staff_user(db, provider_org):
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        org_id=provider_org.id,
        email="staff@test.com",
        password_hash=hash_password("staff123"),
        full_name="Staff One",
        role="staff",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def staff_token(client, staff_user):
    r = client.post("/api/auth/login", json={"email": "staff@test.com", "password": "staff123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
```

- [ ] **Step 2: Verify conftest loads (no main.py yet — expected import error)**

```bash
cd ~/helpdesk-system/backend
venv/bin/pytest tests/ --collect-only 2>&1 | head -5
```

Expected: "ERROR collecting" or "ModuleNotFoundError: app.main" — that's fine; main.py comes next.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: conftest — test DB setup, session fixture, shared user fixtures"
```

---

### Task 7: core/security.py (TDD)

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_security.py
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)


def test_hash_and_verify_correct_password():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_wrong_password_returns_false():
    hashed = hash_password("mysecret")
    assert verify_password("wrong", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token({"sub": "42"})
    claims = decode_token(token)
    assert claims["sub"] == "42"
    assert claims["type"] == "access"


def test_refresh_token_roundtrip():
    token = create_refresh_token({"sub": "7"})
    claims = decode_token(token)
    assert claims["sub"] == "7"
    assert claims["type"] == "refresh"


def test_access_and_refresh_tokens_have_different_type_claim():
    access = create_access_token({"sub": "1"})
    refresh = create_refresh_token({"sub": "1"})
    assert decode_token(access)["type"] == "access"
    assert decode_token(refresh)["type"] == "refresh"
```

- [ ] **Step 2: Run — expect ImportError (module not created yet)**

```bash
cd ~/helpdesk-system/backend
venv/bin/pytest tests/test_security.py -v 2>&1 | head -10
```

Expected: `ImportError: cannot import name 'hash_password' from 'app.core.security'`

- [ ] **Step 3: Implement security.py**

```python
# backend/app/core/security.py
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from app.config import JWT_SECRET, JWT_ALGO, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = {**data, "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def create_refresh_token(data: dict) -> str:
    payload = {**data, "type": "refresh",
                "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
```

- [ ] **Step 4: Run — expect all 5 to pass**

```bash
venv/bin/pytest tests/test_security.py -v
```

Expected:
```
PASSED tests/test_security.py::test_hash_and_verify_correct_password
PASSED tests/test_security.py::test_verify_wrong_password_returns_false
PASSED tests/test_security.py::test_access_token_roundtrip
PASSED tests/test_security.py::test_refresh_token_roundtrip
PASSED tests/test_security.py::test_access_and_refresh_tokens_have_different_type_claim
5 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat: core/security — JWT create/decode, bcrypt hash/verify"
```

---

### Task 8: main.py + /health endpoint (TDD)

**Files:**
- Create: `backend/app/main.py`

- [ ] **Step 1: Write the failing test (add to conftest indirectly — or new file)**

```python
# backend/tests/test_health.py
def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_docs_accessible(client):
    r = client.get("/docs")
    assert r.status_code == 200
```

- [ ] **Step 2: Run — expect ImportError for app.main**

```bash
venv/bin/pytest tests/test_health.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError` or similar

- [ ] **Step 3: Write main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Helpdesk API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


# Routers are registered after their modules are created (Tasks 9-12).
# Uncomment each line as the corresponding task is completed:
# from app.api import auth, organizations, users
# app.include_router(auth.router)
# app.include_router(organizations.router)
# app.include_router(users.router)
```

- [ ] **Step 4: Run — expect 2 passed**

```bash
venv/bin/pytest tests/test_health.py -v
```

Expected:
```
PASSED tests/test_health.py::test_health_returns_ok
PASSED tests/test_health.py::test_docs_accessible
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_health.py
git commit -m "feat: FastAPI app with CORS, /health endpoint"
```

---

### Task 9: schemas/auth.py + api/auth.py (TDD)

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/core/deps.py` (partial — just `get_current_user` for now)
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py` (uncomment auth router)
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_auth.py


def test_login_returns_tokens(client, admin_user):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_returns_401(client, admin_user):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_email_returns_401(client):
    r = client.post("/api/auth/login", json={"email": "nobody@test.com", "password": "x"})
    assert r.status_code == 401


def test_refresh_returns_new_access_token(client, admin_user):
    login = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    refresh_token = login.json()["refresh_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_me_returns_current_user(client, admin_token, admin_user):
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "admin@test.com"
    assert body["role"] == "admin"


def test_me_without_token_returns_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_logout_returns_200(client, admin_token):
    r = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
```

- [ ] **Step 2: Run — expect import errors**

```bash
venv/bin/pytest tests/test_auth.py -v 2>&1 | head -10
```

Expected: errors because router not yet registered.

- [ ] **Step 3: Write schemas/auth.py**

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    org_id: int
```

- [ ] **Step 4: Write core/deps.py (only get_current_user for now)**

```python
# backend/app/core/deps.py
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import get_db
from app.models.user import User
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        claims = decode_token(token)
        if claims.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(claims["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_staff_or_admin(user: User = Depends(get_current_user)) -> User:
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="Staff or admin access required")
    return user
```

- [ ] **Step 5: Write api/auth.py**

```python
# backend/app/api/auth.py
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, AccessTokenResponse, MeResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email, User.is_active.is_(True)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest):
    try:
        claims = decode_token(payload.refresh_token)
        if claims.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return AccessTokenResponse(access_token=create_access_token({"sub": claims["sub"]}))
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    return {"message": "Logged out"}
```

- [ ] **Step 6: Register auth router in main.py**

Replace the commented router block in `backend/app/main.py`:

```python
from app.api import auth
app.include_router(auth.router)
```

The full `main.py` after this step:
```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth

app = FastAPI(title="Helpdesk API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Run — expect 7 passed**

```bash
venv/bin/pytest tests/test_auth.py -v
```

Expected:
```
PASSED tests/test_auth.py::test_login_returns_tokens
PASSED tests/test_auth.py::test_login_wrong_password_returns_401
PASSED tests/test_auth.py::test_login_unknown_email_returns_401
PASSED tests/test_auth.py::test_refresh_returns_new_access_token
PASSED tests/test_auth.py::test_me_returns_current_user
PASSED tests/test_auth.py::test_me_without_token_returns_401
PASSED tests/test_auth.py::test_logout_returns_200
7 passed
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/core/deps.py \
        backend/app/api/auth.py backend/app/main.py \
        backend/tests/test_auth.py
git commit -m "feat: JWT auth — login, refresh, me, logout + RBAC guards"
```

---

### Task 10: core/permissions.py + RBAC guard tests (TDD)

**Files:**
- Create: `backend/app/core/permissions.py`
- Create: `backend/tests/test_permissions.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_permissions.py


def test_unauthenticated_request_returns_401(client):
    r = client.get("/api/organizations")
    assert r.status_code == 401


def test_admin_can_reach_admin_only_endpoint(client, admin_token):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
    # 200 or 404 are both fine here — we just need NOT 403
    assert r.status_code != 403


def test_customer_cannot_reach_admin_only_endpoint(client, customer_token):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 403


def test_staff_cannot_reach_admin_only_endpoint(client, staff_token):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {staff_token}"})
    assert r.status_code == 403
```

Note: `/api/organizations` and `/api/users` don't exist yet — the 401/403 tests can run once we add those routers in the next tasks. For now, run just the 401 test (it should fail with 404 before routers exist):

- [ ] **Step 2: Write core/permissions.py**

```python
# backend/app/core/permissions.py
from sqlalchemy import select
from app.models.user import User
from app.models.team import StaffOrgAssignment


def org_scope_filter(query, model_class, user: User):
    """Apply org-based row-level filter to a SQLAlchemy query.
    Call at the top of every list endpoint.
    """
    if user.role == "admin":
        return query
    if user.role == "staff":
        assigned = (
            select(StaffOrgAssignment.org_id)
            .where(StaffOrgAssignment.user_id == user.id)
            .scalar_subquery()
        )
        return query.filter(model_class.org_id.in_(assigned))
    # customer — own org only
    return query.filter(model_class.org_id == user.org_id)
```

- [ ] **Step 3: Verify import**

```bash
cd ~/helpdesk-system/backend
venv/bin/python -c "from app.core.permissions import org_scope_filter; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit (permission tests complete after orgs/users routers exist)**

```bash
git add backend/app/core/permissions.py backend/tests/test_permissions.py
git commit -m "feat: org_scope_filter RBAC helper + permission tests (full pass after Task 11-12)"
```

---

### Task 11: schemas/organization.py + api/organizations.py (TDD)

**Files:**
- Create: `backend/app/schemas/organization.py`
- Create: `backend/app/api/organizations.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_organizations.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_organizations.py
from app.models.organization import Organization
from app.models.service import Service


def test_admin_can_list_all_orgs(client, admin_token, client_org, provider_org):
    r = client.get("/api/organizations", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()]
    assert client_org.id in ids
    assert provider_org.id in ids


def test_customer_sees_only_own_org(client, customer_token, customer_user, client_org, provider_org):
    r = client.get("/api/organizations", headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()]
    assert ids == [client_org.id]
    assert provider_org.id not in ids


def test_admin_can_create_org(client, admin_token):
    payload = {"name": "New Corp", "code": "NEW-CORP", "status": "active"}
    r = client.post("/api/organizations", json=payload,
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["code"] == "NEW-CORP"


def test_create_org_with_duplicate_code_returns_409(client, admin_token, client_org):
    payload = {"name": "Dup", "code": client_org.code, "status": "active"}
    r = client.post("/api/organizations", json=payload,
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 409


def test_customer_cannot_create_org(client, customer_token):
    r = client.post("/api/organizations",
                    json={"name": "X", "code": "X-001", "status": "active"},
                    headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 403


def test_get_org_detail(client, admin_token, client_org):
    r = client.get(f"/api/organizations/{client_org.id}",
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["id"] == client_org.id


def test_customer_cannot_view_other_org(client, customer_token, provider_org):
    r = client.get(f"/api/organizations/{provider_org.id}",
                   headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 403


def test_admin_can_update_org(client, admin_token, client_org):
    r = client.put(f"/api/organizations/{client_org.id}",
                   json={"phone": "0901234567"},
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["phone"] == "0901234567"


def test_get_org_services(client, admin_token, client_org, db):
    svc = Service(org_id=client_org.id, type="saas", name="Test SaaS", status="active")
    db.add(svc)
    db.commit()
    r = client.get(f"/api/organizations/{client_org.id}/services",
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert any(s["name"] == "Test SaaS" for s in r.json())


def test_unauthenticated_list_orgs_returns_401(client):
    r = client.get("/api/organizations")
    assert r.status_code == 401
```

- [ ] **Step 2: Run — expect import errors**

```bash
venv/bin/pytest tests/test_organizations.py -v 2>&1 | head -5
```

Expected: router not registered, likely 404 on org endpoints.

- [ ] **Step 3: Write schemas/organization.py**

```python
# backend/app/schemas/organization.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class OrganizationCreate(BaseModel):
    name: str
    code: str
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    name: str
    type: str
    status: str
    domain: Optional[str] = None
    expiry_date: Optional[str] = None
```

- [ ] **Step 4: Write api/organizations.py**

```python
# backend/app/api/organizations.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.organization import Organization
from app.models.service import Service
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.core.permissions import org_scope_filter
from app.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationOut, ServiceOut

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.get("", response_model=List[OrganizationOut])
def list_organizations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return org_scope_filter(db.query(Organization), Organization, user).all()


@router.post("", response_model=OrganizationOut)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if db.query(Organization).filter(Organization.code == payload.code).first():
        raise HTTPException(status_code=409, detail="Organization code already exists")
    org = Organization(**payload.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/{org_id}", response_model=OrganizationOut)
def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if user.role == "customer" and org.id != user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return org


@router.put("/{org_id}", response_model=OrganizationOut)
def update_organization(
    org_id: int,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(org, k, v)
    db.commit()
    db.refresh(org)
    return org


@router.get("/{org_id}/services", response_model=List[ServiceOut])
def get_org_services(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "customer" and org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return db.query(Service).filter(Service.org_id == org_id).all()
```

- [ ] **Step 5: Register organizations router in main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, organizations

app = FastAPI(title="Helpdesk API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(organizations.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run organizations tests — expect 10 passed**

```bash
venv/bin/pytest tests/test_organizations.py -v
```

Expected: `10 passed`

- [ ] **Step 7: Run permission tests now that router exists**

```bash
venv/bin/pytest tests/test_permissions.py -v
```

Expected: `4 passed` (the `/api/users` tests still 404 — those pass once Task 12 is done; for now expect `test_unauthenticated_request_returns_401` to pass, others may 404 which is `!= 403`)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/organization.py backend/app/api/organizations.py \
        backend/app/main.py backend/tests/test_organizations.py
git commit -m "feat: organizations CRUD — list (role-scoped), create, get, update, services"
```

---

### Task 12: schemas/user.py + api/users.py (TDD)

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/api/users.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_users.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_users.py


def test_admin_can_list_all_users(client, admin_token, admin_user, customer_user):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    emails = [u["email"] for u in r.json()]
    assert "admin@test.com" in emails
    assert "customer@test.com" in emails


def test_customer_cannot_list_users(client, customer_token):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 403


def test_staff_cannot_list_users(client, staff_token):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {staff_token}"})
    assert r.status_code == 403


def test_admin_can_create_user(client, admin_token, client_org):
    payload = {
        "email": "new@cty.vn",
        "password": "pass1234",
        "full_name": "New Person",
        "role": "customer",
        "org_id": client_org.id,
    }
    r = client.post("/api/users", json=payload,
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "new@cty.vn"
    assert "password_hash" not in body  # never exposed


def test_create_user_duplicate_email_returns_409(client, admin_token, admin_user, provider_org):
    payload = {
        "email": "admin@test.com",  # already exists
        "password": "x",
        "full_name": "Dup",
        "role": "staff",
        "org_id": provider_org.id,
    }
    r = client.post("/api/users", json=payload,
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 409


def test_admin_can_update_user(client, admin_token, customer_user):
    r = client.put(f"/api/users/{customer_user.id}",
                   json={"full_name": "Updated Name"},
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["full_name"] == "Updated Name"


def test_update_nonexistent_user_returns_404(client, admin_token):
    r = client.put("/api/users/99999",
                   json={"full_name": "Ghost"},
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run — expect 403/404 since router not registered**

```bash
venv/bin/pytest tests/test_users.py -v 2>&1 | head -10
```

- [ ] **Step 3: Write schemas/user.py**

```python
# backend/app/schemas/user.py
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "customer"
    org_id: int
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    org_id: int
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime
```

- [ ] **Step 4: Write api/users.py**

```python
# backend/app/api/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.core.deps import require_admin
from app.core.security import hash_password
from app.schemas.user import UserCreate, UserUpdate, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return db.query(User).all()


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already exists")
    data = payload.model_dump()
    data["password_hash"] = hash_password(data.pop("password"))
    new_user = User(**data)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(target, k, v)
    db.commit()
    db.refresh(target)
    return target
```

- [ ] **Step 5: Register users router in main.py (final version)**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, organizations, users

app = FastAPI(title="Helpdesk API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(users.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run all tests — expect everything green**

```bash
venv/bin/pytest tests/ -v
```

Expected:
```
PASSED tests/test_security.py::test_hash_and_verify_correct_password
PASSED tests/test_security.py::test_verify_wrong_password_returns_false
PASSED tests/test_security.py::test_access_token_roundtrip
PASSED tests/test_security.py::test_refresh_token_roundtrip
PASSED tests/test_security.py::test_access_and_refresh_tokens_have_different_type_claim
PASSED tests/test_health.py::test_health_returns_ok
PASSED tests/test_health.py::test_docs_accessible
PASSED tests/test_auth.py::test_login_returns_tokens
PASSED tests/test_auth.py::test_login_wrong_password_returns_401
PASSED tests/test_auth.py::test_login_unknown_email_returns_401
PASSED tests/test_auth.py::test_refresh_returns_new_access_token
PASSED tests/test_auth.py::test_me_returns_current_user
PASSED tests/test_auth.py::test_me_without_token_returns_401
PASSED tests/test_auth.py::test_logout_returns_200
PASSED tests/test_organizations.py::test_admin_can_list_all_orgs
PASSED tests/test_organizations.py::test_customer_sees_only_own_org
PASSED tests/test_organizations.py::test_admin_can_create_org
PASSED tests/test_organizations.py::test_create_org_with_duplicate_code_returns_409
PASSED tests/test_organizations.py::test_customer_cannot_create_org
PASSED tests/test_organizations.py::test_get_org_detail
PASSED tests/test_organizations.py::test_customer_cannot_view_other_org
PASSED tests/test_organizations.py::test_admin_can_update_org
PASSED tests/test_organizations.py::test_get_org_services
PASSED tests/test_organizations.py::test_unauthenticated_list_orgs_returns_401
PASSED tests/test_permissions.py::test_unauthenticated_request_returns_401
PASSED tests/test_permissions.py::test_admin_can_reach_admin_only_endpoint
PASSED tests/test_permissions.py::test_customer_cannot_reach_admin_only_endpoint
PASSED tests/test_permissions.py::test_staff_cannot_reach_admin_only_endpoint
PASSED tests/test_users.py::test_admin_can_list_all_users
PASSED tests/test_users.py::test_customer_cannot_list_users
PASSED tests/test_users.py::test_staff_cannot_list_users
PASSED tests/test_users.py::test_admin_can_create_user
PASSED tests/test_users.py::test_create_user_duplicate_email_returns_409
PASSED tests/test_users.py::test_admin_can_update_user
PASSED tests/test_users.py::test_update_nonexistent_user_returns_404
35 passed
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/user.py backend/app/api/users.py \
        backend/app/main.py backend/tests/test_users.py
git commit -m "feat: users CRUD (admin-only) — list, create, update"
```

---

### Task 13: seed.py — populate demo data

**Files:**
- Create: `backend/app/seed.py`

- [ ] **Step 1: Write seed.py**

```python
# backend/app/seed.py
"""Idempotent seed script. Safe to re-run."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models.organization import Organization
from app.models.user import User
from app.models.service import Service, ServiceCategory
from app.core.security import hash_password


def get_or_create(db, model, filter_by: dict, **kwargs):
    obj = db.query(model).filter_by(**filter_by).first()
    if not obj:
        obj = model(**filter_by, **kwargs)
        db.add(obj)
        db.flush()
    return obj


def seed():
    db = SessionLocal()
    try:
        # PROVIDER org (may already exist from SCHEMA.sql seed)
        provider = get_or_create(db, Organization,
                                  {"code": "PROVIDER"},
                                  name="OSD Provider", contact_email="admin@osd.vn", status="active")

        # Admin
        get_or_create(db, User, {"email": "admin@osd.vn"},
                      org_id=provider.id,
                      password_hash=hash_password("admin123"),
                      full_name="System Admin",
                      role="admin", is_active=True)

        # Staff
        for i in (1, 2):
            get_or_create(db, User, {"email": f"staff{i}@osd.vn"},
                          org_id=provider.id,
                          password_hash=hash_password("staff123"),
                          full_name=f"Staff User {i}",
                          role="staff", is_active=True)

        # Service categories (may already exist)
        cat_saas = get_or_create(db, ServiceCategory, {"slug": "saas"}, name="SaaS Subscription")
        cat_hosting = get_or_create(db, ServiceCategory, {"slug": "hosting"}, name="Web Hosting")

        # Client orgs
        for letter in ("A", "B", "C"):
            code = f"CTY-{letter}"
            org = get_or_create(db, Organization, {"code": code},
                                 name=f"Cong ty {letter}",
                                 contact_email=f"contact@cty-{letter.lower()}.vn",
                                 status="active")

            # 2 services per org (saas + hosting)
            get_or_create(db, Service, {"org_id": org.id, "name": f"SaaS Basic {letter}"},
                          category_id=cat_saas.id, type="saas", status="active")
            get_or_create(db, Service, {"org_id": org.id, "name": f"Hosting Pro {letter}"},
                          category_id=cat_hosting.id, type="hosting", status="active")

            # 2 customers per org
            for n in (1, 2):
                email = f"{letter.lower()}{n}@cty-{letter.lower()}.vn"
                get_or_create(db, User, {"email": email},
                              org_id=org.id,
                              password_hash=hash_password("customer123"),
                              full_name=f"Customer {n} ({letter})",
                              role="customer", is_active=True)

        db.commit()
        print("✓ Seed complete.")
        _print_summary(db)
    except Exception as exc:
        db.rollback()
        print(f"✗ Seed failed: {exc}")
        raise
    finally:
        db.close()


def _print_summary(db):
    print(f"  Organizations : {db.query(Organization).count()}")
    print(f"  Users         : {db.query(User).count()}")
    print(f"  Services      : {db.query(Service).count()}")


if __name__ == "__main__":
    seed()
```

- [ ] **Step 2: Run the seed**

```bash
cd ~/helpdesk-system/backend
venv/bin/python app/seed.py
```

Expected:
```
✓ Seed complete.
  Organizations : 4
  Users         : 9
  Services      : 6
```

(4 = PROVIDER + 3 clients; 9 = 1 admin + 2 staff + 6 customers)

- [ ] **Step 3: Verify rows directly in DB**

```bash
docker exec helpdesk_db mysql -uhelpdesk -phelpdesk_pass helpdesk_db \
  -e "SELECT email, role FROM users ORDER BY role, email;"
```

Expected: 9 rows with roles admin/staff/customer.

- [ ] **Step 4: Commit**

```bash
git add backend/app/seed.py
git commit -m "feat: seed script — 1 admin, 2 staff, 3 client orgs × 2 services × 2 customers"
```

---

### Task 14: End-to-end verification (6 curl checks)

These are the acceptance checks from the original spec.

- [ ] **Step 1: Start uvicorn locally**

```bash
cd ~/helpdesk-system/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

Leave this running. Open a second terminal for the curl commands below.

- [ ] **Step 2: Check 1 — Swagger loads**

```bash
curl -s http://localhost:8001/docs | grep -o "<title>.*</title>"
```

Expected: `<title>Helpdesk API - Swagger UI</title>`

- [ ] **Step 3: Check 2 — Admin login returns tokens**

```bash
curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@osd.vn","password":"admin123"}' | python3 -m json.tool
```

Expected:
```json
{
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer"
}
```

Save the access_token:
```bash
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@osd.vn","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo $ADMIN_TOKEN
```

- [ ] **Step 4: Check 3 — /me returns admin user**

```bash
curl -s http://localhost:8001/api/auth/me \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Expected:
```json
{
    "id": 1,
    "email": "admin@osd.vn",
    "full_name": "System Admin",
    "role": "admin",
    "org_id": 1
}
```

- [ ] **Step 5: Check 4 — Admin sees all 3 client orgs**

```bash
curl -s http://localhost:8001/api/organizations \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -c \
  "import sys,json; orgs=json.load(sys.stdin); print(f'{len(orgs)} orgs:'); [print(' ', o['code']) for o in orgs]"
```

Expected:
```
4 orgs:
  PROVIDER
  CTY-A
  CTY-B
  CTY-C
```

- [ ] **Step 6: Check 5 — Customer sees only their own org (RBAC scoping)**

```bash
CUST_TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"a1@cty-a.vn","password":"customer123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8001/api/organizations \
  -H "Authorization: Bearer $CUST_TOKEN" | python3 -m json.tool
```

Expected: array with exactly one org, code = `CTY-A`.

- [ ] **Step 7: Check 6 — /organizations/{id}/services returns that org's 2 services**

```bash
# Get CTY-A's org ID first
CTYA_ID=$(curl -s http://localhost:8001/api/organizations \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -c \
  "import sys,json; orgs=json.load(sys.stdin); print([o['id'] for o in orgs if o['code']=='CTY-A'][0])")

curl -s http://localhost:8001/api/organizations/$CTYA_ID/services \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Expected: array of 2 services — `SaaS Basic A` and `Hosting Pro A`.

- [ ] **Step 8: Final commit**

```bash
git add .
git commit -m "chore: Phase 1 complete — all 6 verification checks pass"
```

---

## Self-Review Checklist

**Spec coverage against PLAN.md Phase 1:**
- [x] Project skeleton, Docker Compose — Task 1-2
- [x] SQLAlchemy models + Alembic baseline — Task 4-5
- [x] JWT auth (login, refresh, me), bcrypt — Task 9
- [x] Role-based dependency guards + org-scope filters — Task 10
- [x] CRUD Organizations (list, create, get, update, services endpoint) — Task 11
- [x] CRUD Users (list, create, update) — Task 12
- [x] Seed script — Task 13
- [x] CORS for http://localhost:5173 — Task 8
- [x] Backend on port 8001 — Task 2

**Type consistency check:**
- `org_scope_filter(query, model_class, user)` — used with the same 3-arg signature in Task 10 definition and Task 11 usage ✓
- `hash_password` / `verify_password` — defined in `core/security.py` Task 7, used in `api/auth.py` Task 9 and `seed.py` Task 13 ✓
- `get_current_user`, `require_admin`, `require_staff_or_admin` — defined in `core/deps.py` Task 9, used in Tasks 11-12 ✓
- `UserOut.is_active` is `bool` — `User.is_active` is `Boolean` in SQLAlchemy → Pydantic reads it correctly ✓
