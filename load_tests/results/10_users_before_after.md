# 10-user load-test before/after

Environment: local Docker load-test stack, 10 users, spawn rate 2 users/s,
duration 5 minutes, think time 1–5 seconds. The rerun used a dedicated MariaDB
database and Redis instance, with no Celery Beat.

| Metric | Original run | Rerun |
|---|---:|---:|
| Requests | 726 | 1,184 |
| Failures | 131 | 125 |
| Error rate | 18.04% | 10.56% |
| HTTP 429 | 123 | 125 |
| HTTP 500 | 8 | 0 |
| MySQL deadlocks | 8 | 0 observed |
| Overall P95 | 4.2 s | 100 ms |
| Overall P99 | 15 s | 440 ms |
| Ticket-create failures | 8/39 | 0/46 |
| Ticket-create P95 | 26 s | 740 ms |
| Real Groq calls | occurred | 0 observed |
| Real email delivery | occurred | 0 observed |

## Interpretation

The isolated runtime removed the original MySQL deadlocks, HTTP 500 responses,
and external-provider exposure. The run does **not** pass the error-rate gate:
all 125 failures were `GET /api/tickets` HTTP 429 responses.

The current Locust harness reuses one persona token across multiple virtual
users. The authenticated rate limiter therefore correctly groups those
requests under the same user identity. This is a workload/harness issue, not
evidence that rate limiting should be disabled or that the core should fail
open. A future rerun must use distinct synthetic users or an explicitly
approved per-user token setup before it can be used as a clean capacity
baseline.

Status: **RED for load-test acceptance; core safety evidence is positive.**
