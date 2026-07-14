# CUSTOMERHUB PRODUCT QUALITY AUDIT

Audit date: 2026-07-14  
Scope: static source review, repository inventory, business-flow tracing, security review, UX review, and offline analysis of the checked-in AI evaluation dataset.  
Baseline: the worktree already contained uncommitted frontend/SEO changes before this audit. Those changes were treated as user-owned and were not reverted.

## 1. Executive Summary

CustomerHub is a React/Vite frontend backed by FastAPI, SQLAlchemy, Alembic, MySQL/MariaDB, Redis, Celery and Socket.IO. It has real implementations for ticketing, projects/tasks, subscriptions/invoices, email ingestion, notifications, Google Search Console/GA4, and Groq-assisted ticket work. The database contains 43 ORM tables and the backend registers 22 routers with 171 route/router declarations.

The product is not merely a display prototype, but it is not yet production-ready. The most important confirmed issues are:

1. Inbound email threading trusts `In-Reply-To`, `References`, or a subject token such as `[#123]` without verifying that the sender belongs to the referenced ticket. This permits unauthorized content and attachment injection into another customer's ticket.
2. Subscription state has two inconsistent clocks. The model stores `status`, `end_date`, `current_period_end`, and `next_billing_date`, but the daily checker ignores `end_date`, expires only after a billing grace period, and does not synchronize the linked `Service`. This explains an “Active” service shown beside an expired date.
3. Manual ticket/task assignment accepts any existing user, including inactive users, customers, or staff without access to the organization/project. Auto-assignment has workload and historical-category scoring, but its “online” signal is actually `last_login_at`, not presence.
4. Ticket create/update can infer a project from `task_id` without revalidating the inferred project's organization and accessibility. Completed/cancelled project/task eligibility is not checked.
5. AI classification is reasonably bounded, but summarization has no system/user prompt boundary and no injection guard; reply suggestion checks the ticket subject/description but not the reply history. The guard logs the first 120 characters of flagged input.
6. OAuth refresh/access tokens for GSC and GA4 are stored as plaintext. GA4 organization resolution differs from GSC and sends staff to their own provider organization rather than their assigned client organization.
7. The customer-facing `/subscriptions` workflow still imports an ERPNext/Frappe bridge even though the active backend is FastAPI. The admin subscription workflow correctly uses FastAPI, so the system currently has two contradictory implementations.
8. The checked-in AI dataset contains exactly 47 unique, fully labeled tickets. Category results are promising; priority results are not strong enough to support autonomous decisions. The analysis script resolves every disagreement by taking rater 1, which is not a defensible adjudication process.

Recommended thesis position: present AI as a staff-facing suggestion layer only. Do not claim autonomous priority, assignment, reply, resolution, or closure.

## 2. System Inventory

