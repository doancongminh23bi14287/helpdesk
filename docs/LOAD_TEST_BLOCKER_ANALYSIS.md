# Load-test blocker analysis

## Evidence preserved before changes

- Branch at inspection: `fix/loadtest-baseline-blockers`.
- Base commit: `8ad2825`; stable core tag remains `thesis-core-green` at `614d48d`.
- Failed run: 10 users, 5 minutes, 726 CSV requests, 131 failures.
- Preserved result files: `load_tests/results/core-10-failed_*.csv`.
- Preserved aggregate failure evidence: 123 `GET /api/tickets` HTTP 429 responses and 8 `POST /api/tickets` HTTP 500 responses.
- Existing evidence report: `docs/CORE_LOAD_TEST_BASELINE.md`.
- LOADTEST ticket IDs recorded before cleanup: 97–100, 103–109, 110, 112, 114, 116–118, 120–122, 124–125, 127–135; all belong to organisation 4 and use the `LOADTEST-` prefix.
- Untracked slide and backup directories were not staged.

## Runtime snapshot

- MariaDB: 10.11.17.
- Redis: 7.4.9.
- Uvicorn: one process from `backend/start.sh`/Dockerfile; no `--workers` flag.
- Celery: one worker service using the default prefork concurrency; the compose command does not set an explicit concurrency.
- SQLAlchemy: `create_engine(DB_URL, pool_pre_ping=True, pool_recycle=3600)` with no explicit pool arguments. The effective QueuePool defaults are therefore pool size 5 and max overflow 10.
- During the failed run, the running backend and worker had `AI_FEATURES_ENABLED=true` and `EMAIL_FEATURES_ENABLED=true`.

## Demonstrated deadlock path

The ticket-create handler in `backend/app/api/tickets.py` calls `find_best_assignee()` while the ticket transaction is already open. `find_best_assignee()` acquires the organisation Redis lock, computes scores, and releases the lock before the caller creates the assignment rows, updates `users.last_assigned_at`, and commits.

The relevant DB write is:

```text
POST /api/tickets
  → find_best_assignee()
  → Redis lock released
  → set_ticket_assignees()
  → UPDATE users SET last_assigned_at=...
  → db.commit()
```

The backend traceback for all inspected create failures was MySQL error 1213:

```text
Deadlock found when trying to get lock; try restarting transaction
UPDATE users SET last_assigned_at=... WHERE users.id = 10
```

This is a demonstrated transaction race: the organisation lock does not cover the DB mutation/commit, and multiple requests select/update the same staff row. The current code has no deadlock retry around the complete ticket transaction. The Redis lock's token ownership protects release, but does not protect the later DB writes because it has already been released.

## Rate-limit path

The 123 failures were `GET /api/tickets` HTTP 429 responses. Backend logs identify the configured 60-per-minute limiter and the common Docker bridge source IP. They were not login failures or ticket-create rate-limit failures. The single Locust process therefore exercised one per-IP bucket rather than ten independent client addresses.

## External-side-effect finding

The Locust process did not call AI/Google endpoints directly, but ticket creation enqueued the normal AI classification task and the backend background task sent notification email. Because the running backend and worker had both feature flags enabled, the run reached Groq and Gmail. This makes the run unsuitable as an isolated load baseline and is the reason backend-enforced load-test mode is required before rerun.

## Constraints for the fix

No schema, migration, public route contract, assignment weight, lifecycle, SLA, billing, VAT, invoice or permission changes are authorised in this branch. The fix must keep the 40/40/20 scorer and must not silently fail open when an organisation lock cannot be acquired.

