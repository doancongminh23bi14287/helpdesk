"""Regression tests for ticket tenant, assignment, and relation integrity."""


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_project(db, org_id, created_by, *, status="open", visibility="customer_visible"):
    from app.models.project import Project

    project = Project(
        org_id=org_id,
        name=f"Integrity project {org_id}",
        project_type="other",
        status=status,
        visibility=visibility,
        progress_percent=0,
        created_by=created_by,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def make_task(db, project_id, created_by, *, status="open", visible=True):
    from app.models.project import ProjectTask

    task = ProjectTask(
        project_id=project_id,
        title="Integrity task",
        task_type="other",
        status=status,
        priority="medium",
        is_client_visible=visible,
        created_by=created_by,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def create_ticket(client, token, org_id, service_id, **extra):
    payload = {
        "org_id": org_id,
        "service_id": service_id,
        "subject": "Integrity ticket",
        "assignment_mode": "none",
        **extra,
    }
    return client.post("/api/tickets", json=payload, headers=auth(token))


def test_customer_cannot_supply_manual_assignment(
    client, customer_token, customer_user, client_org, service, staff_user
):
    response = create_ticket(
        client,
        customer_token,
        client_org.id,
        service.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id],
    )
    assert response.status_code == 403


def test_non_staff_cannot_be_assigned(
    client, admin_token, client_org, service, customer_user
):
    response = create_ticket(
        client,
        admin_token,
        client_org.id,
        service.id,
        assignment_mode="manual",
        assignee_ids=[customer_user.id],
    )
    assert response.status_code == 422


def test_task_from_other_org_cannot_infer_project(
    client, admin_token, admin_user, client_org, second_client_org, service, db
):
    project = make_project(db, second_client_org.id, admin_user.id)
    task = make_task(db, project.id, admin_user.id)

    response = create_ticket(
        client,
        admin_token,
        client_org.id,
        service.id,
        task_id=task.id,
    )
    assert response.status_code == 422


def test_completed_task_cannot_receive_new_ticket(
    client, admin_token, admin_user, client_org, service, db
):
    project = make_project(db, client_org.id, admin_user.id)
    task = make_task(db, project.id, admin_user.id, status="completed")

    response = create_ticket(
        client,
        admin_token,
        client_org.id,
        service.id,
        project_id=project.id,
        task_id=task.id,
    )
    assert response.status_code == 422


def test_attachment_reply_must_belong_to_ticket(
    client, admin_token, admin_user, client_org, service, db
):
    from app.models.ticket import TicketReply

    first_response = create_ticket(client, admin_token, client_org.id, service.id)
    second_response = create_ticket(client, admin_token, client_org.id, service.id)
    assert first_response.status_code == 201
    assert second_response.status_code == 201
    first = first_response.json()
    second = second_response.json()
    reply = TicketReply(
        ticket_id=second["id"],
        author_id=admin_user.id,
        content="Reply on a different ticket",
        is_internal=False,
        source="portal",
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)

    response = client.post(
        f"/api/tickets/{first['id']}/attachments?reply_id={reply.id}",
        files={"file": ("note.txt", b"safe content", "text/plain")},
        headers=auth(admin_token),
    )
    assert response.status_code == 422


def test_unlink_project_also_clears_task(
    client, admin_token, admin_user, client_org, service, db
):
    project = make_project(db, client_org.id, admin_user.id)
    task = make_task(db, project.id, admin_user.id)
    created = create_ticket(
        client,
        admin_token,
        client_org.id,
        service.id,
        project_id=project.id,
        task_id=task.id,
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    response = client.delete(
        f"/api/tickets/{ticket_id}/unlink-project",
        headers=auth(admin_token),
    )
    assert response.status_code == 200
    detail = client.get(
        f"/api/tickets/{ticket_id}",
        headers=auth(admin_token),
    ).json()
    assert detail["project_id"] is None
    assert detail["task_id"] is None
