# Implementation changelog

## 2026-07-21 - Presence, assignment, AI routing and SLA reliability

- Added Redis heartbeat presence with 90-second TTL and 30-second frontend heartbeat defaults. Socket identity, not client payload, determines the user.
- Assignment now sums active ticket and project-task assignments, excludes terminal work, and uses batched workload/skill/presence reads.
- Historical skill is limited to the ticket organisation and uses latest valid category or human ticket type.
- Candidate eligibility enforces organisation assignment and explicit project membership. Direct assignment no longer grants cross-tenant visibility.
- Tie-breaking is deterministic: score, never-assigned, oldest last_assigned_at, stable user ID.
- Assignment locking uses random ownership tokens and compare-and-delete release.
- Ticket creation remains independent of Groq. Post-classification routing defaults to recommendation and supports guarded auto mode.
- AI reevaluation blocks manual, handled, old, non-open, low-confidence and active-project tickets and records idempotent activities.
- Groq errors are transient or permanent; only timeout, network, 429 and 5xx are retried.
- SLA combines immediate transitions with TTL-limited same-state reminders.
- Admin sidebar shows workload, skill, presence, total and assignment source.
- Added safe Locust personas and operational documentation.

No migration was required. Redis stores ephemeral state and the existing ticket activity table stores AI evaluation audit/idempotency data.