| Module | Frontend pages/components | API routes | Models | Tests | Status |
|---|---|---|---|---|---|
| Authentication | `LoginPage`, `ForgotPasswordPage`, `ChangePasswordPage`, `AccountSecurityPage`, `ProfilePage` | `/api/auth/*` | `User`, `UserSession`, `LoginHistory`, `PasswordResetOTP` | auth, sessions, reset, security | Working; token storage and password policy need hardening |
| Users/Roles | `admin/UsersPage` | `/api/users/*` | `User` | users, permissions, scoping | Working admin CRUD; hard delete is dependency-incomplete |
| Staff | `admin/StaffAssignmentsPage` | `/api/staff-assignments` | `StaffOrgAssignment`, `Team`, `TeamMember` | assignment, auto-assign | Working org assignment; no skill/presence model |
| Customers/Organizations | `admin/OrganizationsPage` | `/api/organizations` | `Organization` | organizations, phase5a | Working |
| Contacts | organization detail UI | `/api/organizations/{id}/contacts` | `Contact` | phase5a | Working; hard delete only |
| Addresses | organization detail UI | `/api/organizations/{id}/addresses` | `Address` | phase5a | Working; hard delete only |
| Tickets | `TicketListPage`, `TicketDetailPage`, `NewTicketPage`, `components/tickets/*` | `/api/tickets/*` | `Ticket`, `TicketActivity`, `TicketAssignee` | tickets, scoping, archive, delete, project | Core workflow works; validation/security gaps remain |
| Ticket replies/notes | `TicketConversation`, `TicketComposer` | `/api/tickets/{id}/replies` | `TicketReply` | replies | Public/internal separation works for portal API |
| Attachments | ticket composer/content | `/api/tickets/{id}/attachments`, `/api/attachments/{id}/download` | `TicketAttachment` | file storage/security | Download scoped; reply association is not validated on upload |
| Ticket transfer | ticket sidebar/dialogs | `/api/tickets/{id}/transfer-request*` | `TicketTransferRequest` | assignment | Working mutual-consent flow |
| SLA/Priority | ticket detail/sidebar, admin SLA | `/api/tickets/{id}/sla`, `/api/admin/sla/policies` | `SlaPolicy`, ticket SLA fields | SLA | Working basic deadlines/pause; no complete breach workflow |
| Projects | `ProjectsPage`, `ProjectDetailPage` | `/api/projects/*` | `Project`, `ProjectMember`, `ProjectDocument` | projects, members, security | Working; “internal” means customer-hidden, not member-private for staff |
| Tasks | `ProjectDetailPage` | `/api/project-tasks/*` | `ProjectTask`, comments, activities, assignees, approvals | tasks, approval, discussion | Working; no dependency model; monolithic UI |
| Services | `ServicesPage` | `/api/services` | `Service`, `ServiceCategory` | service sync | Read-only UI; status/expiry can contradict |
| Subscriptions | `SubscriptionDashboard`, `SubscriptionDetail`, `admin/SubscriptionsPage` | `/api/subscriptions`, `/api/subscription-plans` | `Subscription`, `SubscriptionPlan` | phase5b, service sync | Admin path works; customer path still uses ERP/Frappe |
| Invoices/Payments | `InvoicesPage`, `admin/InvoicesPage` | `/api/invoices/*` | `Invoice`, `InvoiceLine`, `InvoicePayment`, `InvoiceNumberSeq` | invoice suites | Working FastAPI flow; legacy ERP hook remains for customer subscription detail |
| Notifications | `NotificationsPage`, layout menu | `/api/notifications` | `Notification` | notifications, Redis pubsub | Working in-app plus Socket.IO |
| Email/pipemail | admin outbox page | `/api/admin/email*` plus Celery poller | `EmailLog`, `EmailThread`, `EmailOutbox` | piping, threading, outbox | Functional but unsafe sender-to-thread authorization |
| AI classification | ticket detail AI components | `/api/ai/tickets/{id}/classify` | `TicketAiPrediction` | AI classification/base | Suggestion-only; evaluated category stronger than priority |
| AI summary | ticket sidebar | `/api/ai/tickets/{id}/summary|summarize` | `AiTicketSummary` | AI summary | Working but prompt isolation/model provenance incomplete |
| AI reply suggestion | ticket composer | `/api/ai/tickets/{id}/suggest-reply`, accept | `AiReplySuggestion` | AI reply | Working, human-mediated; no reject event/audit actor |
| GSC | `SeoDashboardPage`, `useGscData` | `/api/seo/gsc/*` | `GscConnection` | 26 GSC tests + frontend trend tests | Daily trend implemented; tokens plaintext |
| GA4 | `SeoDashboardPage` | `/api/seo/ga4/*` | `Ga4Connection` | 2 backend tests | Daily sessions implemented; staff org scoping defect |
| Audit/activity | ticket/task activity UI, login history | `/api/admin/activity`, resource-specific activity | `TicketActivity`, `TaskActivity`, `LoginHistory`, `EmailLog` | partial | No system-wide immutable audit log |

Evidence: `frontend/src/App.jsx:63-139`, `backend/app/main.py:160-182`, `backend/app/models/*.py`, `backend/tests/test_*.py`.

## 3. Ticket Audit

### Current lifecycle

Portal and email create tickets in `Open`. Portal creation can link organization, service, project and task, then choose none/manual/auto assignment. The supported state machine is:

```text
Open -> In Progress -> Waiting | Resolved
Waiting -> In Progress | Resolved
Resolved -> Closed | In Progress
Closed -> Open
```

Customer replies on `Waiting` or `Resolved` automatically move the ticket to `In Progress`. Internal replies are forced off for customers and filtered from customer reads. Status, priority, assignment, reply, project link and delete actions create ticket activities, but project/task relinking does not consistently create detailed activity.

Evidence: `backend/app/api/tickets.py:122-128` (`VALID_TRANSITIONS`), `:140-302` (`create_ticket`), `:499-632` (`update_ticket`), `:736-859` (`add_reply`).

### Findings

