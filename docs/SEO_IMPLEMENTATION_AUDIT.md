# SEO implementation audit

| Area | Current implementation | Security/business issue | Proposed action |
|---|---|---|---|
| GSC organisation | `_resolve_org` uses `assert_org_access` and shared `get_accessible_org_ids` | Customers blocked by `require_staff_or_admin`; staff/admin scoping mostly correct | Reuse helper for new reports/ticket conversion |
| GA4 organisation | Same shared scoping helper | Customers blocked; selected org is server validated | Keep central policy |
| OAuth state | Redis state has 10-minute TTL, is deleted on callback, stores org/user | State is one-time/expiring but callback does not independently verify initiating authenticated session/user; callback can persist state owner after possession of state | Add callback binding validation without schema migration |
| Token storage | GSC/GA4 tokens are encrypted before persistence; status/report responses omit token fields | Provider error strings may expose upstream detail; property selection accepts arbitrary URL/ID | Sanitize errors and verify selected property belongs to connection/provider result |
| GSC property | `/properties` lists provider sites; `/property` stores submitted URL | No server-side proof submitted property belongs to listed sites | Validate against provider property list before save |
| GA4 property | `/properties` lists provider properties; `/property` stores submitted ID/name | No server-side proof submitted property belongs to connected account | Validate against provider property list before save |
| Reports | Live provider calls; GSC row limit capped at 25,000; GA4 report has no explicit bounded row limit | No period comparison/opportunity engine yet; provider failures map to 502 | Add bounded GSC dashboard service and deterministic rules |
| Frontend | `useGscData` calls real GSC status/search analytics; SEO nav labels preview; trend has empty/error states | Need audit all cards for fabricated/demo values and add clear connection/error states | Replace demo values or label demo mode; implement dashboard states |
| Ticket workflow | Existing `SEO Request` ticket type exists; no SEO opportunity-to-ticket route found | Manual conversion workflow missing | Add staff/admin-only explicit conversion using existing ticket creation service |
| Celery | No SEO sync task identified in current search | Avoid adding scheduled external calls in this phase | Keep live/mock request flow only |

No database migration is planned. Table and Alembic revision deltas remain zero for this phase.
