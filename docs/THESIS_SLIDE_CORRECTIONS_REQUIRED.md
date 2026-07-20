# Thesis and slide corrections required

The thesis PDF and PowerPoint were reviewed read-only and were not modified.

## 1. Statements now implemented and valid

- Heartbeat-backed staff presence contributes 20 assignment points.
- Workload combines active ticket and project-task assignments.
- Initial assignment does not wait for Groq.
- High-confidence classification can trigger a guarded recommendation or early reassignment.
- SLA sends transition alerts and hourly-limited reminders.
- AI reply output remains a staff-reviewed draft.
- Central tenant scoping and organisation/project assignment eligibility are enforced.

## 2. Statements still outdated

- Replace online equals activity/login within 30 minutes with Redis heartbeat presence: 30-second heartbeat and 90-second TTL defaults.
- Replace AI category is used immediately during creation: initial skill uses ticket_type, classification runs after commit, and guarded reevaluation may then use AI category.
- Replace any fixed 617-test claim with the actual final test report.
- Four Railway services deployed is not verifiable from local source inspection.
- Strict atomic service-subscription lifecycle pairing overstates the current creation transaction boundary.

## 3. Statements deliberately rejected

- Direct assignment across organisations, because assignment cannot grant tenant access.
- last_login_at as online presence.
- Automatic AI priority changes or autonomous customer replies without evidence and human control.
- AI reassignment when Redis lock ownership cannot be proven.

## 4. Claims requiring future production evidence

- Concurrent capacity at 10, 25, 50 and 100 users.
- P95/P99 latency and sustainable RPS.
- Live Railway topology and availability.
- AI category/priority accuracy and reply/summary quality.
- A Cohen's kappa value from a retained double-rated dataset.

## 5. Exact recommended replacement wording

### Assignment / slide 14

“Eligible active staff are filtered by organisation and, when configured, explicit project membership. The deterministic 100-point score combines workload (40), tenant-scoped historical skill with cold-start protection (40), and Redis heartbeat presence (20). Equal scores prefer never-assigned and least-recently-assigned staff.”

### SLA / slide 15

“Database state transitions trigger immediate red or breached alerts. A per-ticket, per-state, per-recipient Redis TTL permits at most one same-state reminder per hour. If Redis is unavailable, first transition alerts still persist while uncertain repeats are skipped.”

Remove color-warning prose from the key idea. Explain recipients and repeat behavior.

### AI safety and operation / slide 17

“Customer-controlled text is authorised and tenant-scoped, then sanitised before the Celery task calls Groq. Classification, reply drafting and summary use separate system instructions and bounded untrusted input. Ticket creation never waits for AI. A high-confidence category can create a guarded routing recommendation; manual, handled, old or active-project tickets cannot be reassigned.”

Evaluation panel wording:

“Two experts independently label the same n tickets. Observed agreement is Po = diagonal agreements / n. Expected chance agreement is Pe = sum over categories of p1(c) x p2(c). Cohen's kappa = (Po - Pe) / (1 - Pe). The manual result is cross-checked with scikit-learn. Kappa measures inter-rater reliability, not model accuracy; report n, Po, Pe and kappa only from the retained rating file.”

Do not show an unsupported numeric kappa. Make Po, Pe and kappa clear enough to defend, while operational AI safety and fail-graceful behavior remain the main implementation evidence.

### Final summary / slide 19

“CustomerHub implements tenant-scoped helpdesk workflows, deterministic explainable assignment, asynchronous human-controlled AI assistance, SLA pause/reminder semantics, durable notifications, billing and project links. Verification uses the current automated test report and a reproducible load-test harness; production capacity remains future evidence.”

Keep the test count small or omit it. Slide 19 is a system-wide conclusion.

### Performance / slide 20

“Sequential measurements describe only the tested requests and are not a concurrency or capacity claim. Locust profiles for 10, 25, 50 and 100 users are prepared for an isolated environment; report RPS, median, P95, P99 and errors after an authorised run.”
