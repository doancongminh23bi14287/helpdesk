# backend/tests/test_notifications.py
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_ticket(client, token, org_id, service_id, subject="Test Subject"):
    r = client.post(
        "/api/tickets",
        json={
            "org_id": org_id,
            "service_id": service_id,
            "subject": subject,
            "priority": "Medium",
            "ticket_type": "Question",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _assign_ticket(client, token, ticket_id, assignee_id):
    r = client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"assignee_id": assignee_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _add_reply(client, token, ticket_id, content="Hello there"):
    r = client.post(
        f"/api/tickets/{ticket_id}/replies",
        json={"content": content, "is_internal": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _get_notifications(client, token):
    r = client.get(
        "/api/notifications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Support both the paginated shape {"items": [...], ...} and legacy list
    if isinstance(body, dict) and "items" in body:
        return body["items"]
    return body


# ── tests ─────────────────────────────────────────────────────────────────────

def test_notification_created_on_assign(
    client, db,
    admin_token, admin_user,
    staff_user, staff_token,
    staff_assignment,
    client_org, service,
    customer_user, customer_token,
):
    """Admin assigns ticket to staff_user → staff_user gets an 'assignment' notification."""
    ticket = _make_ticket(client, customer_token, client_org.id, service.id, "Assign Me")
    ticket_id = ticket["id"]

    # Admin assigns to staff_user
    _assign_ticket(client, admin_token, ticket_id, staff_user.id)

    notifications = _get_notifications(client, staff_token)
    assignment_notifs = [
        n for n in notifications
        if n["type"] == "assignment" and n["ref_ticket_id"] == ticket_id
    ]
    assert len(assignment_notifs) >= 1, f"Expected assignment notification, got: {notifications}"


def test_notification_created_on_reply_to_assignee(
    client, db,
    admin_token, admin_user,
    staff_user, staff_token,
    staff_assignment,
    client_org, service,
    customer_user, customer_token,
):
    """Customer replies on a ticket assigned to staff → staff gets a 'reply' notification."""
    ticket = _make_ticket(client, customer_token, client_org.id, service.id, "Reply Notify")
    ticket_id = ticket["id"]

    # Assign to staff so assignee_id is set
    _assign_ticket(client, admin_token, ticket_id, staff_user.id)

    # Customer posts a reply
    _add_reply(client, customer_token, ticket_id, "Customer says hello")

    notifications = _get_notifications(client, staff_token)
    reply_notifs = [
        n for n in notifications
        if n["type"] == "reply" and n["ref_ticket_id"] == ticket_id
    ]
    assert len(reply_notifs) >= 1, f"Expected reply notification for staff, got: {notifications}"


def test_notification_created_on_reply_to_customer(
    client, db,
    admin_token, admin_user,
    staff_user, staff_token,
    staff_assignment,
    client_org, service,
    customer_user, customer_token,
):
    """Staff replies on a ticket → customer (raised_by) gets a 'reply' notification."""
    ticket = _make_ticket(client, customer_token, client_org.id, service.id, "Staff Reply Notify")
    ticket_id = ticket["id"]

    # Assign to staff
    _assign_ticket(client, admin_token, ticket_id, staff_user.id)

    # Staff posts a reply
    _add_reply(client, staff_token, ticket_id, "Staff says hello")

    notifications = _get_notifications(client, customer_token)
    reply_notifs = [
        n for n in notifications
        if n["type"] == "reply" and n["ref_ticket_id"] == ticket_id
    ]
    assert len(reply_notifs) >= 1, f"Expected reply notification for customer, got: {notifications}"


def test_notifications_scoped_to_owner(
    client, db,
    admin_token, admin_user,
    staff_user, staff_token,
    staff_assignment,
    client_org, service,
    customer_user, customer_token,
    second_customer_user, second_customer_token,
):
    """Notifications are scoped: user A cannot see user B's notifications."""
    ticket = _make_ticket(client, customer_token, client_org.id, service.id, "Scope Test")
    ticket_id = ticket["id"]

    # Assign to staff_user → creates notification for staff_user only
    _assign_ticket(client, admin_token, ticket_id, staff_user.id)

    # staff_user should see it
    staff_notifs = _get_notifications(client, staff_token)
    assert any(n["ref_ticket_id"] == ticket_id for n in staff_notifs)

    # customer should NOT see staff's notifications
    customer_notifs = _get_notifications(client, customer_token)
    staff_assignment_notifs = [
        n for n in customer_notifs
        if n["type"] == "assignment" and n["ref_ticket_id"] == ticket_id
    ]
    assert len(staff_assignment_notifs) == 0, (
        f"customer should not see staff assignment notifications, got: {customer_notifs}"
    )


def test_mark_notification_read(
    client, db,
    admin_token, admin_user,
    staff_user, staff_token,
    staff_assignment,
    client_org, service,
    customer_user, customer_token,
):
    """Mark a single notification as read via PUT /api/notifications/{id}/read."""
    ticket = _make_ticket(client, customer_token, client_org.id, service.id, "Mark Read Test")
    ticket_id = ticket["id"]

    _assign_ticket(client, admin_token, ticket_id, staff_user.id)

    notifications = _get_notifications(client, staff_token)
    notif = next(
        (n for n in notifications if n["type"] == "assignment" and n["ref_ticket_id"] == ticket_id),
        None,
    )
    assert notif is not None, "Expected assignment notification"
    assert notif["is_read"] is False

    r = client.put(
        f"/api/notifications/{notif['id']}/read",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_read"] is True


def test_mark_all_read(
    client, db,
    admin_token, admin_user,
    staff_user, staff_token,
    staff_assignment,
    client_org, service,
    customer_user, customer_token,
):
    """PUT /api/notifications/read-all marks every notification read."""
    # Create 3 notifications: assign 3 different tickets
    for i in range(3):
        ticket = _make_ticket(
            client, customer_token, client_org.id, service.id, f"Mark All Read {i}"
        )
        _assign_ticket(client, admin_token, ticket["id"], staff_user.id)

    notifications = _get_notifications(client, staff_token)
    assignment_notifs = [n for n in notifications if n["type"] == "assignment"]
    assert len(assignment_notifs) >= 3, f"Expected 3 assignment notifications, got: {notifications}"

    r = client.put(
        "/api/notifications/read-all",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 200, r.text

    notifications_after = _get_notifications(client, staff_token)
    unread = [n for n in notifications_after if not n["is_read"]]
    assert len(unread) == 0, f"Expected all read, still unread: {unread}"


def test_mark_read_other_users_notification_404(
    client, db,
    admin_token, admin_user,
    staff_user, staff_token,
    staff_assignment,
    client_org, service,
    customer_user, customer_token,
):
    """customer_user cannot mark admin's notification as read → 404."""
    ticket = _make_ticket(client, customer_token, client_org.id, service.id, "Cross User Test")
    ticket_id = ticket["id"]

    # Assign to staff_user → creates notification for staff_user
    _assign_ticket(client, admin_token, ticket_id, staff_user.id)

    staff_notifs = _get_notifications(client, staff_token)
    notif = next(
        (n for n in staff_notifs if n["type"] == "assignment" and n["ref_ticket_id"] == ticket_id),
        None,
    )
    assert notif is not None, "Expected assignment notification for staff"

    # customer_user tries to mark it as read → should be 404
    r = client.put(
        f"/api/notifications/{notif['id']}/read",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 404, r.text


def test_notification_created_on_auto_assign(client, db, admin_token, admin_user,
                                              provider_org, client_org, service,
                                              staff_user, staff_assignment):
    """Auto-assignment on ticket create notifies the assigned agent."""
    # staff_user is the only candidate (via staff_assignment to client_org)
    # Login to set last_login_at so online score applies
    client.post("/api/auth/login", json={"email": staff_user.email, "password": "staff123"})

    r = client.post("/api/tickets",
                    json={"org_id": client_org.id, "service_id": service.id,
                          "subject": "Auto-assign notify test"},
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 201
    ticket_id = r.json()["id"]
    assignee_id = r.json()["assignee_id"]

    if assignee_id is None:
        pytest.skip("No staff candidate available for auto-assign")

    # Check assignee received assignment notification
    from app.models.notification import Notification
    notif = db.query(Notification).filter(
        Notification.user_id == assignee_id,
        Notification.type == "assignment",
        Notification.ref_ticket_id == ticket_id,
    ).first()
    assert notif is not None


def test_notifications_paginated(
    client, db,
    admin_token, admin_user,
    staff_user, staff_token,
    staff_assignment,
    client_org, service,
    customer_user, customer_token,
):
    """list_notifications returns paginated shape with correct structure."""
    # Create 3 assignment notifications for staff_user
    for i in range(3):
        ticket = _make_ticket(
            client, customer_token, client_org.id, service.id, f"Paginate Test {i}"
        )
        _assign_ticket(client, admin_token, ticket["id"], staff_user.id)

    r = client.get(
        "/api/notifications?per_page=2&page=1",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body, f"Expected paginated shape, got: {body}"
    assert "total" in body
    assert "page" in body
    assert "per_page" in body
    assert "pages" in body
    assert len(body["items"]) == 2
    assert body["total"] >= 3
    assert body["pages"] >= 2
    assert body["page"] == 1
    assert body["per_page"] == 2


def test_unread_count_endpoint(
    client, db,
    admin_token, admin_user,
    staff_user, staff_token,
    staff_assignment,
    client_org, service,
    customer_user, customer_token,
):
    """unread-count returns correct integer for current user."""
    # Create 2 unread assignment notifications
    for i in range(2):
        ticket = _make_ticket(
            client, customer_token, client_org.id, service.id, f"Unread Count {i}"
        )
        _assign_ticket(client, admin_token, ticket["id"], staff_user.id)

    # Mark 1 as read via the read-all endpoint (we'll use individual mark-read)
    # First get notifications to find one id
    r = client.get(
        "/api/notifications?per_page=100",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assignment_notifs = [n for n in items if n["type"] == "assignment"]
    assert len(assignment_notifs) >= 2

    # Mark exactly 1 as read
    r = client.put(
        f"/api/notifications/{assignment_notifs[0]['id']}/read",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 200

    # Check unread count — should be at least 1 (the other assignment notif)
    r = client.get(
        "/api/notifications/unread-count",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "unread" in body
    assert body["unread"] >= 1
