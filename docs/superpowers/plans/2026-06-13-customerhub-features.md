# CustomerHub Feature Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 features to the CustomerHub helpdesk portal: hard-delete users, keyboard-aware pagination (top+bottom on every list), ticket↔project linking, project picker on the new-ticket form, and a task-first project detail layout.

**Architecture:** Backend changes (FastAPI+SQLAlchemy) come first so frontend can call real endpoints. Each part is self-contained and ships behind existing auth/RBAC guards. No new tables beyond a single `project_id` nullable FK on `tickets`.

**Tech Stack:** React 18 + Vite, FastAPI, SQLAlchemy + MariaDB, Alembic, Tailwind CSS v3, Heroicons, Framer Motion.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/api/users.py` | Modify | Add `DELETE /api/users/{id}` with 409 guard |
| `backend/app/models/ticket.py` | Modify | Add `project_id` nullable FK |
| `backend/app/schemas/ticket.py` | Modify | Add `project_id` to `TicketCreate`, `TicketOut`, `TicketDetailOut` |
| `backend/app/api/tickets.py` | Modify | Accept `project_id` in create/update, validate org match |
| `backend/app/api/projects.py` | Modify | Add `GET /api/projects/{id}/tickets` endpoint |
| `backend/alembic/versions/<new>.py` | Create | Migration: `ALTER TABLE tickets ADD COLUMN project_id` |
| `frontend/src/api/users.js` | Modify | Add `deleteUser(id)` function |
| `frontend/src/api/projects.js` | Modify | Add `getProjectTickets(projectId)` function |
| `frontend/src/components/ui/Pagination.jsx` | Modify | Add keyboard ← → navigation, accept `className` prop |
| `frontend/src/pages/admin/UsersPage.jsx` | Modify | Add trash icon + confirm modal + 409 toast |
| `frontend/src/pages/TicketListPage.jsx` | Modify | Replace inline pagination with `<Pagination>` component (top + bottom) |
| `frontend/src/pages/NewTicketPage.jsx` | Modify | Add project dropdown after org select |
| `frontend/src/pages/TicketDetailPage.jsx` | Modify | Show linked project badge |
| `frontend/src/pages/ProjectDetailPage.jsx` | Modify | Restructure to 60/40 layout; add linked-tickets section in sidebar |

---

## Task 1: Backend — DELETE /api/users/{id}

**Files:**
- Modify: `backend/app/api/users.py`

- [ ] **Step 1: Add the endpoint**

Append to `backend/app/api/users.py` (after the `get_login_history` function):

```python
@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Hard-delete a user. Returns 409 if the user has any tickets."""
    from app.models.ticket import Ticket
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    ticket_count = db.query(Ticket).filter(
        Ticket.raised_by == user_id,
        Ticket.is_deleted == False,  # noqa: E712
    ).count()
    if ticket_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete user: they have {ticket_count} open ticket(s). Deactivate instead.",
        )
    # Revoke sessions before deleting
    from app.models.user_session import UserSession
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_active.is_(True),
    ).update({"is_active": False, "revoked_at": now})
    blacklist_user_tokens(user_id, redis_client)
    db.delete(target)
    db.commit()
```

- [ ] **Step 2: Run backend tests**

```bash
cd /home/acm/helpdesk-system/backend && python -m pytest tests/ -x -q 2>&1 | tail -20
```
Expected: all tests pass, no failures.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/users.py
git commit -m "feat: add DELETE /api/users/{id} with 409 guard for tickets"
```

---

## Task 2: Frontend — deleteUser API + UsersPage trash icon + confirm modal

**Files:**
- Modify: `frontend/src/api/users.js`
- Modify: `frontend/src/pages/admin/UsersPage.jsx`

- [ ] **Step 1: Add deleteUser to the API module**

In `frontend/src/api/users.js`, append after the last export:

```js
export const deleteUser = (id) => client.delete(`/users/${id}`)
```

- [ ] **Step 2: Add imports to UsersPage**

At the top of `frontend/src/pages/admin/UsersPage.jsx`, the existing import from heroicons already imports several icons. Add `TrashIcon` to that import:

Find this line (it exists around line 9):
```js
import { KeyIcon, ClockIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline'
```
Replace with:
```js
import { KeyIcon, ClockIcon, CheckCircleIcon, XCircleIcon, TrashIcon } from '@heroicons/react/24/outline'
```

Then add `deleteUser` to the api import. Find:
```js
import { listUsers, createUser, updateUser, resetUserPassword, getUserLoginHistory } from '@/api/users'
```
Replace with:
```js
import { listUsers, createUser, updateUser, resetUserPassword, getUserLoginHistory, deleteUser } from '@/api/users'
```

- [ ] **Step 3: Add delete state and handler**

In the `UsersPage` component function body, find where other state declarations live (e.g., `const [resetModal, setResetModal] = useState(null)`). Add after them:

```js
const [deleteTarget, setDeleteTarget] = useState(null)   // user object to confirm delete
const [deleting, setDeleting] = useState(false)
```

Add the handler function (after `handleResetPassword` or similar):

```js
const handleDelete = async () => {
  if (!deleteTarget) return
  setDeleting(true)
  try {
    await deleteUser(deleteTarget.id)
    setDeleteTarget(null)
    addToast({ type: 'success', message: `User ${deleteTarget.email} deleted` })
    load()
  } catch (err) {
    const detail = err?.response?.data?.detail ?? err?.message ?? 'Delete failed'
    addToast({ type: 'error', message: detail })
    setDeleteTarget(null)
  } finally {
    setDeleting(false)
  }
}
```

- [ ] **Step 4: Add TrashIcon button to the actions column**

In the table row actions, find the existing action buttons (login history clock icon button). After that button, add:

```jsx
<button
  type="button"
  title="Delete user"
  onClick={() => setDeleteTarget(u)}
  className="p-1.5 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
>
  <TrashIcon className="w-4 h-4" aria-hidden="true" />
</button>
```

- [ ] **Step 5: Add confirm modal**

Find the closing `</div>` of the page's outer return (just before the final `}` of `UsersPage`). Before that closing tag, add the confirm modal:

```jsx
{deleteTarget && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
    <div className="bg-white rounded-2xl shadow-xl p-6 max-w-sm w-full mx-4 space-y-4">
      <h2 className="text-base font-semibold text-gray-900">Delete user?</h2>
      <p className="text-sm text-gray-600">
        This will permanently delete <strong>{deleteTarget.email}</strong> and cannot be undone.
        If they have open tickets, deletion will be blocked.
      </p>
      <div className="flex gap-3 justify-end">
        <button
          type="button"
          onClick={() => setDeleteTarget(null)}
          className="btn-secondary"
          disabled={deleting}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleting}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white transition-colors disabled:opacity-50"
        >
          {deleting ? 'Deleting…' : 'Delete permanently'}
        </button>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 6: Build and verify**

```bash
cd /home/acm/helpdesk-system/frontend && npm run build 2>&1 | tail -20
```
Expected: `✓ built in` with no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/users.js frontend/src/pages/admin/UsersPage.jsx
git commit -m "feat: add delete user button with confirm modal and 409 toast"
```

---

## Task 3: Keyboard-aware Pagination (top + bottom)

**Files:**
- Modify: `frontend/src/components/ui/Pagination.jsx`
- Modify: `frontend/src/pages/TicketListPage.jsx`
- Modify: `frontend/src/pages/admin/UsersPage.jsx`
- Modify: `frontend/src/pages/admin/InvoicesPage.jsx`
- Modify: `frontend/src/pages/admin/OrganizationsPage.jsx`
- Modify: `frontend/src/pages/admin/SubscriptionsPage.jsx`
- Modify: `frontend/src/pages/admin/ItemsPage.jsx`

- [ ] **Step 1: Add keyboard navigation to Pagination component**

Replace the entire contents of `frontend/src/components/ui/Pagination.jsx`:

```jsx
import { useEffect } from 'react'
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline'

export default function Pagination({ page, pages, total, perPage, onPage, className = '' }) {
  if (pages <= 1) return null
  const start = (page - 1) * perPage + 1
  const end = Math.min(page * perPage, total)

  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return
      if (e.key === 'ArrowLeft' && page > 1) onPage(page - 1)
      if (e.key === 'ArrowRight' && page < pages) onPage(page + 1)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [page, pages, onPage])

  return (
    <div className={`flex items-center justify-between px-4 py-3 border-t border-border ${className}`}>
      <p className="text-sm text-muted-foreground">
        Showing {start}–{end} of {total}
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Previous page"
        >
          <ChevronLeftIcon className="w-4 h-4" />
        </button>
        {getPageRange(page, pages).map((p, i) =>
          p === '...' ? (
            <span key={`ellipsis-${i}`} className="px-2 text-muted-foreground text-sm">…</span>
          ) : (
            <button
              key={p}
              onClick={() => onPage(p)}
              className={`w-8 h-8 rounded-md text-sm font-medium transition-colors ${
                p === page
                  ? 'bg-primary text-primary-foreground'
                  : 'text-foreground hover:bg-muted'
              }`}
            >
              {p}
            </button>
          )
        )}
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= pages}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Next page"
        >
          <ChevronRightIcon className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function getPageRange(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  if (current <= 4) return [1, 2, 3, 4, 5, '...', total]
  if (current >= total - 3) return [1, '...', total - 4, total - 3, total - 2, total - 1, total]
  return [1, '...', current - 1, current, current + 1, '...', total]
}
```

- [ ] **Step 2: Add top Pagination to each admin list page**

For each of these five admin pages (`UsersPage.jsx`, `InvoicesPage.jsx`, `OrganizationsPage.jsx`, `SubscriptionsPage.jsx`, `ItemsPage.jsx`):

Each page has a table wrapped in a container. Find the `<Pagination ... />` at the bottom of the table container. Add the same `<Pagination ... />` call immediately *before* the `<table>` element (or `<div className="overflow-x-auto">` that wraps the table).

Example pattern — find:
```jsx
<div className="overflow-x-auto">
  <table ...>
```
Replace with:
```jsx
<Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} className="border-t-0 border-b border-border" />
<div className="overflow-x-auto">
  <table ...>
```

(The exact surrounding code differs per file; use the same props already passed to the bottom `<Pagination>`.)

- [ ] **Step 3: Upgrade TicketListPage to use Pagination component**

In `frontend/src/pages/TicketListPage.jsx`:

a) Add import at top (with the other component imports):
```js
import Pagination from '@/components/ui/Pagination'
```

b) Find the inline `{/* Pagination */}` block (around line 358–380) and replace it with:
```jsx
<Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} />
```

c) Also add a top Pagination above the `<table>` (or `<div className="overflow-x-auto">`):
```jsx
<Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} className="border-t-0 border-b border-border" />
```

Note: check what variable name holds per_page in TicketListPage — it may be `PER_PAGE` constant or `perPage`. Use whatever is already defined.

- [ ] **Step 4: Build and run tests**

```bash
cd /home/acm/helpdesk-system/frontend && npm run build 2>&1 | tail -10
cd /home/acm/helpdesk-system/frontend && npx vitest run --reporter=verbose 2>&1 | tail -20
```
Expected: build succeeds, all tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Pagination.jsx frontend/src/pages/TicketListPage.jsx \
  frontend/src/pages/admin/UsersPage.jsx frontend/src/pages/admin/InvoicesPage.jsx \
  frontend/src/pages/admin/OrganizationsPage.jsx frontend/src/pages/admin/SubscriptionsPage.jsx \
  frontend/src/pages/admin/ItemsPage.jsx
git commit -m "feat: keyboard pagination (← →) and top+bottom pagination on all list pages"
```

---

## Task 4: Backend — Ticket↔Project linking (model + migration + schemas + API)

**Files:**
- Modify: `backend/app/models/ticket.py`
- Create: `backend/alembic/versions/<hash>_add_ticket_project_id.py`
- Modify: `backend/app/schemas/ticket.py`
- Modify: `backend/app/api/tickets.py`
- Modify: `backend/app/api/projects.py`

- [ ] **Step 1: Add project_id column to Ticket model**

In `backend/app/models/ticket.py`, find `service_id` column:
```python
    service_id = Column(BigInteger, ForeignKey("services.id"))
```
Add after it:
```python
    project_id = Column(BigInteger, ForeignKey("projects.id"), nullable=True)
```

- [ ] **Step 2: Generate Alembic migration**

```bash
cd /home/acm/helpdesk-system/backend && python -m alembic revision --autogenerate -m "add_ticket_project_id" 2>&1
```
Expected: creates a new file in `alembic/versions/`.

Verify the generated file has:
```python
op.add_column('tickets', sa.Column('project_id', sa.BigInteger(), sa.ForeignKey('projects.id'), nullable=True))
```

If the autogenerate missed it (sometimes happens with nullable FKs), edit the file to add it manually.

- [ ] **Step 3: Run migration**

```bash
cd /home/acm/helpdesk-system/backend && python -m alembic upgrade head 2>&1
```
Expected: `Running upgrade ... -> <revision>`.

- [ ] **Step 4: Update schemas**

In `backend/app/schemas/ticket.py`:

a) Add `project_id: Optional[int] = None` to `TicketCreate`:
```python
class TicketCreate(BaseModel):
    org_id: int
    service_id: Optional[int] = None
    project_id: Optional[int] = None   # <-- add this line
    subject: str
    ...
```

b) Add `project_id: Optional[int] = None` to `TicketUpdate` (if it exists; add similarly).

c) Add `project_id: Optional[int] = None` to `TicketOut` and `TicketDetailOut`.

- [ ] **Step 5: Update ticket create endpoint — validate project org match**

In `backend/app/api/tickets.py`, in the `create_ticket` function, after the service validation block (around line 80), add:

```python
    # Validate project belongs to same org (when project_id is provided)
    if payload.project_id is not None:
        from app.models.project import Project
        project = db.query(Project).filter(Project.id == payload.project_id).first()
        if not project or project.org_id != payload.org_id:
            raise HTTPException(status_code=422, detail="Project does not belong to the specified organization")
```

Then in the `Ticket(...)` constructor call, add:
```python
        project_id=payload.project_id,
```

- [ ] **Step 6: Update ticket detail response to include project_id**

In `backend/app/api/tickets.py`, in the `get_ticket` function's `ticket_dict`, add `"project_id": ticket.project_id,` alongside the other fields.

- [ ] **Step 7: Add GET /api/projects/{project_id}/tickets endpoint**

In `backend/app/api/projects.py`, after the existing `list_project_tasks` endpoint, add:

```python
@router.get("/{project_id}/tickets")
def list_project_tickets(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all non-deleted tickets linked to this project."""
    project = assert_project_access(project_id, user, db)
    from app.models.ticket import Ticket
    query = db.query(Ticket).filter(
        Ticket.project_id == project.id,
        Ticket.is_deleted == False,  # noqa: E712
    )
    # Customers can only see their org's tickets
    if user.role == "customer":
        query = query.filter(Ticket.org_id == user.org_id)
    tickets = query.order_by(Ticket.created_at.desc()).limit(50).all()
    from app.api.tickets import _enrich_tickets
    enriched = _enrich_tickets(tickets, db)
    return [
        {
            "id": t.id,
            "subject": t.subject,
            "status": t.status,
            "priority": t.priority,
            "created_at": t.created_at,
        }
        for t in enriched
    ]
