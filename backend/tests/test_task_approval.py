"""Tests for Sprint F: task approval flow."""
import pytest


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_project(db, org_id, created_by, name="Approval Project"):
    from app.models.project import Project
    p = Project(
        org_id=org_id,
        name=name,
        project_type="seo",
        status="open",
        visibility="customer_visible",
        created_by=created_by,
        progress_percent=0,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_task(db, project_id, created_by, status="working", is_client_visible=True):
    from app.models.project import ProjectTask
    t = ProjectTask(
        project_id=project_id,
        title="Approval Task",
        task_type="other",
        status=status,
        priority="medium",
        is_client_visible=is_client_visible,
        created_by=created_by,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _add_member(db, project_id, user_id, role, added_by):
    from app.models.project import ProjectMember
    m = ProjectMember(project_id=project_id, user_id=user_id, role=role, added_by=added_by)
    db.add(m)
    db.commit()
    return m


# ── F.3 submit_for_review ─────────────────────────────────────────────────────

def test_staff_submit_for_review(
    client, db, admin_token, admin_user, staff_user, staff_token, customer_user, client_org
):
    """Staff submits task → status='review', approval record created, customer notified."""
    project = _make_project(db, client_org.id, admin_user.id)
    _add_member(db, project.id, customer_user.id, "customer", admin_user.id)
    task = _make_task(db, project.id, admin_user.id, status="working")

    r = client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "submitted_for_review"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["action"] == "submitted_for_review"
    assert data["actor_id"] == admin_user.id

    # Task status updated
    task_r = client.get(f"/api/project-tasks/{task.id}", headers=_auth(admin_token))
    assert task_r.json()["status"] == "review"

    # Approval record saved
    from app.models.project import TaskApproval
    db.expire_all()
    approvals = db.query(TaskApproval).filter(TaskApproval.task_id == task.id).all()
    assert len(approvals) == 1
    assert approvals[0].action == "submitted_for_review"

    # Notification created for customer
    from app.models.notification import Notification
    notif = db.query(Notification).filter(
        Notification.user_id == customer_user.id,
        Notification.title == "Task needs your approval",
    ).first()
    assert notif is not None


def test_customer_approve(
    client, db, admin_token, customer_token, admin_user, customer_user, client_org, staff_user
):
    """Customer approves task in review → status='approved', staff notified."""
    project = _make_project(db, client_org.id, admin_user.id)
    _add_member(db, project.id, customer_user.id, "customer", admin_user.id)
    _add_member(db, project.id, staff_user.id, "staff", admin_user.id)
    task = _make_task(db, project.id, admin_user.id, status="review")

    r = client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "approved"},
        headers=_auth(customer_token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["action"] == "approved"

    # Status updated
    task_r = client.get(f"/api/project-tasks/{task.id}", headers=_auth(admin_token))
    assert task_r.json()["status"] == "approved"

    # Staff notified
    from app.models.notification import Notification
    notif = db.query(Notification).filter(
        Notification.user_id == staff_user.id,
        Notification.title == "Task approved",
    ).first()
    assert notif is not None


def test_customer_request_changes(
    client, db, admin_token, customer_token, admin_user, customer_user, client_org, staff_user
):
    """Customer requests changes → status='working', comment saved, staff notified."""
    project = _make_project(db, client_org.id, admin_user.id)
    _add_member(db, project.id, customer_user.id, "customer", admin_user.id)
    _add_member(db, project.id, staff_user.id, "staff", admin_user.id)
    task = _make_task(db, project.id, admin_user.id, status="review")

    r = client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "changes_requested", "comment": "Please fix the intro paragraph"},
        headers=_auth(customer_token),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["action"] == "changes_requested"
    assert data["comment"] == "Please fix the intro paragraph"

    # Status reverted
    task_r = client.get(f"/api/project-tasks/{task.id}", headers=_auth(admin_token))
    assert task_r.json()["status"] == "working"

    # Staff notified
    from app.models.notification import Notification
    notif = db.query(Notification).filter(
        Notification.user_id == staff_user.id,
        Notification.title == "Changes requested on task",
    ).first()
    assert notif is not None

    # Comment stored in approval record
    from app.models.project import TaskApproval
    db.expire_all()
    approval = db.query(TaskApproval).filter(TaskApproval.task_id == task.id).first()
    assert approval.comment == "Please fix the intro paragraph"


def test_customer_cannot_submit_for_review(
    client, db, admin_user, customer_token, customer_user, client_org
):
    """Customer trying to submit_for_review → 403."""
    project = _make_project(db, client_org.id, admin_user.id)
    _add_member(db, project.id, customer_user.id, "customer", admin_user.id)
    task = _make_task(db, project.id, admin_user.id, status="working")

    r = client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "submitted_for_review"},
        headers=_auth(customer_token),
    )
    assert r.status_code == 403


def test_staff_cannot_approve(
    client, db, admin_user, staff_user, staff_token, staff_assignment, client_org
):
    """Staff trying to approve → 403."""
    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id, status="review")

    r = client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "approved"},
        headers=_auth(staff_token),
    )
    assert r.status_code == 403


def test_wrong_status_for_action_returns_422(
    client, db, admin_token, admin_user, client_org
):
    """Trying to approve a task that isn't in 'review' → 422."""
    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id, status="working")

    r = client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "approved"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 422


def test_customer_cannot_approve_invisible_task(
    client, db, admin_user, customer_token, customer_user, client_org
):
    """Customer cannot approve a task with is_client_visible=False → 404 (existence leak fix)."""
    project = _make_project(db, client_org.id, admin_user.id)
    _add_member(db, project.id, customer_user.id, "customer", admin_user.id)
    task = _make_task(db, project.id, admin_user.id, status="review", is_client_visible=False)

    r = client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "approved"},
        headers=_auth(customer_token),
    )
    assert r.status_code == 404


def test_get_approvals_customer_blocked_on_invisible_task(
    client, db, admin_user, customer_token, customer_user, client_org
):
    """Customer cannot GET approvals for a non-client-visible task → 404 (existence leak fix)."""
    project = _make_project(db, client_org.id, admin_user.id)
    _add_member(db, project.id, customer_user.id, "customer", admin_user.id)
    task = _make_task(db, project.id, admin_user.id, status="review", is_client_visible=False)

    r = client.get(
        f"/api/project-tasks/{task.id}/approvals",
        headers=_auth(customer_token),
    )
    assert r.status_code == 404


def test_approval_history_newest_first(
    client, db, admin_token, customer_token, admin_user, customer_user, client_org
):
    """GET /approvals returns records newest-first."""
    project = _make_project(db, client_org.id, admin_user.id)
    _add_member(db, project.id, customer_user.id, "customer", admin_user.id)
    task = _make_task(db, project.id, admin_user.id, status="working")

    # submit → approve cycle
    client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "submitted_for_review"},
        headers=_auth(admin_token),
    )
    client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "approved"},
        headers=_auth(customer_token),
    )

    r = client.get(f"/api/project-tasks/{task.id}/approvals", headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 2
    # Newest first: 'approved' was created after 'submitted_for_review'
    assert items[0]["action"] == "approved"
    assert items[1]["action"] == "submitted_for_review"


def test_submit_for_review_from_review_status(
    client, db, admin_token, admin_user, client_org
):
    """Staff can submit_for_review even when task is already in 'review' (idempotent)."""
    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id, status="review")

    r = client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "submitted_for_review"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 201, r.text
    task_r = client.get(f"/api/project-tasks/{task.id}", headers=_auth(admin_token))
    assert task_r.json()["status"] == "review"