| ID | Severity | Module | Evidence | Business impact | Proposed fix | Risk |
|---|---|---|---|---|---|---|
| TKT-01 | CRITICAL | Email replies | `backend/app/services/email_piping.py:139-173`, `:239-272`; `_resolve_ticket_id` trusts headers/subject and append path does not compare sender with ticket | Any email sender who knows/guesses an ID can inject public replies or attachments into another ticket | Require the resolved sender to be the ticket creator/contact for the same org, or an authorized staff member; otherwise create a new ticket or quarantine | Existing legitimate forwarding aliases may need an allowlist |
| TKT-02 | HIGH | Ticket/project link | `backend/app/api/tickets.py:157-174`, `:583-594` | `task_id` can infer a cross-org project because only an explicitly supplied project is org-validated | Load task and project together, validate project org/access/status, validate task state | Could reject previously accepted invalid payloads |
| TKT-03 | HIGH | Assignment | `backend/app/services/assignment.py:16-71`; only existence is checked | Tickets/tasks can be assigned to customers, inactive users, or unauthorized staff; project membership can then be polluted | Central eligible-assignee validator: active staff/admin policy, org assignment, project access | Admin assignment policy must be explicit |
| TKT-04 | HIGH | Manual create | `backend/app/api/tickets.py:188-230` | Customers can submit manual assignee IDs because creation does not restrict assignment fields by role | Customers should use auto/none only; staff/admin can use manual under eligibility checks | Frontend currently hides controls by role, backend enforcement may expose client misuse |
| TKT-05 | MEDIUM | Attachments | `backend/app/api/tickets.py:949-982`; `reply_id` is stored without verifying it belongs to `ticket_id` | Corrupt association and misleading attachment placement | Validate reply belongs to scoped ticket before storage | Low |
| TKT-06 | MEDIUM | Validation | `backend/app/schemas/ticket.py:36-105` | Empty/whitespace replies and descriptions, arbitrary status/priority update strings can reach DB errors or low-quality records | Add Pydantic enums, trim/min/max validation; preserve API values | Validation changes can turn 500 into 422, which is desirable but observable |
| TKT-07 | MEDIUM | Hard delete | `backend/app/api/tickets.py:688-730` | Permanent delete removes operational history; no separate audit record survives | Keep archive/soft delete as default; restrict permanent deletion to retention workflow and durable audit | Requires product retention decision |
| TKT-08 | MEDIUM | Workflow semantics | `Ticket.status` enum and transitions | “Open” combines new/triaged/assigned; “Waiting” does not distinguish customer/internal wait | Keep current enum before thesis; document semantics and use activity/assignee to explain state | Enum migration is high-risk and deferred |
| TKT-09 | LOW | Activity output | `backend/app/api/tickets.py:408-496` | Customers receive ticket activities including internal assignment/status details | Define customer-safe activity whitelist if activity is customer-facing | Could hide useful status history |

### Business assessment

The workflow is coherent enough for a small support operation: create, assign, work, wait, resolve, close, reopen. It should not be replaced before the thesis. The immediate priority is enforcing entity consistency and authorization. A richer triage workflow should be deferred until there is a clear reporting/SLA requirement.

## 4. Project and Task Audit

Projects support organization/service/subscription links, visibility, members, documents, tasks, progress, customer-visible tasks, comments, approvals and linked tickets. Progress is the percentage of non-cancelled tasks in `completed`; a project becomes completed only when all active tasks are completed.

Evidence: `backend/app/services/projects.py:21-65`, `backend/app/api/projects.py:219-1149`, `backend/app/models/project.py:59-185`.

Findings:

| ID | Severity | Module | Evidence | Business impact | Proposed fix | Risk |
|---|---|---|---|---|---|---|
| PRJ-01 | HIGH | Visibility | `backend/app/core/scoping.py:102-134` | “internal” hides a project from customers, but any staff assigned to the organization can see it; project membership is not staff-private access control | Rename/document visibility semantics or add a separate member-restricted policy in a later migration | Changing access now can lock staff out |
| PRJ-02 | HIGH | Assignees | `backend/app/services/assignment.py:74-119`, project task create/update | Task assignees only need to exist | Apply same eligible-assignee validator as tickets and require project access | Same policy risk as TKT-03 |
| PRJ-03 | MEDIUM | Terminal entities | `backend/app/services/projects.py:111-172` | A task can be created under a completed/cancelled project; a ticket can be linked to completed/cancelled tasks/projects | Reject new operational links to cancelled/completed entities unless explicitly reopening | Must preserve historical read access |
| PRJ-04 | MEDIUM | Member role integrity | `backend/app/api/projects.py:539-579` | Payload role is not required to match target user's actual account role; a staff user can be added with customer role and vice versa | Derive/validate member role from target account and manager policy | Existing inconsistent rows may need audit |
| PRJ-05 | MEDIUM | Activity | Project updates/visibility/member changes have no durable project activity table | Cannot explain who changed visibility/membership | Add project activity only after retention/audit design | Schema/migration required; deferred |
| PRJ-06 | LOW | UX maintainability | `frontend/src/pages/ProjectDetailPage.jsx` is 1,939 lines; activity tab says “coming soon” | High regression risk and mixed interaction patterns | Split by existing tabs/domain sections in Phase 3 | Refactor risk if mixed with business changes |
| PRJ-07 | INFO | Drag/drop | `frontend/src/pages/ProjectDetailPage.jsx:133` | Explicit TODO, but not required for workflow | Defer; status controls already work | None |