```

- [ ] **Step 8: Run backend tests**

```bash
cd /home/acm/helpdesk-system/backend && python -m pytest tests/ -x -q 2>&1 | tail -20
```
Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/ticket.py backend/app/schemas/ticket.py \
  backend/app/api/tickets.py backend/app/api/projects.py \
  backend/alembic/versions/
git commit -m "feat: add project_id FK to tickets + GET /api/projects/{id}/tickets"
```

---

## Task 4b: Backend — scope_projects: staff visibility via assigned ticket

**Files:**
- Modify: `backend/app/core/scoping.py`
- Modify: `backend/tests/test_scoping.py`

**Context:** A staff member who is not assigned to a project's org but has a ticket assigned to them where `ticket.project_id == project.id` should be able to view that project. This is implemented by extending the OR condition in `scope_projects()` — no new table required.

**Depends on:** Task 4 (migration must run first so `Ticket.project_id` column exists in DB).

- [ ] **Step 1: Write the failing test first**

Append to `backend/tests/test_scoping.py`:

```python
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
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
cd /home/acm/helpdesk-system/backend && python -m pytest tests/test_scoping.py::test_staff_sees_project_via_assigned_ticket tests/test_scoping.py::test_staff_does_not_see_unlinked_project -v 2>&1 | tail -20
```
Expected: FAIL — `scope_projects` doesn't have the OR condition yet (and `Ticket.project_id` exists from Task 4 migration).

