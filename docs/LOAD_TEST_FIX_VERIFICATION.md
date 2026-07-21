# Load-test fix verification

## Current state

- Branch: `fix/loadtest-baseline-blockers`
- Expected commit: `97ce4b3`
- CI: PENDING; GitHub CLI is not authenticated.
- Main/tag are unchanged; no merge performed.
- Scope: assignment concurrency safety, load-test limiter, external-side-effect controls and cleanup tooling only.

## Evidence state

- Original aggregate/failure CSVs remain preserved in the main history as `load_tests/results/core-10-failed_*.csv`.
- Additional old result files remain untracked and are not staged.
- LOADTEST ticket IDs recorded before cleanup are documented in `docs/LOAD_TEST_BLOCKER_ANALYSIS.md`.
- Slide directories and backups remain untracked and are not staged.
- Cleanup has not been executed.

## Runtime snapshot before verification

- MariaDB: 10.11.17.
- Redis: 7.4.9.
- Uvicorn: one process; Dockerfile/start script has no `--workers` option.
- Celery: one worker service with default prefork concurrency; compose does not set `--concurrency`.
- SQLAlchemy: no explicit pool arguments; effective QueuePool defaults are size 5 and max overflow 10.
- The currently running stack is the previous non-load-test stack unless a later preflight explicitly proves otherwise.

## Verification log

| Gate | Result | Evidence |
|---|---|---|
| Static syntax compile | PASS | Python compile of changed backend, test, Locust and helper modules |
| Focused assignment tests | PARTIAL/RED | Lock-focused subset: 4 passed, 12 deselected in 36.96s. The broader assignment/scoping group was interrupted after more than 7 minutes with failure/error markers and no summary; it is not evidence of a pass. |
| Full backend tests | PENDING | Not run yet |
| Frontend tests x3/build | PENDING | Not run yet |
| Alembic | PENDING | Not run yet |
| Cleanup dry-run | PASS | Corrected dry-run selected all 31 recorded LOADTEST tickets in organisation 4; no deletion was executed. |
| Load-test preflight | PARTIAL | Missing required load-test flags was correctly rejected with exit code 2. End-to-end backend/worker isolation is still pending. |
| 10-user rerun | NOT RUN | Blocked until all prior gates pass |
| GitHub Actions | PENDING | GitHub CLI unauthenticated |

## Classification

Current overall status is **RED/PENDING**. No GREEN/YELLOW claim is made until focused tests, full suites, external-side-effect proof, cleanup dry-run and the controlled 10-user rerun produce evidence.

## Additional evidence

- Static compilation of changed Python modules passed.
- The lock-focused unit subset passed, but the broader focused test command was stopped after hanging for more than seven minutes and emitted failure/error markers. This is a verification blocker, not a pass.
- Load-test preflight refused to run when `LOAD_TEST_MODE` was absent, as intended.
- The first cleanup dry-run exposed a pagination defect; the cleanup script now requests 100 records and follows subsequent pages. The corrected dry-run found all 31 recorded LOADTEST tickets: `97, 98, 99, 100, 103-110, 112, 114, 116-118, 120-122, 124-125, 127-135`.
- No cleanup confirmation flag has been used, so no LOADTEST data has been deleted.
- The 10-user rerun has not started. Frontend, full backend, Alembic, provider-spy and end-to-end worker verification remain pending.
