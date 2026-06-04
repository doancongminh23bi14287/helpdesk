# Subscription & Invoice Improvements — Design Spec
**Date:** 2026-06-04  
**Status:** Approved

---

## Overview

Three improvements to the subscription/invoice billing system:

1. **Create Subscription form UX** — replace raw ID inputs with dropdowns
2. **Tax support** — per-plan tax rate threaded through to invoice generation
3. **Annual billing** — per-subscription billing cycle with discounted annual price

---

## What Is Already Built (No Work Required)

- `invoices` table already has `subtotal`, `tax_rate`, `tax_amount` columns
- `InvoiceDetailModal` (admin + customer) already renders Subtotal / Tax (X%) / Total
- Plan dropdown in Create Subscription already loads from `GET /api/subscription-plans`
- `subscription_plans.billing_cycle` already has `monthly/quarterly/yearly` enum; `yearly` is used as the canonical "annual" value

---

## Section 1 — DB Schema Changes

### Migration `0002_add_plan_tax_rate.py`
```
subscription_plans:
  + tax_rate  DECIMAL(5,2)  NOT NULL DEFAULT 0.00
```

### Migration `0003_add_annual_billing.py`
```
subscription_plans:
  + annual_price  DECIMAL(15,2)  NULL

subscriptions:
  + billing_cycle  ENUM('monthly', 'yearly')  NOT NULL DEFAULT 'monthly'
```

**Convention:** `yearly` is the stored enum value; the frontend labels it "Annual" everywhere.

---

## Section 2 — Backend Logic

### Schemas (`backend/app/schemas/subscription.py`)

| Schema | New Fields |
|---|---|
| `SubscriptionPlanCreate` | `tax_rate: Decimal = 0.00`, `annual_price: Optional[Decimal] = None` |
| `SubscriptionPlanUpdate` | same as above (all optional) |
| `SubscriptionPlanOut` | `tax_rate`, `annual_price` |
| `SubscriptionCreate` | `billing_cycle: Literal['monthly', 'yearly'] = 'monthly'` |
| `SubscriptionOut` | `billing_cycle` |

### `services/billing.py` — `create_subscription()`

- Accept `billing_cycle` from the incoming request
- **If `billing_cycle == 'yearly'`:** `unit_price = plan.annual_price` if set, else `round(resolved_monthly_price × 12 × 0.8, 2)`
- **If `billing_cycle == 'monthly'`:** `unit_price = resolved_monthly_price` (unchanged)
- Freeze `billing_cycle` on the subscription row
- Pass `subscription.billing_cycle` to `compute_period_end()` for period-end calculations

### `services/invoice_service.py` — `create_invoice_from_subscription()`

- Replace hardcoded `tax_rate = Decimal("10.00")` with `plan.tax_rate`
- Recalculate: `tax_amount = subtotal × plan.tax_rate / 100`, `total = subtotal + tax_amount`

### Subscription Plans API (`api/subscription_plans.py`)

- `GET /api/subscription-plans` — already exists; add `tax_rate` + `annual_price` to response
- `POST /api/subscription-plans` + `PUT /api/subscription-plans/{id}` — already exist; accept new fields

---

## Section 3 — Frontend

### 3a. Create Subscription Modal (`SubscriptionsPage.jsx`)

| Field | Change |
|---|---|
| Organisation ID (number input) | → `<select>` from `GET /api/organizations`, label: `org.name (org.code)` |
| Price List ID (number input) | → `<select>` from `GET /api/price-lists`, label: `list.name`, with "— None —" option |
| Billing Cycle | New toggle: `Monthly \| Annual`. When Annual selected, show computed price: `selected_plan.annual_price` or `unit_price × 12 × 0.8` |
| Plan | Unchanged (already a dropdown from API) |
| Start Date | Unchanged |

### 3b. New Admin Subscription Plans Page

**File:** `frontend/src/pages/admin/SubscriptionPlansPage.jsx`  
**Route:** `/admin/subscription-plans`  
**Nav:** Add "Subscription Plans" link to admin sidebar

**Table columns:** Name, Code, Default Billing Cycle, Tax Rate (%), Monthly Price (item.unit_price), Annual Price (plan.annual_price or auto), Active badge

**Create/Edit modal fields:**
- Code (text, required)
- Name (text, required)
- Description (textarea, optional)
- Item (dropdown from `GET /api/items`)
- Default Billing Cycle (`monthly` | `yearly`)
- Tax Rate % (number, default 0)
- Annual Price override (number, blank = auto-calculate as monthly × 12 × 0.8)
- Active (toggle)

### 3c. Customer Services Page (`ServicesPage.jsx`)

- Add billing cycle badge to each service card: `Monthly` or `Annual`
- Source: `service.billing_cycle` — the `services` table already has a `billing_cycle` column (`monthly/quarterly/yearly`) and `subscription_id` FK; no propagation needed
- The services API just needs to include `billing_cycle` in its response shape (verify and add if missing)

---

## Files to Create / Modify

### Backend
| File | Change |
|---|---|
| `alembic/versions/0002_add_plan_tax_rate.py` | New migration |
| `alembic/versions/0003_add_annual_billing.py` | New migration |
| `app/models/subscription.py` | Add `tax_rate`, `annual_price` to `SubscriptionPlan`; add `billing_cycle` to `Subscription` |
| `app/schemas/subscription.py` | Add new fields to plan + subscription schemas |
| `app/services/billing.py` | Handle billing_cycle + annual price in `create_subscription()` |
| `app/services/invoice_service.py` | Use `plan.tax_rate` instead of hardcoded 10% |
| `app/api/subscription_plans.py` | Accept/return new plan fields |
| `app/api/subscriptions.py` | Accept `billing_cycle` in create; return it in list/get |
| `app/api/services.py` | Ensure `billing_cycle` is included in service response (model column already exists) |

### Frontend
| File | Change |
|---|---|
| `src/pages/admin/SubscriptionsPage.jsx` | Replace raw inputs with dropdowns; add billing cycle toggle |
| `src/pages/admin/SubscriptionPlansPage.jsx` | New page |
| `src/pages/ServicesPage.jsx` | Add billing cycle badge to service cards |
| `src/api/subscriptions.js` | Add `createSubscriptionPlan`, `updateSubscriptionPlan` if not present |
| `src/App.jsx` | Add `/admin/subscription-plans` route |
| Admin sidebar component | Add "Subscription Plans" nav link |

---

## Data Integrity

- Existing subscriptions get `billing_cycle = 'monthly'` (migration default)
- Existing plans get `tax_rate = 0.00` and `annual_price = NULL` (migration defaults)
- Existing invoices are unaffected (their stored `tax_rate` values are preserved)
- `compute_period_end()` already handles `'yearly'` correctly

---

## Out of Scope

- `quarterly` billing cycle: kept in DB enum, hidden from new create forms but not removed (preserves existing data)
- Manual invoice tax rate: remains as-is (already stored per-invoice)
- Customer-facing subscription plan selection UI