There is no task dependency model. That is acceptable for the thesis because dependency management is not required to demonstrate ticket-to-project execution.

## 5. Subscription and Service Audit

### Current source of truth

The current design is a combination of stored state and dates, but without a single resolver:

- `Subscription.status` is stored.
- `Subscription.end_date`, `current_period_end`, and `next_billing_date` are stored.
- Celery mutates `Subscription.status` based on `trial_end_date` and `next_billing_date`.
- `Service.status` is separately stored and copied only when selected subscription operations explicitly call `sync_service_from_subscription`.
- The service UI computes expiry independently from `Service.expiry_date`.

This is internally inconsistent. The effective business status should be computed by one function, with terminal manual states (`cancelled`, `suspended` if later added) taking precedence, contractual `end_date` next, then billing state. Stored status may remain for filtering and jobs, but all writers and serializers must use the same resolver.

### Confirmed defect

`check_subscriptions()` ignores `end_date`, uses a seven-day grace window after `next_billing_date`, commits the subscription status, and never synchronizes the linked service. `sync_service_from_subscription()` maps `expired` to service `inactive`, not `expired`. The UI displays `service.status` and an independently computed expiry chip, producing “Active” plus “Expired”.

Evidence: `backend/app/tasks/subscription_checker.py:6-52`, `backend/app/services/service_sync.py:12-66`, `backend/app/models/subscription.py:26-55`, `backend/app/models/service.py:14-31`, `frontend/src/pages/ServicesPage.jsx:17-53,109-128`.

| ID | Severity | Module | Evidence | Business impact | Proposed fix | Risk |
|---|---|---|---|---|---|---|
| SUB-01 | HIGH | Expiry | checker ignores `end_date` | Contract-ended subscriptions remain active/past-due | Add pure effective-status resolver and use it in checker/API | Must define end-date inclusive boundary |
| SUB-02 | HIGH | Service sync | checker never calls service sync | Service badge remains stale after scheduled transition | Sync linked service in same DB transaction without nested commit | Refactor transaction boundaries |
| SUB-03 | HIGH | Customer UI | `useSubscriptions`, `SubscriptionDashboard`, `SubscriptionDetail` import `@/erp` | Active customer route calls removed Frappe/ERPNext contract | Replace with existing FastAPI subscription/invoice APIs; no route change | UI data shape mapping required |
| SUB-04 | MEDIUM | Period semantics | expiry notifier says expired on `current_period_end == today`, checker marks expired after grace | Customer communication contradicts stored state | Distinguish service-period end from payment grace, or align wording | Business wording decision |
| SUB-05 | MEDIUM | Deletion | two permanent-delete endpoints detach invoices/services/projects | Historical relation is lost even when financial records remain | Prefer archive/cancel; reserve permanent deletion for dependency-free erroneous records | Existing admin UI exposes permanent delete |

Boundary rule recommended for current schema: `cancelled` wins; `expired` when `end_date < today`; `past_due` according to unpaid billing grace; `scheduled` cannot be represented without enum migration and should be deferred; `end_date == today` remains active through that date. Timezone should use business-local `date` consistently.

### Delete/archive decision

