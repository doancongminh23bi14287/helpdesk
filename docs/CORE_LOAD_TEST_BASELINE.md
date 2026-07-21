# Core load-test baseline — 2026-07-21

## Status

**FAILED SAFETY/PERFORMANCE GATE — not capacity evidence.** The core functional baseline remains tagged `thesis-core-green`, but the load-test progression is stopped at 10 users. The 25, 50 and 100-user stages were not run.

## Environment

- Target: local Docker deployment at loopback (`127.0.0.1`), not production.
- Host: 4 logical CPUs, 7,839 MiB RAM, 2,047 MiB swap.
- Snapshot after the run: 884 MiB available RAM and swap fully used.
- Services: backend, MariaDB/MySQL, Redis, Celery worker, Celery Beat and mail service were running.
- Dataset: isolated organisation ID 4, service ID 10, three synthetic persona accounts, generated subjects prefixed `LOADTEST-`.
- Duration: 5 minutes.
- User mix: 10 concurrent users (Locust spawned 6 customer, 3 staff and 1 admin in this run).
- Think time: random 1–5 seconds.
- Setup authentication: one login per persona, then token reuse within the Locust process.

## Results

| Measure | Result |
|---|---:|
| Requests | 726 recorded in CSV |
| Throughput | 2.75 requests/second |
| Failures | 131 (18.04%) |
| Overall P50 | 36 ms |
| Overall P95 | 4,200 ms |
| Overall P99 | 15,000 ms |
| Maximum | 36,049 ms |

Key endpoints:

| Endpoint | Requests | Failures | P50 | P95 | P99 |
|---|---:|---:|---:|---:|---:|
| `GET /api/tickets` | 398 | 123 (30.90%) | 450 ms | 3,200 ms | 5,400 ms |
| `POST /api/tickets` | 39 | 8 (20.51%) | 6,600 ms | 26,000 ms | 36,000 ms |
| `GET /api/tickets/[id]` | 103 | 0 | 37 ms | 100 ms | 320 ms |
| `POST /api/tickets/[id]/replies` | 6 | 0 | 4,000 ms | 15,000 ms | 15,000 ms |

The Locust console observed 727 completed requests at shutdown; the generated stats CSV contains 726. This one-request shutdown discrepancy does not change the failed result.

## Failure analysis

1. `GET /api/tickets` returned 123 HTTP 429 responses. Backend logs show the configured 60 requests/minute limiter treated the Locust traffic as one source IP. This is expected limiter behaviour for a single-process, single-host generator, but means this profile cannot represent 10 independent client IPs without a trusted test-only proxy arrangement.
2. Eight ticket creates returned HTTP 500. Every inspected traceback was MySQL error 1213: a deadlock while concurrent requests updated the same staff user's `users.last_assigned_at`. This is a real concurrent-assignment failure and blocks a capacity claim.
3. The running backend and worker had `AI_FEATURES_ENABLED=true` and `EMAIL_FEATURES_ENABLED=true`. Ticket creation consequently called Groq and Gmail despite the Locust client not invoking AI/Google endpoints directly. This violated the intended no-external-provider load-test policy. The harness now requires explicit attestation that backend side effects are disabled before ticket creation can be enabled.
4. Email logging also emitted MariaDB truncation warnings for `email_log.action='outbound'`. This did not account for Locust's eight create failures, but is a separate operational defect to investigate before another write-heavy stage.
5. Celery executed AI classification work, including one task lasting approximately 107 seconds. Therefore queue/provider observations from this run are contaminated by real external inference and are not a repeatable baseline.

No database-connection exhaustion or Redis crash was demonstrated in the captured logs. The host was memory constrained, so latency numbers are environment-specific; memory pressure does not explain away the deterministic deadlock or unsafe external calls.

## Decision

- Do not run 25, 50 or 100 users from this result.
- Do not claim system capacity.
- Do not start SEO implementation under the agreed sequence because the core load baseline is not green.
- Before rerun: isolate a deployment with AI/email/provider effects disabled, address or safely retry the assignment deadlock, decide how to model per-client rate limits, and verify the email-log enum mismatch.
- Keep the raw aggregate and failure CSV files as evidence; the high-frequency history file is not required for the report.
