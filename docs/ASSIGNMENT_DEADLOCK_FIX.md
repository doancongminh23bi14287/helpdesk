# Assignment deadlock fix

The first controlled run demonstrated MySQL error 1213 while concurrent ticket creation updated the `users.last_assigned_at` row.

Before:

`find_best_assignee()` acquired the organisation Redis lock, computed scores, and released the lock before the caller wrote `TicketAssignee`, updated the selected user, and committed. The Redis lock therefore did not protect the transaction.

After:

- automatic ticket creation uses `find_best_assignee_for_transaction()`;
- the random-token Redis organisation lock is stored on the SQLAlchemy session;
- the selected user row is locked with `SELECT ... FOR UPDATE`;
- assignment records, activity, notification and `last_assigned_at` are committed while the Redis lock is still held;
- the lock is released after commit, or after rollback on failure;
- Redis unavailable/lock held leaves the ticket unassigned instead of fail-open concurrent assignment;
- the existing 40/40/20 scoring and eligibility rules are unchanged.

No migration or public API contract changed. AI reevaluation already held its organisation lock through its commit and continues to use token-based compare-and-delete release.

The next verification must run same-organisation concurrent creates repeatedly and must prove zero deadlocks, no duplicate assignments and no lost tickets. This document does not claim that evidence before CI/rerun completes.