| Entity | Archive | Soft delete | Hard delete | Reason |
|---|---:|---:|---:|---|
| Ticket | Yes | Yes | Exceptional only | Replies, attachments, SLA and audit value |
| Project | Yes/cancel | Yes | No normal UI | Linked tasks/tickets/documents |
| Task | Yes/cancel | Yes | No normal UI | Progress and activity history |
| Organization/customer | Yes | Yes | Exceptional only | Tenant ownership root |
| Service | Yes/inactive | Yes | Dependency-free error only | Ticket/project/subscription references |
| Subscription | Yes/cancel | Yes | Dependency-free error only | Accounting and entitlement history |
| User/staff | Deactivate | Yes | Dependency-free error only | Auth/activity/assignment history |
| Contact/address | Optional | Optional | Allowed with dependency check | Lower historical risk |
| AI records | Retain with ticket | Ticket cascade only | No independent delete | Model traceability |

## 6. Staff Presence and Assignment Audit

No presence system exists. There is no heartbeat, `last_seen_at`, `presence_status`, `availability_status`, or `show_presence`. The only similar value is `User.last_login_at`, and auto-assignment treats a login within `ASSIGN_ONLINE_WINDOW_SECONDS` as online.

Evidence: `backend/app/models/user.py:7-30`, `backend/app/services/auto_assign.py:78-138`, `frontend/src/pages/ProfilePage.jsx`.

Current auto-assignment:

1. Candidate must be active staff assigned to the ticket organization.
2. Workload is active project task count; only when task count is zero does it fall back to active assigned tickets. It therefore does not combine both workloads.
3. Skill is inferred from historical resolved tickets with matching AI category, with a cold-start baseline.
4. Online score uses recent login.
5. Ties prefer least recently assigned.
6. Redis lock reduces concurrent assignment races.

| ID | Severity | Module | Evidence | Business impact | Proposed fix | Risk |
|---|---|---|---|---|---|---|
| STF-01 | HIGH | Online signal | `auto_assign.py:115-123` uses `last_login_at` | A user who logged in recently but left is shown/scored as online | Stop naming this online; add heartbeat-backed presence in a separate phase | Realtime schema/API/UI work |
| STF-02 | HIGH | Eligibility | no project-member/visibility check in `_compute_scores` | Staff can be auto-assigned to a linked project they should not work on under a future private policy | Include project access/member eligibility when ticket has project | Current visibility semantics must be resolved first |
| STF-03 | MEDIUM | Workload | task count replaces, rather than adds to, ticket count | Workload ranking can undercount busy agents | Weighted sum of active tasks and tickets | Requires calibration |
| STF-04 | MEDIUM | Skill | skill is historical category count, not declared skill | Sparse history can misrepresent competence | Present as experience score; add explicit skills only if thesis scope needs it | New schema otherwise |
| STF-05 | MEDIUM | Privacy | no `show_presence` | Requested privacy behavior cannot work | Add migration + heartbeat endpoint + profile toggle in an isolated implementation | Cross-layer change; defer until critical fixes pass |

Presence is a high-value improvement, not a critical fix. It should be implemented only as a small explicit subsystem with privacy rules and tests; `last_login_at` must not be relabeled as real-time presence.

## 7. AI and Groq Audit

### Runtime pipeline

```text
Ticket text -> sanitizer -> injection check (classification/reply header only)
-> prompt -> Groq chat completions -> JSON/text parsing
-> DB prediction/summary/suggestion -> staff-only UI
```

Configuration:

- Default model: `llama-3.1-8b-instant` via `AI_MODEL`.
- Timeout: 30 seconds.
- Retry: one retry for timeout only; no structured retry for 429/5xx.
- Classification: temperature 0.2, 256 tokens, plain JSON instruction but no API JSON mode/schema.
- Reply: temperature 0.5, 300 tokens.
- Summary: temperature 0.3, 300 tokens.
- Feature flag: `AI_FEATURES_ENABLED`.

Evidence: `backend/app/config.py:64-66`, `backend/app/services/ai/groq_client.py:16-48`, classifier/reply/API files.

### Evaluation dataset

File audited: `eval/ticket_bank_final_merged_v3.csv`.

- 47 rows, 47 unique IDs, 47 unique ticket texts.
- All six human/model label columns are complete.
- No exact overlap with the three few-shot prompt examples.
- Basic regex scan found no email address, phone number, IPv4 address or URL.
- Category class support by rater 1: technical 14, billing 9, general 6, domain 5, email 5, hosting 4, security 4.
- Priority class support by rater 1: low 15, medium 14, urgent 11, high 7.

Recomputed results using `eval/analyze_eval.py` manual formulas:

| Task | Rater agreement | Cohen kappa | Model accuracy | Macro precision | Macro recall | Macro F1 |
|---|---:|---:|---:|---:|---:|---:|
| Category | 39/47 (83.0%) | 0.794 | 0.894 | 0.892 | 0.931 | 0.904 |
| Priority | 42/47 (89.4%) | 0.854 | 0.617 | 0.686 | 0.613 | 0.573 |

