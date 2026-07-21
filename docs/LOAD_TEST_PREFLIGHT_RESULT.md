# Load-test preflight result

Date: 2026-07-21

Result: PASS for runtime isolation.

- Target: `http://127.0.0.1:8011` (loopback only)
- Database: dedicated `helpdesk_loadtest` on `helpdesk_loadtest_db`
- Redis: dedicated `helpdesk_loadtest_redis`
- Backend and worker restarted with the load-test environment
- Celery Beat: not started
- `LOAD_TEST_MODE=true`, `ALLOW_LOAD_TEST=true`
- AI, email sending, email polling, Google and payment integrations: false
- Synthetic organisation: ID 4
- Preflight output: `PREFLIGHT OK: target and side-effect configuration passed`

Secrets and tokens are intentionally not recorded.
