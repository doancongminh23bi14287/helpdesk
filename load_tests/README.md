# CustomerHub Locust harness

The harness is inert until both ALLOW_LOAD_TEST=true and LOAD_TEST_CONFIRM=true are set. Credentials come only from environment variables. The prefix must begin with LOADTEST-, and synthetic login addresses must use the reserved example.com, example.org or example.net domains. The main workload contains no AI, Google or payment endpoint. Ticket creation separately requires LOAD_TEST_CREATE_TICKETS=true.

Loopback is allowed by default. Staging requires LOAD_TEST_ALLOW_STAGING=true plus an exact LOAD_TEST_ALLOWED_HOSTS entry. Production-like hostnames are always rejected and have no override.

Environment setup example (replace every value locally):

    export ALLOW_LOAD_TEST=true
    export LOAD_TEST_MODE=true
    export LOAD_TEST_KEY=replace_with_test_only_key
    export AI_ENABLED=false
    export EMAIL_SENDING_ENABLED=false
    export EMAIL_POLLING_ENABLED=false
    export GOOGLE_INTEGRATIONS_ENABLED=false
    export PAYMENT_INTEGRATIONS_ENABLED=false
    export LOAD_TEST_CONFIRM=true
    export LOAD_TEST_PREFIX=LOADTEST-
    export LOAD_TEST_CUSTOMER_EMAIL=load-customer@example.com
    export LOAD_TEST_CUSTOMER_PASSWORD=replace_me
    export LOAD_TEST_STAFF_EMAIL=load-staff@example.org
    export LOAD_TEST_STAFF_PASSWORD=replace_me
    export LOAD_TEST_ADMIN_EMAIL=load-admin@example.net
    export LOAD_TEST_ADMIN_PASSWORD=replace_me
    export LOAD_TEST_ORG_ID=123
    export LOAD_TEST_SERVICE_ID=456
    export LOAD_TEST_CREATE_TICKETS=true
    export LOAD_TEST_BACKEND_SIDE_EFFECTS_DISABLED=true
    export LOAD_TEST_PREFIX=LOADTEST-

`LOAD_TEST_BACKEND_SIDE_EFFECTS_DISABLED=true` is an operator attestation, not a client-side switch. Before setting it, inspect the environment of the running backend and worker, disable `AI_FEATURES_ENABLED` and `EMAIL_FEATURES_ENABLED`, remove provider credentials from the isolated load-test deployment, and restart those processes. A shell `.env` value does not prove that an already-running container received it. If this cannot be demonstrated, leave ticket creation disabled and run a read-only profile.

The harness performs one measured setup login per persona and reuses that persona token within the Locust process. This prevents password hashing from dominating the core endpoint profile; authentication capacity must be measured separately.

Profiles:

| Profile | Headless command |
|---|---|
| 10 users | locust -f load_tests/locustfile.py --headless -u 10 -r 2 -t 5m --host http://127.0.0.1:8001 |
| 25 users | locust -f load_tests/locustfile.py --headless -u 25 -r 5 -t 10m --host http://127.0.0.1:8001 |
| 50 users | locust -f load_tests/locustfile.py --headless -u 50 -r 5 -t 15m --host http://127.0.0.1:8001 |
| 100 users | locust -f load_tests/locustfile.py --headless -u 100 -r 10 -t 20m --host http://127.0.0.1:8001 |

Capture RPS, median, P95, P99, error rate and endpoint failures. Also observe DB pool exhaustion/timeouts, Redis errors, Celery queue depth/age and retries. Sequential browser timings are not capacity evidence.

Cleanup uses the supported admin API/UI: locate subjects beginning with the configured prefix in the isolated organisation, export their IDs, delete them, and verify replies/attachments are gone. Never use broad recursive SQL deletion on shared data.

No production load run is permitted by this harness. Google, AI and payment endpoints are absent from the main workload. Stop a stage on any deterministic 5xx, assignment race/deadlock, unsafe external call, or material error rate; do not increase user count after a failed stage.