- [ ] **Step 3: Update scope_projects in scoping.py**

In `backend/app/core/scoping.py`, replace the staff branch of `scope_projects`:

Find:
```python
def scope_projects(query, user: User, db: Session, include_internal: bool = False):
    """
    Apply SEO project visibility rules.

    - Admin: unrestricted
    - Staff: projects in assigned organisations
    - Customer: own org and customer-visible projects only
    """
    if user.role == "admin":
        return query
    if user.role == "customer":
        return query.filter(
            Project.org_id == user.org_id,
            Project.visibility == "customer_visible",
        )
    org_ids = get_accessible_org_ids(user, db)
    return query.filter(Project.org_id.in_(org_ids or []))
```

Replace with:
```python
def scope_projects(query, user: User, db: Session, include_internal: bool = False):
    """
    Apply SEO project visibility rules.

    - Admin: unrestricted
    - Staff: projects in assigned orgs OR projects where staff has an assigned ticket
    - Customer: own org and customer-visible projects only
    """
    if user.role == "admin":
        return query
    if user.role == "customer":
        return query.filter(
            Project.org_id == user.org_id,
            Project.visibility == "customer_visible",
        )
    # staff: assigned-org projects OR projects linked via an assigned ticket
    org_ids = get_accessible_org_ids(user, db)
    linked_via_ticket = (
        db.query(Ticket.project_id)
        .filter(
            Ticket.assignee_id == user.id,
            Ticket.project_id.isnot(None),
            Ticket.is_deleted == False,  # noqa: E712
        )
        .subquery()
    )
    return query.filter(
        or_(
            Project.org_id.in_(org_ids or []),
            Project.id.in_(linked_via_ticket),
        )
    )
```

