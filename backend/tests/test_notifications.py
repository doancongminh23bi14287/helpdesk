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
            "ticket_type": "Unspecified",
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
    return r.json()


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
