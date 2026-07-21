# 10-user load-test before/after

## Current status

The rerun has not been executed. This file is a reporting template plus the recorded failed baseline; no performance improvement is claimed.

| Metric | Before (`core-10-failed`) | After |
|---|---:|---:|
| Requests | 726 | pending |
| HTTP 429 | 123 | pending |
| HTTP 500 | 8 | pending |
| MySQL deadlocks | 8 observed | pending |
| External Groq calls | yes, unintended | must be 0 |
| External email deliveries | yes, unintended | must be 0 |
| Error rate | 18.04% | must be <1% |
| Overall P95 | 4.2 s | pending |
| Overall P99 | 15 s | pending |
| Ticket-create P95 | 26 s | pending |

Before environment: local Docker, MariaDB 10.11.17, Redis 7.4.9, one Uvicorn process, default SQLAlchemy pool 5 plus max overflow 10, AI/email enabled accidentally in backend and worker.

After environment must use `LOAD_TEST_MODE=true`, `ALLOW_LOAD_TEST=true`, a dedicated `LOAD_TEST_KEY`, test organisation, AI/email/IMAP/Google/payment disabled in the backend and worker, and the preflight script before Locust. The 429 comparison must state the approved per-user load-test limiter policy.

Do not run 25/50/100 users from this task.
