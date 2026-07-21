# Post-implementation verification report

Verification date: 2026-07-21  
Scope: verification of approved TC-01 through TC-12 changes in commit `94a62a3`  
Current status: **IN PROGRESS — not GREEN**

## 1. Verification constraints

- Verification only; no new business features.
- Do not modify the thesis PDF or PowerPoint.
- Do not modify schema or historical migrations.
- Preserve assignment weights 40 workload / 40 skill / 20 presence.
- Preserve ticket lifecycle, billing, VAT, invoice numbering, public route contracts and organisation-scoping rules.
- Keep `AI_ASSIGNMENT_REEVALUATION_MODE=suggest`; do not enable automatic production reassignment.
- Source or test changes require a reproduced deterministic defect and a documented root cause within the relevant TC.
- Do not stage or commit `slides/`, `slides-backup-20260716-0001/` or `slides-backup-20260718-012906/`.
- Do not run load tests until security, backend, frontend, build and migration gates are GREEN.

## 2. Repository and environment baseline

| Item | Observed value | Evidence/qualification |
|------|----------------|------------------------|
| Branch | `main` | `git branch --show-current` |
| Exact commit | `94a62a39a889c8b1fb8d49aaf4c1854e26bc4a20` | `git rev-parse HEAD` |
| Python | `3.12.3` | Repository backend virtual environment |
| Node.js | `v24.15.0` | Local executable |
| npm | Pending exact version capture | Initial version command returned no stdout |
| Database | MariaDB `10.11` container, healthy | Container image `mariadb:10.11`; exact server version check pending |
| Redis | Redis 7 Alpine container, available for inspection | Container image `redis:7-alpine`; exact server version and ping pending |
| Backend services | Backend, Celery worker and Celery Beat containers up | `docker ps` at verification start |

### Git status at verification start

No tracked source file was modified. The following paths were untracked:

```text
docs/THESIS_CHANGE_IMPACT_MATRIX.md
slides-backup-20260716-0001/
slides-backup-20260718-012906/
slides/
```

This report is subsequently added as an untracked documentation file. Slide paths remain excluded from staging and commits.

## 3. Backend baseline

Pending current collection and complete test run.

| Run | Collected | Passed | Failed | Skipped | Xfailed | Warnings | Duration | Result |
|-----|-----------|--------|--------|---------|---------|----------|----------|--------|
| Collection | 683 | — | — | — | — | 3 collection warnings | 5.61s | Collection succeeded |
| GitHub Actions baseline for 94a62a3 | 683 | 675 | 8 | 0 reported | 0 reported | 839 | 519.00s | **FAILED** |
| Local baseline | 683 | Incomplete | 6 reproduced by 23% | Unknown | Unknown | Unknown | Interrupted at user request | Stopped to protect low-RAM workstation; use CI for complete rerun |

For each failure, record whether it predates `94a62a3`, the relevant TC, reproduction evidence and root cause before any fix.

## 4. Frontend baseline

Pending three complete test-suite runs and production build. The previously observed 65-pass/1-timeout result is historical evidence only and will not be treated as current verification.

| Run | Passed | Failed | Skipped | Duration | Timeout/flakiness conclusion |
|-----|--------|--------|---------|----------|------------------------------|
| 1 | Pending | Pending | Pending | Pending | Pending |
| 2 | Pending | Pending | Pending | Pending | Pending |
| 3 | Pending | Pending | Pending | Pending | Pending |

Production build: **Pending**.

## 5. Alembic and database

Repository facts measured during the compatibility audit:

- 47 repository revisions.
- One repository head: `d1c8e4f2a7b9`.
- 43 ORM-declared tables.
- Commit `94a62a3` added no migration or model table.

Local/test database `current`, history and upgrade verification: **Pending**.

## 6. Focused TC evidence

| TC | Required evidence | Status | Findings |
|----|-------------------|--------|----------|
| TC-01/02 | Tenant isolation, AI/output/attachment/note scoping, admin and eligible-staff behaviour, candidate eligibility | Pending | — |
| TC-03 | Authenticated non-impersonable heartbeat, 30s/90s defaults, reconnect/multi-tab and Redis-failure behaviour, 20/0 scoring | Pending | — |
| TC-04/05 | Combined non-terminal workload, no duplicate counts, tenant-scoped history, ticket-type fallback, accepted prediction, deterministic ties, 40/40/20 | Pending | — |
| TC-06 | Token ownership, bounded TTL, compare-delete, concurrent behaviour and Redis-failure policy | Pending | — |
| TC-07 | Default `suggest`, no default automatic reassignment, all guards and Celery idempotency | Pending | — |
| TC-08 | Retry categories, no duplicate prediction, core workflow independence, human-controlled replies and safe logs | Pending | — |
| TC-09 | Red/breached transitions and reminders, Redis degradation, waiting pause/deadline and no activity spam | Pending | — |
| TC-10 | Score/source display, role/organisation visibility, configured accessibility/build checks | Pending | — |
| TC-12 | Harness production refusal, explicit gate, synthetic/prefixed data, external-service exclusions and cleanup | Pending | — |

## 7. Failure log

GitHub Actions produced eight deterministic failures for commit 94a62a3. Root-cause classification was completed before any corrective edit:

| Failure group | Relevant TC | Predates 94a62a3? | Root cause | Corrective boundary |
|---------------|-------------|--------------------|------------|---------------------|
| Two member-sync replacement tests return 422 | TC-02 | No; exposed by the new eligibility guard | The tests replace an assignee with staff2 after the first assignee has caused a project staff-member list to exist. staff2 is organisation-eligible but is not yet an explicit project member, so the approved guard correctly rejects it. | Make staff2 project-eligible in test setup. Do not weaken project eligibility. |
| Four skill tests cannot import the former per-agent helper | TC-04/05 | No; helper changed in 94a62a3 | Batched skill scoring replaced the per-agent helper to avoid N+1 queries. Tests still import the removed internal helper; scoring assertions were never reached. | Point tests at the batched helper while preserving every numerical assertion. Do not restore the N+1 helper. |
| Project visibility test expects access via assigned ticket | TC-01 | Old expectation predates 94a62a3; failure is intentional under the approved invariant | The test expects direct ticket assignment to expand project/organisation access, which TC-01 explicitly forbids. | Assert invisibility for staff without organisation access. Do not restore cross-tenant visibility. |
| Assignment activity test returns 422 | TC-02 | Test setup predates 94a62a3; its assumption became invalid | The test omits the existing staff-assignment fixture, so its assignee is not eligible for the ticket organisation. | Add the fixture and retain the activity assertion. Do not bypass organisation eligibility. |

No source business logic was changed for these failures. Corrective edits are test-only and limited to TC-01/02/04/05. The next complete evidence source is GitHub Actions because the local full run was intentionally stopped to avoid exhausting workstation RAM.

## 8. Load-test gate

**BLOCKED until all preceding gates are GREEN.** No Locust stage has been executed.

## 9. Final status

**RED pending rerun.** Baseline CI has deterministic failures. Load testing remains blocked until the corrective commit passes all required CI gates.
