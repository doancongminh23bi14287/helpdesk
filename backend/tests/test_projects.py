from app.models.project import Project, ProjectTask


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _project_payload(org_id, **overrides):
    payload = {
        "org_id": org_id,
        "name": "SEO Growth Project",
        "description": "Client SEO delivery plan",
        "project_type": "seo",
        "visibility": "customer_visible",
    }
    payload.update(overrides)
    return payload


def _task_payload(**overrides):
    payload = {
        "title": "Keyword Research",
        "task_type": "keyword_research",
        "priority": "medium",
        "status": "open",
        "is_client_visible": True,
        "internal_note": "Internal SERP workflow",
    }
    payload.update(overrides)
    return payload


def test_admin_can_create_project_for_any_org(client, admin_token, client_org):
    r = client.post("/api/projects", json=_project_payload(client_org.id), headers=_auth(admin_token))

    assert r.status_code == 201, r.text
    data = r.json()
    assert data["org_id"] == client_org.id
    assert data["name"] == "SEO Growth Project"
    assert data["progress_percent"] == 0


def test_staff_can_create_project_only_for_assigned_org(
    client,
    staff_token,
    staff_assignment,
    client_org,
    second_client_org,
):
    allowed = client.post("/api/projects", json=_project_payload(client_org.id), headers=_auth(staff_token))
    denied = client.post("/api/projects", json=_project_payload(second_client_org.id), headers=_auth(staff_token))

    assert allowed.status_code == 201, allowed.text
    assert denied.status_code == 404, denied.text