- [ ] **Step 4: Run the new tests — expect pass**

```bash
cd /home/acm/helpdesk-system/backend && python -m pytest tests/test_scoping.py::test_staff_sees_project_via_assigned_ticket tests/test_scoping.py::test_staff_does_not_see_unlinked_project -v 2>&1 | tail -20
```
Expected: both PASS.

- [ ] **Step 5: Run full backend test suite — no regressions**

```bash
cd /home/acm/helpdesk-system/backend && python -m pytest tests/ -q 2>&1 | tail -20
```
Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/scoping.py backend/tests/test_scoping.py
git commit -m "feat: staff can see project via assigned ticket (scope_projects OR condition)"
```

---

⏸️ **PAUSE HERE — await user review before continuing to Task 5.**

---

## Task 5: Frontend — Project picker in NewTicketPage + project badge in TicketDetailPage

**Files:**
- Modify: `frontend/src/api/projects.js`
- Modify: `frontend/src/pages/NewTicketPage.jsx`
- Modify: `frontend/src/pages/TicketDetailPage.jsx`

- [ ] **Step 1: Add getProjectTickets to projects API**

In `frontend/src/api/projects.js`, append:
```js
export const getProjectTickets = (projectId) => client.get(`/projects/${projectId}/tickets`).then(r => r.data)
```

Also ensure there is a `listProjects` function that accepts `{ org_id }` filter. Check `frontend/src/api/projects.js` for its current signature. If it already exists as `listProjects`, this step is done. If it accepts a params object and forwards to the backend, that's fine. If not, add:
```js
export const listProjects = (params = {}) => client.get('/projects', { params }).then(r => r.data)
```

- [ ] **Step 2: Add project state and load effect to NewTicketPage**

In `frontend/src/pages/NewTicketPage.jsx`, in the existing imports from `@/api/projects.js` (or create a new import), add `listProjects`:
```js
import { listProjects } from '@/api/projects'
```

In the component body, after the `services` state declarations:
```js
const [projects, setProjects] = useState([])
const [projectsLoading, setProjectsLoading] = useState(false)
const [selectedProjectId, setSelectedProjectId] = useState(null)
```

After the existing `useEffect` that loads services when org changes, add:
```js
// Load projects when org changes
useEffect(() => {
  if (!selectedOrgId) { setProjects([]); setSelectedProjectId(null); return }
  setProjectsLoading(true)
  setSelectedProjectId(null)
  listProjects({ org_id: selectedOrgId, per_page: 100 })
    .then((data) => setProjects(data?.items ?? []))
    .catch(() => setProjects([]))
    .finally(() => setProjectsLoading(false))
}, [selectedOrgId])
```

- [ ] **Step 3: Add project dropdown to the form**

In NewTicketPage's JSX, inside `FormBlock` step "1" (Organization & Service), after the Service `<Field>`, add:

```jsx
{projects.length > 0 && (
  <Field label="Link to Project" hint="Optional — link this ticket to an ongoing SEO project">
    <StyledSelect
      value={selectedProjectId ?? ''}
      onChange={(e) => setSelectedProjectId(Number(e.target.value) || null)}
      disabled={projectsLoading}
    >
      <option value="">{projectsLoading ? 'Loading projects…' : 'No project (optional)'}</option>
      {projects.map((p) => (
        <option key={p.id} value={p.id}>{p.name}</option>
      ))}
    </StyledSelect>
  </Field>
)}
```

- [ ] **Step 4: Pass project_id to submit**

In `handleSubmit`, in the `await submit({...})` call, add:
```js
...(selectedProjectId ? { project_id: selectedProjectId } : {}),
```

- [ ] **Step 5: Show project badge in TicketDetailPage**

In `frontend/src/pages/TicketDetailPage.jsx`, find the ticket metadata section (where org, service, priority, status are displayed). After the service badge (or wherever org_name is shown), add a project link when `ticket.project_id` is defined:

```jsx
{ticket.project_id && (
  <Link
    to={`/projects/${ticket.project_id}`}
    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-violet-50 text-violet-700 hover:bg-violet-100 transition-colors"
  >
    <FolderIcon className="w-3.5 h-3.5" aria-hidden="true" />
    Project #{ticket.project_id}
  </Link>
)}
```

(Import `FolderIcon` from heroicons if not already imported; import `Link` from react-router-dom if not already imported.)

- [ ] **Step 6: Build and test**

```bash
cd /home/acm/helpdesk-system/frontend && npm run build 2>&1 | tail -10
```
Expected: build succeeds with no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/projects.js frontend/src/pages/NewTicketPage.jsx frontend/src/pages/TicketDetailPage.jsx
git commit -m "feat: project picker in new ticket form + project badge in ticket detail"
```

