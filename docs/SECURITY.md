# Security

## Authentication
- Access tokens are JWTs with short expiry.
- Refresh tokens are stored server-side as hashes in `user_sessions`.
- Refresh rotation revokes the old session and creates a new one.
- Logout revokes the active refresh token.
- Password change revokes active sessions and blacklists existing tokens.

## Authorisation
- Route dependencies enforce feature-level RBAC.
- `403` means the role cannot use the feature.
- `404` means the record does not exist or is outside the caller's scope.
- Customer users are restricted to their own organisation and their own tickets.
- Staff users see assigned organisations and directly assigned tickets.
- Admin users can access all organisations.

## Production Config
- `ENV=production` fails fast for unsafe JWT secrets.
- Production requires explicit database and Redis config.
- Email credentials are required when `EMAIL_FEATURES_ENABLED=true`.
- `CORS_ORIGINS=*` is rejected in production.

## Attachments
- Uploads are authenticated.
- Downloads go through backend access checks.
- MIME type and magic bytes are validated.
- SHA-256 checksums are stored.
- Local storage rejects absolute paths and path traversal.

## Rate Limits
- Login: `RATE_LIMIT_LOGIN`, default `10/minute`.
- Refresh: `RATE_LIMIT_REFRESH`, default `30/minute`.
- Change password: `RATE_LIMIT_CHANGE_PASSWORD`, default `5/minute`.
- Ticket creation: `RATE_LIMIT_TICKET_CREATE`, default `20/minute`.
- File upload: `RATE_LIMIT_FILE_UPLOAD`, default `10/minute`.
- Admin email poll: `RATE_LIMIT_ADMIN_EMAIL_POLL`, default `3/minute`.

## Logging
- Request logs include request id, method, path, status code, and duration.
- Tokens, passwords, SMTP/IMAP credentials, and raw file contents must not be logged.
