# Load-test runtime configuration

## Status

`NOT READY`. The current local stack is the normal development stack, not an
isolated load-test runtime. Locust must not run against it.

| Capability | Actual configuration | Required load-test value | API enforced | Worker enforced | Verified |
|---|---|---:|---|---|---|
| Application environment | `ENV` | `local` or `staging` | Partial | Partial | No |
| AI | `AI_FEATURES_ENABLED` / `AI_ENABLED` | `false` | Yes | Yes, after restart | No |
| Email sending | `EMAIL_FEATURES_ENABLED` / `EMAIL_SENDING_ENABLED` | `false` | Yes | Yes, after restart | No |
| Email polling | `EMAIL_POLLING_ENABLED` | `false` | N/A | Guard exists | No |
| Google integrations | `GOOGLE_INTEGRATIONS_ENABLED` | `false` | Guard exists | N/A | No |
| Payments | `PAYMENT_INTEGRATIONS_ENABLED` | `false` | Guard exists | N/A | No |
| Load-test mode | `LOAD_TEST_MODE` + `ALLOW_LOAD_TEST` | `true` | Yes | Process startup | No |
| Database | `DB_URL` / `DATABASE_URL` | dedicated test database | N/A | N/A | No |
| Redis broker/result | `REDIS_URL` | dedicated instance/index/namespace | N/A | N/A | No |
| Celery queue | Celery defaults | dedicated queue | N/A | N/A | No |
| Celery Beat | `celery_beat` compose service | stopped or safe test schedule | N/A | N/A | No |

## Observed current runtime

- `helpdesk_backend` has `AI_FEATURES_ENABLED=true`.
- `helpdesk_backend` has `EMAIL_FEATURES_ENABLED=true`.
- `helpdesk_celery_worker` and `helpdesk_celery_beat` use the same normal
  `backend/.env.docker` configuration.
- `docker-compose.yml` uses the shared `helpdesk_db` and `helpdesk_redis`.
- Celery uses Redis database 0 for broker/result; the application Redis client
  is hard-coded to database 1, so changing only `REDIS_URL` is not sufficient
  to prove complete isolation.
- Beat schedules email polling, email outbox processing, subscriptions,
  expiry notifications and invoice jobs.

## Required isolated runtime before Locust

The operator must provide a separate local/staging database and Redis
instance/database/namespace, a dedicated Celery queue, synthetic accounts and
an out-of-band load-test key. All backend, worker and any Beat processes must
be restarted with the same load-test environment. The effective values must be
recorded from the running processes, not only from an env file.

No credentials or `.env.loadtest.local` file is committed by this change.

## Decision

The controlled 10-user rerun is blocked until the table above is verified
green and provider calls are proven to be zero using provider spies, blocked
network or equivalent runtime evidence.