---

## Task 6: Frontend — Add linked-tickets section to ProjectDetailPage

**Files:**
- Modify: `frontend/src/pages/ProjectDetailPage.jsx`

- [ ] **Step 1: Import getProjectTickets and Link**

In `frontend/src/pages/ProjectDetailPage.jsx`, add `getProjectTickets` to the projects import:
```js
import {
  cancelProject,
  cancelProjectTask,
  createProjectTask,
  downloadProjectDocument,
  getProject,
  getProjectTickets,   // <-- add
  listProjectDocuments,
  listProjectTasks,
  updateProjectTask,
  updateProjectTaskStatus,
  uploadProjectDocument,
} from '@/api/projects'
```

Add `Link` from react-router-dom if not already imported:
```js
import { Link, useParams } from 'react-router-dom'
```

- [ ] **Step 2: Add tickets state and loading**

In the `ProjectDetailPage` component, add state after the `documents` state:
```js
const [linkedTickets, setLinkedTickets] = useState([])
```

In the `load` callback (the `Promise.all([...])` block), add `getProjectTickets(id).catch(() => [])` to the array and destructure it:
```js
const [projectData, taskData, documentData, ticketData] = await Promise.all([
  getProject(id),
  listProjectTasks(id),
  listProjectDocuments(id).catch(() => []),
  getProjectTickets(id).catch(() => []),
])
setProject(projectData)
setTasks(taskData)
setDocuments(documentData)
setLinkedTickets(ticketData)
```