Priority is materially weak: urgent recall is 0.27 and low recall is 0.47 against the script's chosen rater-1 truth. This does not support automated priority assignment.

Category disagreements (the requested eight):

| Ticket | Rater 1 | Rater 2 | Model | Audit comment |
|---|---|---|---|---|
| T001 | general | hosting | general | Ambiguous product question; adjudication needed |
| T002 | general | technical | general | How-to vs technical boundary; adjudication needed |
| T008 | technical | domain | domain | Model agrees with rater 2; rater 1 must not be automatic truth |
| T009 | domain | general | domain | Model agrees with rater 1 |
| T010 | domain | general | domain | Model agrees with rater 1 |
| T011 | domain | general | domain | Model agrees with rater 1 |
| T013 | technical | general | domain | Three-way conflict; highest adjudication priority |
| T014 | email | general | email | Model agrees with rater 1 |

Priority disagreements: T015, T018, T030, T032 and T047. The report requested “8 disagreements”, which is true only for category; priority has five additional disagreements.

The script's `majority_label(a, b)` returns rater 1 on every disagreement (`eval/analyze_eval.py:62-63`). Therefore the reported model metrics are provisional, not adjudicated ground truth. A third independent reviewer or a written tie-break rubric is required. The current files do not prove that the two raters labeled independently or blind; that remains an open methodological question.

### AI findings

| ID | Severity | Module | Evidence | Business impact | Proposed fix | Risk |
|---|---|---|---|---|---|---|
| AI-01 | HIGH | Summary prompt | `backend/app/api/ai.py:188-273` | Ticket text shares one user message with instructions and has no injection guard | Add system prompt, delimit untrusted content, run guard over all content | Guard false positives |
| AI-02 | HIGH | Reply history | `reply_suggester.py:48-84` | Injection in a public reply bypasses the current check | Guard all included replies after sanitization; treat content as quoted data | Could disable suggestions on legitimate security discussions |
| AI-03 | MEDIUM | Sensitive logging | `prompt_guard.py:16-20` logs first 120 chars | Flagged customer content can enter production logs | Log ticket/event identifier and pattern class, not content | Reduced debugging detail |
| AI-04 | MEDIUM | Structured output | `classifier.py:79-111` uses `json.loads` on free text | Malformed output returns unavailable with no repair/schema mode | Use supported JSON object mode or strict extraction/validation | Groq model capability varies |
| AI-05 | MEDIUM | Model evidence | dataset script uses rater 1 on ties | Inflated/biased ground truth claims | Add `adjudicated_label`, preserve both raters, recompute metrics/CI/confusion matrix | Requires human adjudication |
| AI-06 | MEDIUM | Priority automation | priority macro F1 0.573, urgent recall 0.27 | Business-critical incidents may be under-prioritized | Keep as suggestion; require staff review; show confidence/reason | None if advisory |
| AI-07 | MEDIUM | Audit/provenance | summaries do not store model/version; accepted suggestion has no accepted-by/time/reject event | Cannot reproduce or audit human use of AI | Add provenance/audit fields in later migration | Schema change; defer unless thesis requires |
| AI-08 | LOW | Retry/rate limit | `groq_client.py:29-46` retries timeout only | 429/5xx cause avoidable failures | Bounded exponential retry honoring Retry-After | Increased latency |

AI must remain advisory. It currently does not auto-close, auto-send customer replies, or alter project visibility, which is the correct safety posture.

## 8. Security Audit

