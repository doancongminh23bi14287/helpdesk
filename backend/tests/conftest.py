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
    # Purge any data left from a previous interrupted run
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"TRUNCATE TABLE `{tbl.name}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        conn.commit()
    yield
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DROP TABLE IF EXISTS `{tbl.name}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        conn.commit()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate-limit counters and Redis blacklist keys before every test."""
    from app.core.limiter import limiter
    try:
        limiter._storage.reset()
    except Exception:
        pass
    # Clear Redis keys that use auto-incremented IDs as part of their name.
    # These bleed across test sessions because TRUNCATE resets autoincrement,
    # causing new test records to get the same IDs as previous-session records.
    from app.core.redis_client import redis_client
    for pattern in ("blacklist:user:*", "expiry_notif:*", "sla:*", "reset_jti:*"):
        for key in redis_client.scan_iter(pattern):
            redis_client.delete(key)
    yield


def _truncate_all(conn):
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    for tbl in _get_sorted_tables():
        conn.execute(text(f"TRUNCATE TABLE `{tbl}`"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    conn.commit()


@pytest.fixture
def db():
    """Fresh session per test. Truncates all tables before AND after each test."""
    with engine.connect() as conn:
        _truncate_all(conn)
    session = TestingSessionLocal()
    yield session
    session.close()
    with engine.connect() as conn:
        _truncate_all(conn)


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


@pytest.fixture
def service(db, client_org):
    """A saas service belonging to client_org."""
    from app.models.service import Service
    svc = Service(org_id=client_org.id, name="Test SaaS", type="saas", status="active")
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


@pytest.fixture
def second_client_org(db):
    from app.models.organization import Organization
    org = Organization(name="Client Org B", code="CLT-TEST-B", status="active")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def second_customer_user(db, second_client_org):
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        org_id=second_client_org.id,
        email="customer2@test.com",
        password_hash=hash_password("cust123"),
        full_name="Customer Two",
        role="customer",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def second_customer_token(client, second_customer_user):
    r = client.post("/api/auth/login", json={"email": "customer2@test.com", "password": "cust123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def staff_assignment(db, staff_user, client_org):
    """Assign staff_user to client_org via StaffOrgAssignment."""
    from app.models.team import StaffOrgAssignment
    assignment = StaffOrgAssignment(user_id=staff_user.id, org_id=client_org.id)
    db.add(assignment)
    db.commit()
    return assignment
