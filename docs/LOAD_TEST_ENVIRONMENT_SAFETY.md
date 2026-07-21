# Load-test environment safety

This document defines the non-production safety boundary for the next controlled run.

Required runtime flags:

```text
LOAD_TEST_MODE=true
ALLOW_LOAD_TEST=true
AI_ENABLED=false
EMAIL_SENDING_ENABLED=false
EMAIL_POLLING_ENABLED=false
GOOGLE_INTEGRATIONS_ENABLED=false
PAYMENT_INTEGRATIONS_ENABLED=false
```

The backend and Celery worker must receive the flags in their actual container environment. A shell value in the Locust process is not sufficient. Production startup must reject `LOAD_TEST_MODE=true`; load-test mode is valid only for local or explicitly approved staging targets with a dedicated test organisation.

In load-test mode:

- ticket creation never calls Groq;
- AI classification is skipped or deterministic and locally marked;
- email is suppressed or routed to a local sink;
- IMAP polling, GSC, GA4 and payment calls are disabled;
- scheduled billing/email work cannot affect non-test organisations;
- all generated records are scoped to the dedicated test organisation.

The preflight must verify the target environment, database identity, external flags, test organisation and cleanup credentials before Locust starts. The runner must fail closed when any check is missing.

