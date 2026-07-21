# OAuth callback integration audit

## Current sequence

Both callbacks consume the provider-specific Redis state with `GETDEL`, parse the server-side provider/user/organisation binding, load the initiating active user, and validate organisation access before exchanging the authorization code. Provider token exchange then creates or updates the organisation connection and commits it.

## Current blockers before PASS

- The callback does not yet fetch and validate a provider property before saving the connection; property validation currently occurs in the explicit property-selection route.
- Full mocked end-to-end callback tests for provider failure, database rollback, existing-connection preservation and log/redirect redaction are not yet complete.
- Redis `GETDEL` intentionally consumes state before provider exchange; a provider/network failure requires a new OAuth flow.

## Safety already present

- GSC and GA4 use separate state namespaces and provider checks.
- State is opaque, short-lived and atomically consumed.
- Callback organisation comes from server-side state; no organisation parameter is read by the callback.
- User must still exist, be active and retain organisation access.
- Tokens are encrypted before persistence and are not returned by status/property schemas.

The callback remains a merge blocker until the missing property-before-commit, rollback-preservation and redaction integration tests pass.