| ID | Severity | Finding | File/evidence | Impact |
|---|---|---|---|---|
| SEC-01 | CRITICAL | Email thread sender authorization missing | `email_piping.py:139-173,239-272` | Cross-ticket message/attachment injection |
| SEC-02 | HIGH | OAuth tokens plaintext at rest | `models/gsc_connection.py:14-17`, `models/ga4_connection.py:14-17` | DB read compromise exposes long-lived Google access |
| SEC-03 | HIGH | Assignment authorization incomplete | `services/assignment.py:16-71` | Cross-role/cross-org assignment and project-member pollution |
| SEC-04 | HIGH | Task-inferred project not org-validated | `api/tickets.py:157-174,583-594` | Cross-tenant relationship corruption and data exposure paths |
| SEC-05 | HIGH | Access and refresh tokens in localStorage | `frontend/src/api/client.js:15-24,71-99` | Any successful XSS can steal both token classes |
| SEC-06 | HIGH | Socket.IO checks JWT and active user but not DB session `jti`/blacklist | `backend/app/socketio_server.py:29-57` | Revoked access token may retain realtime access until expiry |
| SEC-07 | MEDIUM | Password minimum is six characters | `api/auth.py:442-459,584-627`, `api/users.py:135-160` | Weak credentials remain allowed |
| SEC-08 | MEDIUM | Seed has a usable default password if env is omitted | `backend/scripts/seed_base.py:12-15` | Accidental production seed creates known credential |
| SEC-09 | MEDIUM | Eval runner contains `staff123` fallbacks and fixed seeded org ID | `eval/run_ai_classification_eval.py:14-17,55-61` | Unsafe operational practice if pointed at a non-test environment |
| SEC-10 | MEDIUM | AI summary/reply prompt isolation incomplete | AI-01/AI-02 | Prompt injection and misleading staff output |
| SEC-11 | MEDIUM | Public avatar privacy relies on unguessable UUID | `api/auth.py:311-350` | URL leakage grants unauthenticated access until avatar changes |
| SEC-12 | LOW | AI health endpoint unauthenticated | `api/ai.py:43-49` | Exposes model/configuration state |

Positive controls confirmed: production config rejects insecure JWT defaults and wildcard CORS; refresh tokens are hashed in session storage and rotated; access JWTs include jti and HTTP dependencies verify active session; reset OTP is rate-limited, attempt-limited, row-locked and single-use; file paths are sanitized and storage resolution blocks traversal; attachment downloads check ticket scope; internal notes are filtered for customers.

## 9. UX Audit

The worktree already contains a responsive design foundation and ticket-focused UI refactor. Large tables now commonly use `ResponsiveTableViewport` with mobile cards and sticky desktop/tablet headers. Ticket list/detail/new-ticket have dedicated components. Remaining issues are architectural consistency rather than a need for a visual redesign.

| Severity | Area | Evidence | Finding | Impact |
|---|---|---|---|---|
| HIGH | Customer subscriptions | `SubscriptionDashboard`, `SubscriptionDetail`, `useSubscriptions`, `useInvoices` | Uses removed ERP/Frappe data shapes and methods | Route can fail despite working FastAPI backend |
| HIGH | Ticket assignment UI/API | New/detail pages hide invalid options by role, backend does not enforce all rules | Frontend-only safety can be bypassed | Data integrity |
| MEDIUM | Project detail | 1,939-line page; duplicated task/dialog sections | UI and business interactions are tightly coupled | Regression risk |
| MEDIUM | Modal consistency | `SubscriptionDashboard` custom overlay; `SubscriptionDetail` and SEO use `window.confirm`; staff assignments use native confirm | Focus, Escape, mobile and destructive confirmation behavior differ | Accessibility and trust |
| MEDIUM | Feedback | Some pages still use centered spinners (`Notifications`, `SystemStatus`, account security) while shared skeleton states exist | Inconsistent loading experience | Perceived quality |
| MEDIUM | Activity | Project activity tab displays “coming soon” | Visible unfinished feature | Thesis credibility |
| MEDIUM | Status vocabulary | ERP customer subscription UI uses `Active/Completed/Past Due Date`; FastAPI uses lowercase `active/expired/past_due/cancelled` | User sees inconsistent concepts | Confusion and mapping errors |
| LOW | Hardcoded ticket types | `frontend/src/api/tickets.js:150-174` and `NewTicketPage.jsx:35-48` duplicate backend enum | Enum can drift | Maintenance risk |
| LOW | Accessibility | Remaining icon/native confirm/custom modal paths lack consistent labels/focus handling | Keyboard/mobile usability gaps | Accessibility |

Responsive foundations present: desktop table/mobile card split, `overflow-x-auto` for tablet, app shell `overflow-x-hidden`, mobile drawer navigation, shared feedback states, semantic tokens, and trend charts with explicit height/fullscreen modal. Visual verification still must be repeated after functional fixes at 360, 390, 768, 1024 and 1440 pixels.

## 10. Business Logic Findings

