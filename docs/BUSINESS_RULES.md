# CustomerHub business rules

## Tenant isolation

All organisation-scoped reads use central scoping and out-of-scope IDs return 404. Assignment does not grant access: staff must already belong to the ticket organisation. Explicit project staff/manager membership narrows eligibility; an empty project pool falls back to organisation staff. Customers never receive internal notes.

## Assignment

Candidate set: active organisation staff, restricted to explicit project staff/manager members when present.

Workload units equal active ticket assignments plus active project-task assignments. Active ticket states are Open, In Progress and Waiting. Active task states are open, working and review. Terminal work is excluded.

W_i = 40 x (1 - load_i / max(1, maximum_load)). An all-zero pool gives every candidate 40 workload points.

Skill is deterministic, not machine learning: S_i = 0.7 x historical_i + 0.3 x cold_start_i, capped at 40. History includes only Resolved/Closed tickets in the same organisation. The latest valid AI category is used when present; otherwise human ticket_type is used.

Presence contributes 20 only while the Redis heartbeat key presence:user:{id} exists. It is never inferred from login time. Redis failure gives a neutral zero without failing ticket creation.

Total_i = workload_i + skill_i + presence_i. Ties prefer never-assigned users, then oldest last_assigned_at, then stable user ID.

## Two-stage AI routing

Initial ownership is assigned immediately from available data; ticket creation commits before Celery contacts Groq. Classification may later trigger evaluation. Suggest mode records a recommendation. Auto mode may change ownership only when the ticket is automatic, Open, young enough, untouched by staff, not manually reassigned, not active project work, above confidence and improvement thresholds, and the organisation lock is held.

AI category can support routing. Predicted priority is advisory. Reply suggestions are drafts and are never sent automatically. Authorisation and tenant scoping occur before sanitisation and prompt construction.

## SLA

Waiting pauses effective SLA time and leaving Waiting extends deadlines by accumulated pause duration. Entering red immediately alerts the assignee. Entering breached immediately alerts active administrators. Same-state reminders require an expired per-recipient Redis TTL. Redis failure preserves transition alerts and suppresses uncertain repeats.

## Failure boundaries

Groq failure does not block ticketing, replies, billing or projects. Presence failure means zero presence points. Reminder Redis failure means no uncertain repeat. Pub/Sub failure does not roll back durable notifications or business data.
