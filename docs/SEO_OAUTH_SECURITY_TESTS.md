# OAuth security verification

The current implementation stores an opaque Redis state with provider, initiating user ID, organisation ID and a cryptographic nonce. State is namespaced by provider and consumed with Redis `GETDEL`, so concurrent callback attempts can consume it only once. Callback validation then checks the stored user is active and still has access to the stored organisation before exchanging the provider code.

Focused tests cover opaque binding, malformed/missing state, provider separation and repeated concurrent consumption. A consumed state is not retried after provider failure; the user must start a new OAuth flow.

Remaining verification before PASS: full callback integration tests with mocked provider exchange, expiry boundary tests, token/log redaction assertions, and rollback tests for provider/property/commit failures.