1. Ticket is correctly the operational center and Project/Task are execution context. AI currently supports rather than dominates that workflow.
2. Project `visibility` is customer visibility, not private membership visibility. Thesis/demo language must not claim private staff projects unless the policy is implemented.
3. Subscription entitlements and billing delinquency are conflated. `end_date`, period end, due date and grace expiration need documented precedence.
4. “Online” is currently recent login, so the UI and defense must not claim realtime presence.
5. Auto-assignment is more than round-robin, but workload is incomplete and historical AI category is an experience proxy rather than an explicit skill model.
6. Archive/delete policy is inconsistent across entities. Cancellation/deactivation already functions as soft deletion for projects/tasks/users/subscriptions and should be the default.
7. The customer subscription route is a disconnected legacy feature. The admin route is the correct current implementation.
8. Ticket types are valid and include Renewal; no enum replacement is justified before examining production data and reporting needs.

## 11. Test Coverage

Static inventory found 603 backend test functions across 52 files and 20 frontend test files. Strong areas include auth/session/reset, ticket scoping/replies/delete/archive, projects/tasks/members/approvals, invoice state, file validation, GSC, and AI unit behavior.

Material gaps to add before claiming readiness:

- Email reply sender authorization for Message-ID, References and subject fallback.
- Ticket/task assignment eligibility: inactive, customer, wrong org, project access.
- Task-inferred project cross-org validation on create and update.
- Subscription `end_date` boundaries: yesterday, today, tomorrow, cancelled, no end date; linked service synchronization.
- GA4 staff organization resolution and callback ownership metadata.
- AI summary injection, reply-history injection, malformed JSON, very long mixed-language content and no-sensitive-log behavior.
- Socket.IO revoked-session rejection.
- Customer subscription route smoke test against FastAPI contract.
- Presence privacy/heartbeat tests only if presence is implemented.

Software tests and model evaluation must remain separate. “603 tests” says nothing about model quality; the 47-ticket evaluation says nothing about authorization or application correctness.

## 12. Prioritized Fix Plan

### Critical fixes

1. **Email sender-to-ticket authorization**: add a pure authorization helper, quarantine/create-new behavior, and focused threading tests.
2. **Subscription effective status and service sync**: central resolver, checker transaction fix, API serialization consistency, and date-boundary tests. Do not silently run a production data correction.
3. **Assignment eligibility**: one validator used by ticket create/update/assign and task create/update; add cross-role/cross-org/inactive tests.
4. **Ticket project/task integrity**: validate inferred project org/access/status and task state on create/update; add security tests.
5. **AI prompt boundaries**: system prompt + untrusted-content delimiter + guard over summary and conversation history; remove content from security logs.

### High-value improvements

6. Fix GA4 staff organization resolution to match GSC and add tests.
7. Replace the active customer subscription ERP/Frappe calls with existing FastAPI APIs, keeping routes/workflow stable.
8. Add effective status to service/subscription UI badges and remove contradictory status rendering.
9. Add Socket.IO session-jti validation at connection.
10. Replace remaining destructive native confirms in touched critical workflows with the existing shared confirm dialog.

### Deferred

- Realtime presence with heartbeat and privacy toggle: valuable, but requires schema/API/UI/Socket lifecycle work and should not be mixed with critical fixes.
- New ticket status enum (`triaged`, `assigned`, separate waits): migration/reporting impact is too high before thesis.
- Project member-private visibility: current “internal” meaning must first be agreed with stakeholders.
- Full system audit-log table: requires retention and PII policy.
- Task dependencies and drag-and-drop: not needed for the core thesis workflow.
- AI fine-tuning or autonomous priority: current priority evidence is inadequate.
- Permanent-delete expansion or bulk delete: inconsistent with audit/history requirements.

### Small implementation groups

The work should be reviewable as separate change groups, not one broad commit:

1. email thread authorization + tests;
2. ticket/project/assignment integrity + tests;
3. subscription status resolver/sync + tests;
4. AI prompt safety + tests;
5. GA4 scoping + tests;
6. customer subscription FastAPI migration + frontend tests;
7. final responsive/E2E verification and reports.

No production migration or data correction should run automatically. If a data correction becomes necessary, first report affected row counts, SQL/update semantics, transaction/rollback plan, and dry-run output.

## Open Questions

1. Were rater 1 and rater 2 independent and blind to model output and each other? Source files do not prove this.
2. Who has authority to adjudicate category/priority disagreements?
3. Is `end_date` inclusive through the entire date, and does billing grace preserve service entitlement?
4. Should admins be valid operational assignees, or only staff?
5. Does “internal project” mean hidden from customers only, or restricted to explicit staff members?
6. Which inbound email aliases/contact addresses are authorized to reply for an organization?
7. Is the customer `/subscriptions` route still required, or should customers use `/services` and `/invoices` only?

