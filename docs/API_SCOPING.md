# API Scoping

## Status Codes
- Use `403` when the authenticated role cannot use an endpoint at all.
- Use `404` when a record is missing or outside the caller's allowed scope.

## Central Helpers
- `get_accessible_org_ids(user, db)` returns `None` for admin, assigned org ids for staff, and the customer org id for customers.
- `scope_query(query, model, user, db)` applies generic `org_id` filtering.
- `scope_tickets(query, user, db)` applies ticket-specific staff assignment and customer ownership rules.
- `get_ticket_in_scope(ticket_id, user, db)` returns a visible non-deleted ticket or raises 404.
- `assert_org_access(org_id, user, db)` raises 404 for out-of-scope org resources.

## Resource Rules
- Tickets: admin all; staff assigned orgs or direct assignee; customer own raised tickets only.
- Replies: customers see only public replies; staff/admin see internal notes.
- Attachments: visibility follows the parent ticket.
- Invoices and subscriptions: visibility follows `org_id`.
- Services: visibility follows `org_id`.
- Notifications: visibility follows `user_id`.
- Analytics: ticket analytics follow ticket scope; revenue analytics are admin-only.
- Staff assignments: admin-only.
- Admin email poll: admin-only and rate-limited.

## SEO Project & Task Rules
- Projects: admin all; staff assigned organisations; customer own org only when `visibility = customer_visible`.
- Project tasks: admin all; staff tasks under assigned-org projects; customer only `is_client_visible = true` tasks under customer-visible projects.
- Customers are read-only for projects and tasks. Create, update, status change, and cancel endpoints return `403`.
- Out-of-scope project or task IDs return `404`, including internal projects/tasks hidden from customers.
- Customer responses must not include `internal_note`, `created_by`, or staff assignee email.
- Progress is computed from tasks: cancelled tasks are excluded; completed active tasks count toward the percentage.