- [ ] **Step 3: Add LinkedTicketsPanel component**

Before the `export default function ProjectDetailPage()` line, add:

```jsx
const TICKET_STATUS_BADGE = {
  'Open':        'bg-blue-50 text-blue-700',
  'In Progress': 'bg-amber-50 text-amber-700',
  'Waiting':     'bg-purple-50 text-purple-700',
  'Resolved':    'bg-green-50 text-green-700',
  'Closed':      'bg-gray-100 text-gray-500',
}

function LinkedTicketsPanel({ tickets }) {
  return (
    <WorkspaceCard title="Linked Tickets" icon={DocumentTextIcon}>
      {tickets.length === 0 ? (
        <EmptyPanel>No tickets linked to this project yet.</EmptyPanel>
      ) : (
        <div className="divide-y divide-slate-100 max-h-60 overflow-y-auto">
          {tickets.map((t) => (
            <div key={t.id} className="px-5 py-3 flex items-center justify-between gap-3">
              <Link
                to={`/tickets/${t.id}`}
                className="text-sm font-medium text-slate-900 hover:text-amber-600 truncate flex-1"
              >
                #{t.id} {t.subject}
              </Link>
              <span className={`flex-shrink-0 px-2 py-0.5 rounded-full text-xs font-medium ${TICKET_STATUS_BADGE[t.status] ?? 'bg-gray-100 text-gray-500'}`}>
                {t.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </WorkspaceCard>
  )
}
```

- [ ] **Step 4: Add LinkedTicketsPanel to the aside**

In the `<aside>` section (at the bottom of the main grid), add the panel:
```jsx
<aside className="space-y-5">
  <LinkedTicketsPanel tickets={linkedTickets} />   {/* <-- add this */}
  <NotesPanel tasks={tasks} isCustomer={isCustomer} />
  <ActivityPanel project={project} tasks={tasks} />
</aside>
```

- [ ] **Step 5: Build and verify**

```bash
cd /home/acm/helpdesk-system/frontend && npm run build 2>&1 | tail -10
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ProjectDetailPage.jsx
git commit -m "feat: show linked tickets in project detail sidebar"
```

---

## Task 7: Redesign ProjectDetailPage — tasks-first 60/40 layout

**Files:**
- Modify: `frontend/src/pages/ProjectDetailPage.jsx`

The current layout has a wide grid for the whole page and mixes progress/team/about/docs into `<main>`, with notes/activity in `<aside>`. The redesign puts the task list (+ task form) as the dominant left column and moves progress, team, about, docs, notes, activity all into a right sidebar.

- [ ] **Step 1: Restructure the main content grid**

Find the current main+aside grid wrapper:
```jsx
<div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_340px]">
  <main className="space-y-5 min-w-0">
    <div className={`grid grid-cols-1 gap-5 ${!isCustomer ? 'xl:grid-cols-2' : ''}`}>
      <WorkspaceCard title="Progress" ...>
      ...
      {!isCustomer && <TeamMembers ... />}
    </div>
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
      <WorkspaceCard title="About Project" ...>
      <DocumentsPanel ... />
    </div>
    {!isCustomer && <div ref={taskFormRef}><TaskCreateForm ... /></div>}
    <WorkspaceCard title="Task List" ...>
  </main>
  <aside className="space-y-5">
    <NotesPanel ... />
    <ActivityPanel ... />
  </aside>
</div>
```

Replace the entire block (from `<div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_340px]">` to its closing `</div>`) with:

