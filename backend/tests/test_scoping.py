# backend/tests/test_scoping.py
"""
Unit/integration tests for app.core.scoping.

Verifies:
  - get_accessible_org_ids: correct list per role
  - assert_org_access: passes for authorised orgs, raises 404 otherwise
  - scope_tickets: admin unrestricted; customer sees own; staff sees assigned orgs + personal
  - scope_invoices: customer / staff filtered to their orgs
  - scope_notifications: always user-scoped
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def second_client_org2(db):
    from app.models.organization import Organization
    org = Organization(name="Org B", code="ORG-B-SCOPING", status="active")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def staff_user2(db, provider_org):
    """A staff user with NO org assignments."""
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        org_id=provider_org.id,
        email="staff2@test.com",
        password_hash=hash_password("s2pass"),
        full_name="Staff Two",
        role="staff",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def assigned_staff(db, staff_user, client_org):
    """staff_user assigned to client_org via StaffOrgAssignment."""
    from app.models.team import StaffOrgAssignment
    a = StaffOrgAssignment(user_id=staff_user.id, org_id=client_org.id)
    db.add(a)
    db.commit()
    return staff_user


def _make_ticket(db, org_id, raised_by_id, assignee_id=None):
    from app.models.ticket import Ticket
    t = Ticket(
        org_id=org_id,
        raised_by=raised_by_id,
        raised_by_email="x@x.com",
        subject="Test ticket",
        description="desc",
        status="Open",
        priority="Medium",
        ticket_type="Question",
    )
    if assignee_id:
        t.assignee_id = assignee_id
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _make_invoice(db, org_id):
    from app.models.invoice import Invoice, generate_invoice_number
    inv = Invoice(
        invoice_number=generate_invoice_number(db, date.today().year),
        org_id=org_id,
        status="draft",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=15),
        subtotal=Decimal("100000"),
        tax_rate=Decimal("10.00"),
        tax_amount=Decimal("10000"),
        total=Decimal("110000"),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def _make_notification(db, user_id):
    from app.models.notification import Notification
    n = Notification(user_id=user_id, title="Test", content="Hi", type="info")
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


# ── get_accessible_org_ids ────────────────────────────────────────────────────

def test_admin_gets_unrestricted_org_ids(db, admin_user):
    from app.core.scoping import get_accessible_org_ids

    result = get_accessible_org_ids(admin_user, db)
    assert result is None


def test_staff_gets_assigned_org_ids_only(db, assigned_staff, client_org):
    from app.core.scoping import get_accessible_org_ids

    result = get_accessible_org_ids(assigned_staff, db)
    assert isinstance(result, list)
    assert client_org.id in result


def test_staff_with_no_assignments_gets_empty_list(db, staff_user2):
    from app.core.scoping import get_accessible_org_ids

    result = get_accessible_org_ids(staff_user2, db)
    assert result == []


def test_customer_gets_own_org_only(db, customer_user, client_org):
    from app.core.scoping import get_accessible_org_ids

    result = get_accessible_org_ids(customer_user, db)
    assert result == [client_org.id]


# ── assert_org_access ─────────────────────────────────────────────────────────

def test_assert_org_access_passes_for_valid_org(db, customer_user, client_org):
    from app.core.scoping import assert_org_access

    # Must not raise
    assert_org_access(client_org.id, customer_user, db)


def test_assert_org_access_raises_404_for_wrong_org(db, customer_user, second_client_org2):
    from fastapi import HTTPException
    from app.core.scoping import assert_org_access

    with pytest.raises(HTTPException) as exc_info:
        assert_org_access(second_client_org2.id, customer_user, db)
    assert exc_info.value.status_code == 404


def test_assert_org_access_admin_always_passes(db, admin_user, second_client_org2):
    from app.core.scoping import assert_org_access

    # Admin must never be blocked
    assert_org_access(second_client_org2.id, admin_user, db)


def test_assert_org_access_staff_passes_for_assigned_org(db, assigned_staff, client_org):
    from app.core.scoping import assert_org_access

    assert_org_access(client_org.id, assigned_staff, db)


def test_assert_org_access_staff_raises_for_unassigned_org(db, assigned_staff, second_client_org2):
    from fastapi import HTTPException
    from app.core.scoping import assert_org_access

    with pytest.raises(HTTPException) as exc_info:
        assert_org_access(second_client_org2.id, assigned_staff, db)
    assert exc_info.value.status_code == 404


# ── scope_tickets ─────────────────────────────────────────────────────────────

def test_scope_tickets_admin_sees_all(db, admin_user, client_org, second_client_org2, customer_user):
    from app.core.scoping import scope_tickets
    from app.models.ticket import Ticket

    t1 = _make_ticket(db, client_org.id, customer_user.id)
    t2 = _make_ticket(db, second_client_org2.id, customer_user.id)

    q = scope_tickets(db.query(Ticket), admin_user, db)
    ids = {t.id for t in q.all()}
    assert t1.id in ids
    assert t2.id in ids


def test_scope_tickets_customer_sees_only_own(
    db, customer_user, client_org, second_client_org2
):
    from app.core.scoping import scope_tickets
    from app.models.ticket import Ticket

    own = _make_ticket(db, client_org.id, customer_user.id)
    other = _make_ticket(db, second_client_org2.id, customer_user.id)

    q = scope_tickets(db.query(Ticket), customer_user, db)
    ids = {t.id for t in q.all()}
    assert own.id in ids
    assert other.id not in ids  # different org


def test_scope_tickets_staff_never_gains_cross_org_access_from_assignment(
    db, assigned_staff, client_org, second_client_org2, customer_user
):
    from app.core.scoping import scope_tickets
    from app.models.ticket import Ticket

    in_org = _make_ticket(db, client_org.id, customer_user.id)
    directly_assigned = _make_ticket(db, second_client_org2.id, customer_user.id, assignee_id=assigned_staff.id)
    invisible = _make_ticket(db, second_client_org2.id, customer_user.id)  # different org, not assigned

    q = scope_tickets(db.query(Ticket), assigned_staff, db)
    ids = {t.id for t in q.all()}
    assert in_org.id in ids
    assert directly_assigned.id not in ids
    assert invisible.id not in ids


# ── scope_invoices ────────────────────────────────────────────────────────────

def test_scope_invoices_customer_sees_own_org(
    db, customer_user, client_org, second_client_org2
):
    from app.core.scoping import scope_invoices
    from app.models.invoice import Invoice

    own = _make_invoice(db, client_org.id)
    other = _make_invoice(db, second_client_org2.id)

    q = scope_invoices(db.query(Invoice), customer_user, db)
    ids = {inv.id for inv in q.all()}
    assert own.id in ids
    assert other.id not in ids


def test_scope_invoices_staff_sees_assigned_orgs(
    db, assigned_staff, client_org, second_client_org2
):
    from app.core.scoping import scope_invoices
    from app.models.invoice import Invoice

    visible = _make_invoice(db, client_org.id)
    hidden = _make_invoice(db, second_client_org2.id)

    q = scope_invoices(db.query(Invoice), assigned_staff, db)
    ids = {inv.id for inv in q.all()}
    assert visible.id in ids
    assert hidden.id not in ids


def test_scope_invoices_admin_sees_all(
    db, admin_user, client_org, second_client_org2
):
    from app.core.scoping import scope_invoices
    from app.models.invoice import Invoice

    i1 = _make_invoice(db, client_org.id)
    i2 = _make_invoice(db, second_client_org2.id)

    q = scope_invoices(db.query(Invoice), admin_user, db)
    ids = {inv.id for inv in q.all()}
    assert i1.id in ids
    assert i2.id in ids


# ── scope_notifications ───────────────────────────────────────────────────────

def test_scope_notifications_user_scoped(
    db, customer_user, admin_user
):
    from app.core.scoping import scope_notifications
    from app.models.notification import Notification

    mine = _make_notification(db, customer_user.id)
    theirs = _make_notification(db, admin_user.id)

    q = scope_notifications(db.query(Notification), customer_user, db)
    ids = {n.id for n in q.all()}
    assert mine.id in ids
    assert theirs.id not in ids


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_project(db, org_id, created_by_id, name="Test Project"):
    from app.models.project import Project
    p = Project(
        org_id=org_id,
        name=name,
        project_type="seo",
        status="open",
        visibility="internal",
        created_by=created_by_id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ── scope_projects ────────────────────────────────────────────────────────────

def test_staff_sees_project_via_assigned_ticket(
    db, staff_user2, second_client_org2, customer_user
):
    """Staff with no org assignment sees a project only when they have a ticket
    linked to it and assigned to them."""
    from app.core.scoping import scope_projects
    from app.models.project import Project

    # project in an org that staff_user2 is NOT assigned to
    project = _make_project(db, second_client_org2.id, customer_user.id, name="Linked Project")

    # ticket in that org, assigned to staff_user2, linked to the project
    ticket = _make_ticket(db, second_client_org2.id, customer_user.id, assignee_id=staff_user2.id)
    ticket.project_id = project.id
    db.commit()

    q = scope_projects(db.query(Project), staff_user2, db)
    ids = {p.id for p in q.all()}
    assert project.id in ids, "staff should see project via assigned ticket"


def test_staff_does_not_see_unlinked_project(
    db, staff_user2, second_client_org2, customer_user
):
    """Control: staff with no org assignment and no assigned ticket cannot see the project."""
    from app.core.scoping import scope_projects
    from app.models.project import Project

    project = _make_project(db, second_client_org2.id, customer_user.id, name="Hidden Project")
    # No ticket linking staff_user2 to this project

    q = scope_projects(db.query(Project), staff_user2, db)
    ids = {p.id for p in q.all()}
    assert project.id not in ids, "staff should NOT see project without ticket link"