def test_customer_cannot_create_or_update_project(client, customer_token, db, client_org, admin_user):
    project = Project(org_id=client_org.id, name="Internal SEO", created_by=admin_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    create_r = client.post("/api/projects", json=_project_payload(client_org.id), headers=_auth(customer_token))
    update_r = client.patch(f"/api/projects/{project.id}", json={"name": "Changed"}, headers=_auth(customer_token))

    assert create_r.status_code == 403
    assert update_r.status_code == 403


def test_customer_lists_only_own_customer_visible_projects(
    client,
    customer_token,
    db,
    client_org,
    second_client_org,
    admin_user,
):
    visible = Project(org_id=client_org.id, name="Visible SEO", visibility="customer_visible", created_by=admin_user.id)
    internal = Project(org_id=client_org.id, name="Internal SEO", visibility="internal", created_by=admin_user.id)
    other = Project(org_id=second_client_org.id, name="Other Org SEO", visibility="customer_visible", created_by=admin_user.id)
    db.add_all([visible, internal, other])
    db.commit()

    r = client.get("/api/projects", headers=_auth(customer_token))

    assert r.status_code == 200, r.text
    names = {item["name"] for item in r.json()["items"]}
    assert names == {"Visible SEO"}


def test_out_of_scope_project_returns_404_for_customer_and_staff(
    client,
    customer_token,
    staff_token,
    staff_assignment,
    db,
    second_client_org,
    admin_user,
):
    project = Project(org_id=second_client_org.id, name="Other SEO", visibility="customer_visible", created_by=admin_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    customer_r = client.get(f"/api/projects/{project.id}", headers=_auth(customer_token))
    staff_r = client.get(f"/api/projects/{project.id}", headers=_auth(staff_token))

    assert customer_r.status_code == 404
    assert staff_r.status_code == 404


def test_customer_sees_only_client_visible_tasks_and_no_internal_note(
    client,
    customer_token,
    db,
    client_org,
    admin_user,
):
    project = Project(org_id=client_org.id, name="Visible SEO", visibility="customer_visible", created_by=admin_user.id)
    db.add(project)
    db.flush()
    public = ProjectTask(
        project_id=project.id,
        title="Monthly Report",
        task_type="report",
        is_client_visible=True,
        internal_note="Do not leak",
    )
    internal = ProjectTask(project_id=project.id, title="Backlink Prospecting", is_client_visible=False)
    db.add_all([public, internal])
    db.commit()

    r = client.get(f"/api/projects/{project.id}/tasks", headers=_auth(customer_token))

    assert r.status_code == 200, r.text
    tasks = r.json()
    assert [task["title"] for task in tasks] == ["Monthly Report"]
    assert "internal_note" not in tasks[0]
    assert "assignee_email" not in tasks[0]


def test_admin_can_create_tasks_and_progress_updates(client, admin_token, db, client_org, admin_user):
    project = Project(org_id=client_org.id, name="Progress SEO", created_by=admin_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    first = client.post(
        f"/api/projects/{project.id}/tasks",
        json=_task_payload(title="Technical SEO Audit", task_type="technical_audit"),
        headers=_auth(admin_token),
    )
    second = client.post(
        f"/api/projects/{project.id}/tasks",
        json=_task_payload(title="Monthly Report", task_type="report", status="completed"),
        headers=_auth(admin_token),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    db.refresh(project)
    assert float(project.progress_percent) == 50.0
    assert project.status == "open"


def test_cancelled_tasks_excluded_and_all_active_completed_sets_project_completed(
    client,
    admin_token,
    db,
    client_org,
    admin_user,
):
    project = Project(org_id=client_org.id, name="Completion SEO", created_by=admin_user.id)
    db.add(project)
    db.flush()
    active = ProjectTask(project_id=project.id, title="On-page", status="open")
    cancelled = ProjectTask(project_id=project.id, title="Cancelled", status="cancelled")
    db.add_all([active, cancelled])
    db.commit()
    db.refresh(active)

    r = client.patch(
        f"/api/project-tasks/{active.id}/status",
        json={"status": "completed"},
        headers=_auth(admin_token),
    )

    assert r.status_code == 200, r.text
    db.refresh(project)
    assert float(project.progress_percent) == 100.0
    assert project.status == "completed"


def test_adding_open_task_to_completed_project_reopens_project(client, admin_token, db, client_org, admin_user):
    project = Project(
        org_id=client_org.id,
        name="Reopen SEO",
        status="completed",
        progress_percent=100,
        created_by=admin_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    r = client.post(
        f"/api/projects/{project.id}/tasks",
        json=_task_payload(title="New Audit", is_client_visible=False),
        headers=_auth(admin_token),
    )

    assert r.status_code == 201, r.text
    db.refresh(project)
    assert float(project.progress_percent) == 0
    assert project.status == "open"


def test_staff_and_customer_task_permissions(
    client,
    staff_token,
    customer_token,
    staff_assignment,
    db,
    client_org,
    admin_user,
):
    project = Project(org_id=client_org.id, name="Scoped SEO", created_by=admin_user.id)
    db.add(project)
    db.flush()
    task = ProjectTask(project_id=project.id, title="Content", status="open", is_client_visible=True)
    db.add(task)
    db.commit()
    db.refresh(task)

    staff_r = client.patch(
        f"/api/project-tasks/{task.id}/status",
        json={"status": "working"},
        headers=_auth(staff_token),
    )
    customer_r = client.patch(
        f"/api/project-tasks/{task.id}/status",
        json={"status": "completed"},
        headers=_auth(customer_token),
    )

    assert staff_r.status_code == 200, staff_r.text
    assert customer_r.status_code == 403


def test_admin_can_upload_and_download_project_document(client, admin_token, db, client_org, admin_user):
    project = Project(org_id=client_org.id, name="Docs SEO", visibility="customer_visible", created_by=admin_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    upload = client.post(
        f"/api/projects/{project.id}/documents",
        files={"file": ("brief.txt", b"SEO project brief", "text/plain")},
        headers=_auth(admin_token),
    )

    assert upload.status_code == 201, upload.text
    document = upload.json()
    assert document["file_name"] == "brief.txt"
    assert document["file_size"] == len(b"SEO project brief")
    assert document["sha256"]

    download = client.get(
        f"/api/projects/{project.id}/documents/{document['id']}/download",
        headers=_auth(admin_token),
    )

    assert download.status_code == 200, download.text
    assert download.content == b"SEO project brief"


def test_customer_can_list_visible_project_documents_but_cannot_upload(
    client,
    customer_token,
    admin_token,
    db,
    client_org,
    admin_user,
):
    project = Project(org_id=client_org.id, name="Customer Docs SEO", visibility="customer_visible", created_by=admin_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    upload = client.post(
        f"/api/projects/{project.id}/documents",
        data={"is_client_visible": "true"},
        files={"file": ("public.txt", b"Visible brief", "text/plain")},
        headers=_auth(admin_token),
    )
    assert upload.status_code == 201, upload.text

    listed = client.get(f"/api/projects/{project.id}/documents", headers=_auth(customer_token))
    forbidden = client.post(
        f"/api/projects/{project.id}/documents",
        files={"file": ("customer.txt", b"No upload", "text/plain")},
        headers=_auth(customer_token),
    )

    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["file_name"] == "public.txt"
    assert "uploader_email" not in listed.json()[0]
    assert forbidden.status_code == 403


def test_other_org_project_document_returns_404_for_customer(
    client,
    customer_token,
    admin_token,
    db,
    second_client_org,
    admin_user,
):
    project = Project(org_id=second_client_org.id, name="Other Docs SEO", visibility="customer_visible", created_by=admin_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    upload = client.post(
        f"/api/projects/{project.id}/documents",
        files={"file": ("other.txt", b"Other org", "text/plain")},
        headers=_auth(admin_token),
    )
    assert upload.status_code == 201, upload.text
    document = upload.json()

    listed = client.get(f"/api/projects/{project.id}/documents", headers=_auth(customer_token))
    downloaded = client.get(
        f"/api/projects/{project.id}/documents/{document['id']}/download",
        headers=_auth(customer_token),
    )

    assert listed.status_code == 404
    assert downloaded.status_code == 404
