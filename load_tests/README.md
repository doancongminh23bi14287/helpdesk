# CustomerHub Locust harness

The harness is inert until LOAD_TEST_CONFIRM=true is set. Credentials come only from environment variables. It uses a configurable [LOADTEST] prefix and one-to-five-second think time. AI is excluded unless LOAD_TEST_INCLUDE_AI=true; ticket creation separately requires LOAD_TEST_CREATE_TICKETS=true.

Environment setup example (replace every value locally):

    export LOAD_TEST_CONFIRM=true
    export LOAD_TEST_CUSTOMER_EMAIL=load-customer@example.test
    export LOAD_TEST_CUSTOMER_PASSWORD=replace_me
    export LOAD_TEST_STAFF_EMAIL=load-staff@example.test
    export LOAD_TEST_STAFF_PASSWORD=replace_me
    export LOAD_TEST_ADMIN_EMAIL=load-admin@example.test
    export LOAD_TEST_ADMIN_PASSWORD=replace_me
    export LOAD_TEST_ORG_ID=123
    export LOAD_TEST_SERVICE_ID=456
    export LOAD_TEST_CREATE_TICKETS=true

Profiles:

| Profile | Headless command |
|---|---|
| 10 users | locust -f load_tests/locustfile.py --headless -u 10 -r 2 -t 5m --host http://127.0.0.1:8001 |
| 25 users | locust -f load_tests/locustfile.py --headless -u 25 -r 5 -t 10m --host http://127.0.0.1:8001 |
| 50 users | locust -f load_tests/locustfile.py --headless -u 50 -r 5 -t 15m --host http://127.0.0.1:8001 |
| 100 users | locust -f load_tests/locustfile.py --headless -u 100 -r 10 -t 20m --host http://127.0.0.1:8001 |

Capture RPS, median, P95, P99, error rate and endpoint failures. Also observe DB pool exhaustion/timeouts, Redis errors, Celery queue depth/age and retries. Sequential browser timings are not capacity evidence.

Cleanup uses the supported admin API/UI: locate subjects beginning with the configured prefix in the isolated organisation, export their IDs, delete them, and verify replies/attachments are gone. Never use broad recursive SQL deletion on shared data.

Production-like hosts are blocked unless LOAD_TEST_ALLOW_PRODUCTION=true is also explicitly supplied after human approval. No production load run was performed by this task.