```jsx
<div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
  {/* Left column — tasks primary */}
  <main className="space-y-5 min-w-0">
    {!isCustomer && <div ref={taskFormRef}><TaskCreateForm onCreate={addTask} /></div>}
    <WorkspaceCard title="Task List" icon={CheckCircleIcon} action={<span className="text-xs text-slate-500">{tasks.length} shown</span>}>
      {tasks.length === 0 ? (
        <EmptyPanel>{isCustomer ? 'No customer-visible tasks are available yet.' : 'No tasks have been created yet.'}</EmptyPanel>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-100 bg-slate-50">
              <tr>
                <th className="w-10 px-4 py-3" />
                <th className="text-left px-4 py-3 font-medium text-slate-500">Task</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Assignee</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Priority</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Status</th>
                {!isCustomer && <th className="text-left px-4 py-3 font-medium text-slate-500">Client</th>}
                <th className="text-left px-4 py-3 font-medium text-slate-500">Deadline</th>
                {!isCustomer && <th className="text-left px-4 py-3 font-medium text-slate-500">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {tasks.map(task => (
                <Fragment key={task.id}>
                <tr className="hover:bg-slate-50/70">
                  <td className="px-4 py-3">
                    <span className={`flex h-5 w-5 items-center justify-center rounded-full border ${task.status === 'completed' ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-300 text-transparent'}`}>
                      <CheckCircleIcon className="h-4 w-4" aria-hidden="true" />
                    </span>
                  </td>
                  <td className="px-4 py-3 min-w-64">
                    <p className="font-medium text-slate-900">{task.title}</p>
                    {task.description && <p className="text-xs text-slate-500 mt-0.5">{task.description}</p>}
                    <p className="mt-1 text-xs text-slate-400">{TASK_TYPES.find(([value]) => value === task.task_type)?.[1] ?? task.task_type}</p>
                    {!isCustomer && task.internal_note && <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1 mt-2">Internal: {task.internal_note}</p>}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{isCustomer ? (task.assignee_name || '—') : (task.assignee_name || task.assignee_email || '—')}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${PRIORITY_CLASSES[task.priority] ?? PRIORITY_CLASSES.medium}`}>{task.priority}</span>
                  </td>
                  <td className="px-4 py-3"><TaskStatusBadge status={task.status} /></td>
                  {!isCustomer && <td className="px-4 py-3">{task.is_client_visible ? 'Visible' : 'Internal'}</td>}
                  <td className="px-4 py-3 text-slate-500">
                    <span className="inline-flex items-center gap-1">
                      <CalendarDaysIcon className="w-3.5 h-3.5" aria-hidden="true" />
                      {fmtDate(task.due_date)}
                    </span>
                  </td>
                  {!isCustomer && (
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                      <select
                        value={task.status}
                        disabled={updatingTask === task.id || task.status === 'cancelled'}
                        onChange={e => changeStatus(task.id, e.target.value)}
                        className="px-2 py-1 border border-slate-200 rounded bg-white text-xs"
                      >
                        {TASK_STATUSES.map(status => <option key={status} value={status}>{status}</option>)}
                      </select>
                      <button
                        type="button"
                        onClick={() => setEditingTaskId(task.id)}
                        className="rounded border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-100"
                        title="Edit task"
                      >
                        <PencilSquareIcon className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        onClick={() => cancelTask(task.id)}
                        disabled={taskActionId === task.id || task.status === 'cancelled'}
                        className="rounded border border-red-100 p-1.5 text-red-600 hover:bg-red-50 disabled:opacity-40"
                        title="Cancel task"
                      >
                        <XMarkIcon className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                      </div>
                    </td>
                  )}
                </tr>
                {!isCustomer && editingTaskId === task.id && (
                  <TaskEditRow
                    key={`${task.id}-edit`}
                    task={task}
                    onCancel={() => setEditingTaskId(null)}
                    onSave={(payload) => saveTask(task.id, payload)}
                  />
                )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </WorkspaceCard>
  </main>

  {/* Right sidebar — supporting info */}
  <aside className="space-y-5">
    <WorkspaceCard title="Progress" icon={CheckCircleIcon}>
      <div className="px-5 py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <span className="text-3xl font-bold text-slate-900">{Math.round(Number(project.progress_percent ?? 0))}%</span>
            <p className="mt-1 text-xs text-slate-500">Completed active tasks</p>
          </div>
          <StatusBadge status={project.status} />
        </div>
        <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-amber-500" style={{ width: `${Math.max(0, Math.min(100, Number(project.progress_percent ?? 0)))}%` }} />
        </div>
      </div>
    </WorkspaceCard>

    {!isCustomer && <TeamMembers project={project} tasks={tasks} />}

    <LinkedTicketsPanel tickets={linkedTickets} />

    <WorkspaceCard title="About Project" icon={FolderIcon}>
      <div className="px-5 py-5">
        <p className="text-sm leading-6 text-slate-600 whitespace-pre-wrap">{project.description || 'No project description has been added yet.'}</p>
        <dl className="mt-5 grid grid-cols-1 gap-3 text-sm">
          {!isCustomer && project.org_name && (
            <div className="rounded-lg bg-muted/30 px-3 py-2">
              <dt className="text-xs text-muted-foreground">Organisation</dt>
              <dd className="font-medium text-foreground truncate">{project.org_name}</dd>
            </div>
          )}
          <div className="rounded-lg bg-muted/30 px-3 py-2">
            <dt className="text-xs text-muted-foreground">Start date</dt>
            <dd className="font-medium text-foreground">{fmtDate(project.start_date)}</dd>
          </div>
          <div className={`rounded-lg px-3 py-2 ${projectOverdue ? 'border border-red-100 bg-red-50' : 'bg-muted/30'}`}>
            <dt className="text-xs text-muted-foreground">Deadline</dt>
            <dd className={`font-medium ${projectOverdue ? 'text-red-700' : 'text-foreground'}`}>
              {fmtDate(project.due_date)}
              {projectOverdue && <span className="ml-2 text-xs font-semibold">Overdue</span>}
            </dd>
          </div>
          {!isCustomer && project.project_manager_name && (
            <div className="rounded-lg bg-muted/30 px-3 py-2">
              <dt className="text-xs text-muted-foreground">Project manager</dt>
              <dd className="font-medium text-foreground truncate">{project.project_manager_name}</dd>
            </div>
          )}
        </dl>
      </div>
    </WorkspaceCard>

    <DocumentsPanel
      projectId={id}
      documents={documents}
      loading={documentsLoading}
      error={documentsError}
      canUpload={!isCustomer}
      onUpload={uploadDocument}
      onDownload={downloadProjectDocument}
    />

    <NotesPanel tasks={tasks} isCustomer={isCustomer} />
    <ActivityPanel project={project} tasks={tasks} />
  </aside>
</div>
```

- [ ] **Step 2: Build and verify**

```bash
cd /home/acm/helpdesk-system/frontend && npm run build 2>&1 | tail -10
```
Expected: build succeeds, no TypeScript/JSX errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectDetailPage.jsx
git commit -m "feat: redesign project detail — task-first 60/40 layout with supporting sidebar"
```

---

⏸️ **PAUSE HERE — await user review before continuing to Task 8.**

---

## Task 8: Final checks

- [ ] **Step 1: Run full backend test suite**

```bash
cd /home/acm/helpdesk-system/backend && python -m pytest tests/ -q 2>&1 | tail -20
```
Expected: all tests pass.

- [ ] **Step 2: Run full frontend test suite**

```bash
cd /home/acm/helpdesk-system/frontend && npx vitest run --reporter=verbose 2>&1 | tail -30
```
Expected: all tests pass (44/44 minimum).

- [ ] **Step 3: Production build**

```bash
cd /home/acm/helpdesk-system/frontend && npm run build 2>&1 | tail -10
```
Expected: `✓ built in` with no errors or warnings about missing modules.

- [ ] **Step 4: Smoke-check backend starts**

```bash
cd /home/acm/helpdesk-system/backend && timeout 8 python -m uvicorn app.main:app --port 8099 2>&1 | tail -10
```
Expected: `Application startup complete` (process times out normally after 8s).

---

## Self-Review Checklist

**Spec coverage:**
- [x] Part 1 (delete user): Task 1 (backend) + Task 2 (frontend)
- [x] Part 2 (pagination): Task 3
- [x] Part 3a (project_id FK + migration + validation): Task 4
- [x] Part 3b (auto-add assignee to project team): **intentionally skipped** — no `project_members` table exists; team is derived dynamically from `tasks.assignee_id`. Creating a new table is out of scope per YAGNI.
- [x] Part 3c (project link badge in ticket detail): Task 5 Step 5
- [x] Part 3d (GET /api/projects/{id}/tickets + section in project detail): Task 4 Step 7 + Task 6
- [x] Part 4 (project dropdown in new ticket form): Task 5 Steps 2–4
- [x] Part 5 (project detail redesign): Task 7
- [x] Part 6 (final checks): Task 8

**Known deviations from spec:**
- Part 3b (auto-add team) replaced by Task 4b: instead of a `project_members` table, `scope_projects` now grants staff visibility into any project where they have an assigned ticket. The "team" in the UI is still derived dynamically from task assignees.
- Project badge in TicketDetailPage shows `Project #ID` (no name) to avoid an extra API call; the name could be fetched if desired.
