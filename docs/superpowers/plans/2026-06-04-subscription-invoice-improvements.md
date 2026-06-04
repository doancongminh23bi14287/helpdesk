# Subscription & Invoice Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-plan tax rate, per-subscription annual billing cycle, and UX improvements to the Create Subscription form.

**Architecture:** Two Alembic migrations add columns; model/schema/service layers thread new fields through invoice generation and subscription creation; three frontend changes complete the feature (SubscriptionsPage form dropdowns + billing toggle, new SubscriptionPlansPage, ServicesPage billing badge).

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, MariaDB, Python 3.12, React 18, Vite, Tailwind CSS, React Router v6

---

## File Map

| File | Action |
|---|---|
| `backend/alembic/versions/0008_add_plan_tax_rate.py` | CREATE |
| `backend/alembic/versions/0009_add_annual_billing.py` | CREATE |
| `backend/app/models/subscription.py` | MODIFY — add `tax_rate`, `annual_price`, `billing_cycle` columns |
| `backend/app/schemas/subscription.py` | MODIFY — add fields to 5 schemas |
| `backend/app/services/billing.py` | MODIFY — `create_subscription()` annual price logic |
| `backend/app/services/invoice_service.py` | MODIFY — use `plan.tax_rate` |
| `backend/app/schemas/organization.py` | MODIFY — add `billing_cycle` to `ServiceOut` |
| `backend/tests/test_billing_improvements.py` | CREATE — tests for billing + invoice changes |
| `frontend/src/pages/admin/SubscriptionsPage.jsx` | MODIFY — form UX (org/price-list dropdowns, billing cycle toggle) |
| `frontend/src/pages/admin/SubscriptionPlansPage.jsx` | CREATE — plan management page |
| `frontend/src/pages/ServicesPage.jsx` | MODIFY — billing cycle badge on cards |
| `frontend/src/App.jsx` | MODIFY — add `/admin/subscription-plans` route |
| `frontend/src/components/layout/Layout.jsx` | MODIFY — add "Subscription Plans" nav entry |

---

## Task 1: Migration 0008 — add `tax_rate` to `subscription_plans`

**Files:**
- Create: `backend/alembic/versions/0008_add_plan_tax_rate.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/0008_add_plan_tax_rate.py
"""add tax_rate to subscription_plans

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column("tax_rate", sa.DECIMAL(5, 2), nullable=False, server_default="0.00"),
    )


def downgrade() -> None:
    op.drop_column("subscription_plans", "tax_rate")
```

- [ ] **Step 2: Run the migration**

```bash
cd ~/helpdesk-system/backend && source venv/bin/activate
alembic upgrade head
```

Expected output ends with: `Running upgrade 0007 -> 0008, add tax_rate to subscription_plans`

- [ ] **Step 3: Verify column exists**

```bash
python3 -c "
import pymysql, os
from dotenv import load_dotenv; load_dotenv()
c = pymysql.connect(host='127.0.0.1', port=3306, user='helpdesk', password='helpdesk_pass', db='helpdesk_db')
cur = c.cursor()
cur.execute('SHOW COLUMNS FROM subscription_plans LIKE \"tax_rate\"')
print(cur.fetchone())
c.close()
"
```

Expected: a non-None tuple containing `tax_rate`.

---

## Task 2: Migration 0009 — add `annual_price` + `billing_cycle`

**Files:**
- Create: `backend/alembic/versions/0009_add_annual_billing.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/0009_add_annual_billing.py
"""add annual_price to subscription_plans and billing_cycle to subscriptions

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column("annual_price", sa.DECIMAL(15, 2), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column(
            "billing_cycle",
            sa.Enum("monthly", "yearly", name="sub_subscription_billing_cycle"),
            nullable=False,
            server_default="monthly",
        ),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "billing_cycle")
    op.drop_column("subscription_plans", "annual_price")
```

- [ ] **Step 2: Run the migration**

```bash
alembic upgrade head
```

Expected: `Running upgrade 0008 -> 0009, add annual_price to subscription_plans and billing_cycle to subscriptions`

- [ ] **Step 3: Verify columns exist**

```bash
python3 -c "
import pymysql
c = pymysql.connect(host='127.0.0.1', port=3306, user='helpdesk', password='helpdesk_pass', db='helpdesk_db')
cur = c.cursor()
cur.execute('SHOW COLUMNS FROM subscription_plans LIKE \"annual_price\"')
print('annual_price:', cur.fetchone())
cur.execute('SHOW COLUMNS FROM subscriptions LIKE \"billing_cycle\"')
print('billing_cycle:', cur.fetchone())
c.close()
"
```

Expected: both print non-None tuples.

---

## Task 3: Update SQLAlchemy models

**Files:**
- Modify: `backend/app/models/subscription.py`

- [ ] **Step 1: Replace the file content with the updated models**

```python
from sqlalchemy import BigInteger, Column, String, Text, Integer, Date, DateTime, Enum, Boolean, DECIMAL, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    billing_cycle = Column(
        Enum("monthly", "quarterly", "yearly", name="sub_billing_cycle"),
        nullable=False,
        default="monthly",
        server_default="monthly",
    )
    trial_days = Column(Integer, nullable=False, default=0, server_default="0")
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    tax_rate = Column(DECIMAL(5, 2), nullable=False, default=0, server_default="0.00")
    annual_price = Column(DECIMAL(15, 2), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    subscription_plan_id = Column(BigInteger, ForeignKey("subscription_plans.id"), nullable=False)
    price_list_id = Column(BigInteger, ForeignKey("price_lists.id"), nullable=True)
    status = Column(
        Enum("trial", "active", "past_due", "cancelled", "expired", name="subscription_status"),
        nullable=False,
        default="active",
        server_default="active",
    )
    billing_cycle = Column(
        Enum("monthly", "yearly", name="sub_subscription_billing_cycle"),
        nullable=False,
        default="monthly",
        server_default="monthly",
    )
    start_date = Column(Date, nullable=False)
    trial_end_date = Column(Date, nullable=True)
    current_period_start = Column(Date, nullable=False)
    current_period_end = Column(Date, nullable=False)
    next_billing_date = Column(Date, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)
    unit_price = Column(DECIMAL(15, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: Verify Python parses the module correctly**

```bash
python3 -c "from app.models.subscription import SubscriptionPlan, Subscription; print('OK')"
```

Expected: `OK`

---

## Task 4: Update Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/subscription.py`

- [ ] **Step 1: Replace the file content**

```python
from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional
from datetime import date, datetime
from decimal import Decimal


class SubscriptionPlanCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    item_id: int
    billing_cycle: Literal["monthly", "quarterly", "yearly"] = "monthly"
    trial_days: int = 0
    is_active: bool = True
    tax_rate: Decimal = Decimal("0.00")
    annual_price: Optional[Decimal] = None


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    billing_cycle: Optional[Literal["monthly", "quarterly", "yearly"]] = None
    trial_days: Optional[int] = None
    is_active: Optional[bool] = None
    tax_rate: Optional[Decimal] = None
    annual_price: Optional[Decimal] = None


class SubscriptionPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: Optional[str] = None
    item_id: int
    billing_cycle: str
    trial_days: int
    is_active: bool
    tax_rate: Decimal
    annual_price: Optional[Decimal] = None
    created_at: datetime


class SubscriptionCreate(BaseModel):
    org_id: int
    plan_id: int
    start_date: date
    price_list_id: Optional[int] = None
    billing_cycle: Literal["monthly", "yearly"] = "monthly"


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    org_id: int
    subscription_plan_id: int
    price_list_id: Optional[int] = None
    status: str
    billing_cycle: str
    start_date: date
    trial_end_date: Optional[date] = None
    current_period_start: date
    current_period_end: date
    next_billing_date: date
    cancelled_at: Optional[datetime] = None
    unit_price: Decimal
    created_at: datetime
    updated_at: datetime
    # enriched fields
    plan_name: Optional[str] = None
    org_name: Optional[str] = None
```

- [ ] **Step 2: Verify Python parses the module**

```bash
python3 -c "from app.schemas.subscription import SubscriptionPlanCreate, SubscriptionCreate, SubscriptionOut; print('OK')"
```

Expected: `OK`

---

## Task 5: Write tests for billing service + invoice service

**Files:**
- Create: `backend/tests/test_billing_improvements.py`

- [ ] **Step 1: Create the test file**

```python
# backend/tests/test_billing_improvements.py
"""Tests for annual billing cycle and per-plan tax rate."""
from decimal import Decimal
from datetime import date


# ─── Annual billing: create_subscription ────────────────────────────────────

def test_monthly_subscription_uses_resolved_price(client, admin_token, db, client_org):
    """Creating a monthly subscription freezes the item's unit_price."""
    from app.models.item import Item
    from app.models.subscription import SubscriptionPlan, Subscription

    item = Item(name="Test SaaS", code="TST-001", unit_price=Decimal("500000"), type="service")
    db.add(item)
    db.commit()

    plan = SubscriptionPlan(
        code="PLAN-M",
        name="Monthly Plan",
        item_id=item.id,
        billing_cycle="monthly",
        tax_rate=Decimal("0.00"),
    )
    db.add(plan)
    db.commit()

    r = client.post(
        "/api/subscriptions",
        json={"org_id": client_org.id, "plan_id": plan.id, "start_date": "2026-01-01", "billing_cycle": "monthly"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["billing_cycle"] == "monthly"
    assert Decimal(str(body["unit_price"])) == Decimal("500000")


def test_annual_subscription_uses_plan_annual_price_when_set(client, admin_token, db, client_org):
    """When plan.annual_price is set, annual subscription freezes that value."""
    from app.models.item import Item
    from app.models.subscription import SubscriptionPlan

    item = Item(name="Annual SaaS", code="ANN-001", unit_price=Decimal("500000"), type="service")
    db.add(item)
    db.commit()

    plan = SubscriptionPlan(
        code="PLAN-A-FIXED",
        name="Annual Plan Fixed",
        item_id=item.id,
        billing_cycle="yearly",
        tax_rate=Decimal("0.00"),
        annual_price=Decimal("4800000"),
    )
    db.add(plan)
    db.commit()

    r = client.post(
        "/api/subscriptions",
        json={"org_id": client_org.id, "plan_id": plan.id, "start_date": "2026-01-01", "billing_cycle": "yearly"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["billing_cycle"] == "yearly"
    assert Decimal(str(body["unit_price"])) == Decimal("4800000")


def test_annual_subscription_auto_calculates_price_when_annual_price_null(client, admin_token, db, client_org):
    """When plan.annual_price is None, unit_price = monthly * 12 * 0.8."""
    from app.models.item import Item
    from app.models.subscription import SubscriptionPlan

    item = Item(name="Auto Annual SaaS", code="AUTO-001", unit_price=Decimal("500000"), type="service")
    db.add(item)
    db.commit()

    plan = SubscriptionPlan(
        code="PLAN-A-AUTO",
        name="Annual Plan Auto",
        item_id=item.id,
        billing_cycle="monthly",
        tax_rate=Decimal("0.00"),
        annual_price=None,
    )
    db.add(plan)
    db.commit()

    r = client.post(
        "/api/subscriptions",
        json={"org_id": client_org.id, "plan_id": plan.id, "start_date": "2026-01-01", "billing_cycle": "yearly"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    expected = round(Decimal("500000") * Decimal("12") * Decimal("0.8"), 2)
    assert Decimal(str(body["unit_price"])) == expected  # 4800000.00


def test_annual_subscription_period_end_is_one_year(client, admin_token, db, client_org):
    """Annual subscription's current_period_end is ~1 year after start."""
    from app.models.item import Item
    from app.models.subscription import SubscriptionPlan

    item = Item(name="Period SaaS", code="PER-001", unit_price=Decimal("100000"), type="service")
    db.add(item)
    db.commit()

    plan = SubscriptionPlan(code="PLAN-PER", name="Period Plan", item_id=item.id)
    db.add(plan)
    db.commit()

    r = client.post(
        "/api/subscriptions",
        json={"org_id": client_org.id, "plan_id": plan.id, "start_date": "2026-01-01", "billing_cycle": "yearly"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["current_period_end"] == "2026-12-31"


# ─── Tax rate: invoice generation ───────────────────────────────────────────

def test_invoice_uses_plan_tax_rate(db, client_org):
    """create_invoice_from_subscription uses plan.tax_rate, not hardcoded 10%."""
    from app.models.item import Item
    from app.models.subscription import SubscriptionPlan, Subscription
    from app.services.invoice_service import create_invoice_from_subscription

    item = Item(name="Tax Test SaaS", code="TAX-001", unit_price=Decimal("1000000"), type="service")
    db.add(item)
    db.commit()

    plan = SubscriptionPlan(
        code="PLAN-TAX",
        name="Tax Test Plan",
        item_id=item.id,
        tax_rate=Decimal("8.00"),
    )
    db.add(plan)
    db.commit()

    today = date.today()
    sub = Subscription(
        org_id=client_org.id,
        subscription_plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        start_date=today,
        current_period_start=today,
        current_period_end=today,
        next_billing_date=today,
        unit_price=Decimal("1000000"),
    )
    db.add(sub)
    db.commit()

    invoice = create_invoice_from_subscription(sub.id, db)
    assert invoice.tax_rate == Decimal("8.00")
    assert invoice.tax_amount == Decimal("80000.00")
    assert invoice.total == Decimal("1080000.00")


def test_invoice_zero_tax_rate(db, client_org):
    """plan.tax_rate = 0 produces zero tax_amount."""
    from app.models.item import Item
    from app.models.subscription import SubscriptionPlan, Subscription
    from app.services.invoice_service import create_invoice_from_subscription

    item = Item(name="Zero Tax SaaS", code="ZT-001", unit_price=Decimal("500000"), type="service")
    db.add(item)
    db.commit()

    plan = SubscriptionPlan(
        code="PLAN-ZT",
        name="Zero Tax Plan",
        item_id=item.id,
        tax_rate=Decimal("0.00"),
    )
    db.add(plan)
    db.commit()

    today = date.today()
    sub = Subscription(
        org_id=client_org.id,
        subscription_plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        start_date=today,
        current_period_start=today,
        current_period_end=today,
        next_billing_date=today,
        unit_price=Decimal("500000"),
    )
    db.add(sub)
    db.commit()

    invoice = create_invoice_from_subscription(sub.id, db)
    assert invoice.tax_rate == Decimal("0.00")
    assert invoice.tax_amount == Decimal("0.00")
    assert invoice.total == Decimal("500000.00")
```

- [ ] **Step 2: Run the tests — expect failures (billing service not updated yet)**

```bash
cd ~/helpdesk-system/backend && source venv/bin/activate
pytest tests/test_billing_improvements.py -v 2>&1 | tail -20
```

Expected: 6 tests collected, most FAILED (services not yet updated).

---

## Task 6: Update billing service (`create_subscription`)

**Files:**
- Modify: `backend/app/services/billing.py`

- [ ] **Step 1: Replace `create_subscription()` with the annual-aware version**

Replace the entire `create_subscription` function (from `def create_subscription(` to the final `return sub`) with:

```python
def create_subscription(
    db: Session,
    org_id: int,
    plan_id: int,
    start_date: date,
    price_list_id: Optional[int] = None,
    billing_cycle: str = "monthly",
) -> Subscription:
    """
    Create a new subscription for an org.
    - billing_cycle: 'monthly' or 'yearly'. Annual price = plan.annual_price if set,
      else resolved_monthly * 12 * 0.8.
    - Fetches plan and org; raises ValueError if not found or inactive.
    - Computes period_end using billing_cycle (yearly = 1 year period).
    - If plan.trial_days > 0: status='trial', trial_end_date = start_date + trial_days.
    - Otherwise: status='active'.
    - Commits and returns the Subscription.
    """
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == plan_id,
        SubscriptionPlan.is_active.is_(True),
    ).first()
    if not plan:
        raise ValueError(f"Subscription plan {plan_id} not found or inactive")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError(f"Organization {org_id} not found")

    resolved_monthly = resolve_subscription_price(plan, org, db, price_list_id_override=price_list_id)

    if billing_cycle == "yearly":
        if plan.annual_price is not None:
            unit_price = Decimal(str(plan.annual_price))
        else:
            unit_price = round(resolved_monthly * Decimal("12") * Decimal("0.8"), 2)
    else:
        unit_price = resolved_monthly

    # Compute dates using the chosen billing_cycle
    period_end = compute_period_end(start_date, billing_cycle)
    next_billing = compute_next_billing_date(period_end)

    # Trial logic
    if plan.trial_days > 0:
        status = "trial"
        trial_end = start_date + timedelta(days=plan.trial_days)
    else:
        status = "active"
        trial_end = None

    sub = Subscription(
        org_id=org_id,
        subscription_plan_id=plan_id,
        price_list_id=price_list_id,
        status=status,
        billing_cycle=billing_cycle,
        start_date=start_date,
        trial_end_date=trial_end,
        current_period_start=start_date,
        current_period_end=period_end,
        next_billing_date=next_billing,
        unit_price=unit_price,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub
```

- [ ] **Step 2: Update the subscriptions API endpoint to pass `billing_cycle`**

In `backend/app/api/subscriptions.py`, replace the `create_subscription_endpoint` function body:

```python
@router.post("", response_model=SubscriptionOut, status_code=201)
def create_subscription_endpoint(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Create a new subscription (admin only)."""
    try:
        sub = create_subscription(
            db=db,
            org_id=payload.org_id,
            plan_id=payload.plan_id,
            start_date=payload.start_date,
            price_list_id=payload.price_list_id,
            billing_cycle=payload.billing_cycle,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_one(sub, db)
```

---

## Task 7: Update invoice service (use `plan.tax_rate`)

**Files:**
- Modify: `backend/app/services/invoice_service.py`

- [ ] **Step 1: Replace the tax calculation block in `create_invoice_from_subscription`**

In `create_invoice_from_subscription`, replace these three lines:

```python
    subtotal = line_total
    tax_amount = round(subtotal * Decimal("0.10"), 2)
    total = subtotal + tax_amount

    invoice = Invoice(
        invoice_number=invoice_number,
        org_id=sub.org_id,
        subscription_id=subscription_id,
        status="draft",
        issue_date=issue_date,
        due_date=due_date,
        subtotal=subtotal,
        tax_rate=Decimal("10.00"),
        tax_amount=tax_amount,
        total=total,
    )
```

With:

```python
    subtotal = line_total
    plan_tax_rate = Decimal(str(plan.tax_rate)) if plan and plan.tax_rate is not None else Decimal("0.00")
    tax_amount = round(subtotal * plan_tax_rate / Decimal("100"), 2)
    total = subtotal + tax_amount

    invoice = Invoice(
        invoice_number=invoice_number,
        org_id=sub.org_id,
        subscription_id=subscription_id,
        status="draft",
        issue_date=issue_date,
        due_date=due_date,
        subtotal=subtotal,
        tax_rate=plan_tax_rate,
        tax_amount=tax_amount,
        total=total,
    )
```

- [ ] **Step 2: Run the billing improvement tests — all should pass now**

```bash
pytest tests/test_billing_improvements.py -v 2>&1 | tail -15
```

Expected: `6 passed`

- [ ] **Step 3: Run full test suite to check no regressions**

```bash
pytest tests/test_auth.py tests/test_security_features.py tests/test_phase5c.py -v 2>&1 | tail -10
```

Expected: all previously passing tests still pass.

- [ ] **Step 4: Commit backend changes**

```bash
git add backend/alembic/versions/0008_add_plan_tax_rate.py \
        backend/alembic/versions/0009_add_annual_billing.py \
        backend/app/models/subscription.py \
        backend/app/schemas/subscription.py \
        backend/app/services/billing.py \
        backend/app/services/invoice_service.py \
        backend/app/api/subscriptions.py \
        backend/tests/test_billing_improvements.py
git commit -m "feat: add per-plan tax rate and annual billing cycle"
```

---

## Task 8: Update `ServiceOut` schema

**Files:**
- Modify: `backend/app/schemas/organization.py`

- [ ] **Step 1: Add `billing_cycle` field to `ServiceOut`**

In `backend/app/schemas/organization.py`, find the `ServiceOut` class and add `billing_cycle` after `monthly_cost`:

```python
class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    name: str
    type: str
    status: str
    domain: Optional[str] = None
    expiry_date: Optional[date] = None
    disk_usage: Optional[str] = None
    monthly_cost: Optional[float] = None
    billing_cycle: Optional[str] = None
```

(Keep all other fields already on `ServiceOut` — only add `billing_cycle: Optional[str] = None` at the end.)

- [ ] **Step 2: Verify services API returns billing_cycle**

```bash
pytest tests/ -k "service" -v 2>&1 | tail -10
```

Expected: existing service tests still pass.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/organization.py
git commit -m "feat: expose billing_cycle in ServiceOut response"
```

---

## Task 9: Frontend — SubscriptionsPage form UX

**Files:**
- Modify: `frontend/src/pages/admin/SubscriptionsPage.jsx`

- [ ] **Step 1: Add org and price-list imports to the file**

At the top of `SubscriptionsPage.jsx`, add `listOrganizations` and `listPriceLists` imports alongside the existing ones:

```js
import {
  listSubscriptions, createSubscription, cancelSubscription,
  listSubscriptionPlans
} from '@/api/subscriptions'
import { listOrganizations } from '@/api/organizations'
import { listPriceLists } from '@/api/items'
```

- [ ] **Step 2: Replace `EMPTY_FORM` and `SubscriptionForm` component**

Replace the existing `EMPTY_FORM` constant and the entire `SubscriptionForm` function with:

```jsx
const EMPTY_FORM = { org_id: '', plan_id: '', start_date: '', price_list_id: '', billing_cycle: 'monthly' }

function SubscriptionForm({ plans, orgs, priceLists, onSubmit, onCancel, loading }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setVal = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const selectedPlan = plans.find((p) => String(p.id) === String(form.plan_id))

  const annualPreview = () => {
    if (!selectedPlan) return null
    if (selectedPlan.annual_price != null) return selectedPlan.annual_price
    return null
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.org_id) { setError('Organisation is required'); return }
    if (!form.plan_id) { setError('Plan is required'); return }
    if (!form.start_date) { setError('Start date is required'); return }
    try {
      const payload = {
        org_id: Number(form.org_id),
        plan_id: Number(form.plan_id),
        start_date: form.start_date,
        billing_cycle: form.billing_cycle,
      }
      if (form.price_list_id !== '') payload.price_list_id = Number(form.price_list_id)
      await onSubmit(payload)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'An error occurred')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Organisation dropdown */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          Organisation <span className="text-red-500">*</span>
        </label>
        <select
          value={form.org_id}
          onChange={set('org_id')}
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">Select an organisation…</option>
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>{o.name} ({o.code})</option>
          ))}
        </select>
      </div>

      {/* Plan dropdown */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          Plan <span className="text-red-500">*</span>
        </label>
        <select
          value={form.plan_id}
          onChange={set('plan_id')}
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">Select a plan…</option>
          {plans.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      {/* Billing cycle toggle */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          Billing Cycle <span className="text-red-500">*</span>
        </label>
        <div className="flex rounded-lg border border-input overflow-hidden">
          <button
            type="button"
            onClick={() => setVal('billing_cycle', 'monthly')}
            className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
              form.billing_cycle === 'monthly'
                ? 'bg-primary text-primary-foreground'
                : 'bg-background text-foreground hover:bg-muted'
            }`}
          >
            Monthly
          </button>
          <button
            type="button"
            onClick={() => setVal('billing_cycle', 'yearly')}
            className={`flex-1 px-4 py-2 text-sm font-medium transition-colors border-l border-input ${
              form.billing_cycle === 'yearly'
                ? 'bg-primary text-primary-foreground'
                : 'bg-background text-foreground hover:bg-muted'
            }`}
          >
            Annual <span className="ml-1 text-xs opacity-75">−20%</span>
          </button>
        </div>
        {form.billing_cycle === 'yearly' && selectedPlan && (
          <p className="mt-1.5 text-xs text-muted-foreground">
            {annualPreview() != null
              ? `Annual price: ${fmtVND(annualPreview())}`
              : 'Annual price auto-calculated at 20% off (monthly × 12 × 0.8)'}
          </p>
        )}
      </div>

      {/* Start Date */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          Start Date <span className="text-red-500">*</span>
        </label>
        <input
          type="date"
          value={form.start_date}
          onChange={set('start_date')}
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Price List dropdown */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          Price List <span className="text-muted-foreground text-xs">(optional)</span>
        </label>
        <select
          value={form.price_list_id}
          onChange={set('price_list_id')}
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">— None (use default) —</option>
          {priceLists.map((pl) => (
            <option key={pl.id} value={pl.id}>{pl.name}</option>
          ))}
        </select>
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={loading}
          className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {loading && <Spinner className="w-3.5 h-3.5" />}
          Create Subscription
        </button>
      </div>
    </form>
  )
}
```

- [ ] **Step 3: Fetch orgs and price lists in `SubscriptionsPage` and pass to form**

In the `SubscriptionsPage` component, add `orgs` and `priceLists` state and fetch them in the `useEffect`:

Add state declarations (alongside existing `const [plans, setPlans] = useState([])`):
```js
const [orgs, setOrgs] = useState([])
const [priceLists, setPriceLists] = useState([])
```

In the existing `useEffect` that loads plans (or create a separate one), add:
```js
useEffect(() => {
  listSubscriptionPlans().then(setPlans).catch(() => {})
  listOrganizations({ per_page: 200 }).then(r => setOrgs(Array.isArray(r) ? r : (r.items ?? []))).catch(() => {})
  listPriceLists().then(setPriceLists).catch(() => {})
}, [])
```

- [ ] **Step 4: Pass `orgs` and `priceLists` to `SubscriptionForm`**

Find the `<SubscriptionForm` JSX usage and update its props:
```jsx
<SubscriptionForm
  plans={plans}
  orgs={orgs}
  priceLists={priceLists}
  onSubmit={handleCreate}
  onCancel={() => setCreateOpen(false)}
  loading={saving}
/>
```

- [ ] **Step 5: Also show `billing_cycle` in the subscriptions table**

In the subscriptions table header row, add a `Billing Cycle` column after `Plan`:
```jsx
<th className="text-left px-4 py-3 font-medium text-muted-foreground">Billing Cycle</th>
```

In each table data row, add after the plan cell:
```jsx
<td className="px-4 py-3 text-muted-foreground capitalize">
  {sub.billing_cycle === 'yearly' ? 'Annual' : 'Monthly'}
</td>
```

---

## Task 10: Frontend — New `SubscriptionPlansPage`

**Files:**
- Create: `frontend/src/pages/admin/SubscriptionPlansPage.jsx`

- [ ] **Step 1: Create the file**

```jsx
import { useState, useEffect } from 'react'
import { PlusIcon, PencilIcon } from '@heroicons/react/24/outline'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui'
import { listSubscriptionPlans, createSubscriptionPlan, updateSubscriptionPlan } from '@/api/subscriptions'
import { listItems } from '@/api/items'

const fmtVND = (n) => n != null ? new Intl.NumberFormat('vi-VN').format(n) + ' ₫' : '—'

const EMPTY_FORM = {
  code: '', name: '', description: '', item_id: '',
  billing_cycle: 'monthly', trial_days: '0',
  tax_rate: '0', annual_price: '', is_active: true,
}

function PlanForm({ initial, items, onSubmit, onCancel, loading }) {
  const [form, setForm] = useState(initial ?? EMPTY_FORM)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setCheck = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.checked }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.code.trim()) { setError('Code is required'); return }
    if (!form.name.trim()) { setError('Name is required'); return }
    if (!form.item_id) { setError('Item is required'); return }
    try {
      const payload = {
        code: form.code.trim(),
        name: form.name.trim(),
        description: form.description.trim() || null,
        item_id: Number(form.item_id),
        billing_cycle: form.billing_cycle,
        trial_days: Number(form.trial_days) || 0,
        tax_rate: form.tax_rate !== '' ? form.tax_rate : '0',
        annual_price: form.annual_price !== '' ? form.annual_price : null,
        is_active: form.is_active,
      }
      await onSubmit(payload)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'An error occurred')
    }
  }

  const inputCls = 'w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring'

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
          {error}
        </div>
      )}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Code <span className="text-red-500">*</span></label>
          <input type="text" value={form.code} onChange={set('code')} placeholder="BASIC-M" className={inputCls} disabled={!!initial} />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Name <span className="text-red-500">*</span></label>
          <input type="text" value={form.name} onChange={set('name')} placeholder="Basic Monthly" className={inputCls} />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">Description</label>
        <textarea value={form.description} onChange={set('description')} rows={2} className={inputCls} />
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">Item <span className="text-red-500">*</span></label>
        <select value={form.item_id} onChange={set('item_id')} className={inputCls}>
          <option value="">Select an item…</option>
          {items.map((i) => (
            <option key={i.id} value={i.id}>{i.name} — {fmtVND(i.unit_price)}</option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Default Billing Cycle</label>
          <select value={form.billing_cycle} onChange={set('billing_cycle')} className={inputCls}>
            <option value="monthly">Monthly</option>
            <option value="yearly">Annual</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Trial Days</label>
          <input type="number" min="0" value={form.trial_days} onChange={set('trial_days')} className={inputCls} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Tax Rate (%)</label>
          <input type="number" min="0" max="100" step="0.01" value={form.tax_rate} onChange={set('tax_rate')} placeholder="0" className={inputCls} />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Annual Price Override <span className="text-muted-foreground text-xs">(blank = auto)</span>
          </label>
          <input type="number" min="0" step="0.01" value={form.annual_price} onChange={set('annual_price')} placeholder="Auto (×12×0.8)" className={inputCls} />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <input type="checkbox" id="is_active" checked={form.is_active} onChange={setCheck('is_active')} className="rounded" />
        <label htmlFor="is_active" className="text-sm text-foreground">Active</label>
      </div>
      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onCancel} className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors">
          Cancel
        </button>
        <button type="submit" disabled={loading} className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">
          {loading && <Spinner className="w-3.5 h-3.5" />}
          {initial ? 'Save Changes' : 'Create Plan'}
        </button>
      </div>
    </form>
  )
}

export default function SubscriptionPlansPage() {
  const [plans, setPlans] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState(null)

  const load = async () => {
    setLoading(true)
    const [p, i] = await Promise.all([listSubscriptionPlans(), listItems()])
    setPlans(Array.isArray(p) ? p : [])
    setItems(Array.isArray(i) ? i : (i.items ?? []))
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const itemMap = Object.fromEntries(items.map((i) => [i.id, i]))

  const handleCreate = async (payload) => {
    setSaving(true)
    try { await createSubscriptionPlan(payload); setCreateOpen(false); await load() }
    finally { setSaving(false) }
  }

  const handleEdit = async (payload) => {
    setSaving(true)
    try { await updateSubscriptionPlan(editTarget.id, payload); setEditTarget(null); await load() }
    finally { setSaving(false) }
  }

  const editInitial = editTarget ? {
    code: editTarget.code,
    name: editTarget.name,
    description: editTarget.description ?? '',
    item_id: String(editTarget.item_id),
    billing_cycle: editTarget.billing_cycle,
    trial_days: String(editTarget.trial_days),
    tax_rate: String(editTarget.tax_rate),
    annual_price: editTarget.annual_price != null ? String(editTarget.annual_price) : '',
    is_active: editTarget.is_active,
  } : null

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Subscription Plans</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage plans, tax rates, and pricing</p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <PlusIcon className="w-4 h-4" /> New Plan
        </button>
      </div>

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20"><Spinner className="w-6 h-6" /></div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Name / Code</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Default Cycle</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Tax Rate</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Monthly Price</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Annual Price</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {plans.map((p) => {
                const item = itemMap[p.item_id]
                const monthlyPrice = item?.unit_price
                const autoAnnual = monthlyPrice != null
                  ? Math.round(Number(monthlyPrice) * 12 * 0.8)
                  : null
                return (
                  <tr key={p.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-foreground">{p.name}</p>
                      <p className="text-xs text-muted-foreground font-mono">{p.code}</p>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground capitalize">
                      {p.billing_cycle === 'yearly' ? 'Annual' : p.billing_cycle}
                    </td>
                    <td className="px-4 py-3 text-right text-muted-foreground tabular-nums">
                      {Number(p.tax_rate).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmtVND(monthlyPrice)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                      {p.annual_price != null
                        ? fmtVND(p.annual_price)
                        : autoAnnual != null
                          ? <span title="Auto-calculated">{fmtVND(autoAnnual)} <span className="text-[10px]">auto</span></span>
                          : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${p.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                        {p.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setEditTarget(p)}
                        className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                      >
                        <PencilIcon className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New Subscription Plan">
        <PlanForm items={items} onSubmit={handleCreate} onCancel={() => setCreateOpen(false)} loading={saving} />
      </Modal>

      <Modal open={!!editTarget} onClose={() => setEditTarget(null)} title="Edit Subscription Plan">
        {editTarget && (
          <PlanForm initial={editInitial} items={items} onSubmit={handleEdit} onCancel={() => setEditTarget(null)} loading={saving} />
        )}
      </Modal>
    </div>
  )
}
```

---

## Task 11: Frontend — ServicesPage billing cycle badge

**Files:**
- Modify: `frontend/src/pages/ServicesPage.jsx`

- [ ] **Step 1: Add billing cycle badge inside `ServiceCard`**

In the `ServiceCard` function, in the `<div className="mt-4 pt-4 border-t border-border space-y-3">` section, add the billing cycle badge right before the `monthly_cost` block:

```jsx
{service.billing_cycle && (
  <div>
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold ${
      service.billing_cycle === 'yearly'
        ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
        : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
    }`}>
      {service.billing_cycle === 'yearly' ? 'Annual' : 'Monthly'}
    </span>
  </div>
)}
```

---

## Task 12: Frontend — Route + Nav

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/layout/Layout.jsx`

- [ ] **Step 1: Add lazy import and route in `App.jsx`**

After the existing `const SubscriptionsPage = lazy(...)` line, add:
```js
const SubscriptionPlansPage = lazy(() => import('@/pages/admin/SubscriptionPlansPage'))
```

After the existing `/admin/subscriptions` route block, add:
```jsx
<Route path="/admin/subscription-plans" element={
  <ProtectedLayout>
    <AdminRoute><SubscriptionPlansPage /></AdminRoute>
  </ProtectedLayout>
} />
```

- [ ] **Step 2: Add nav entry in `Layout.jsx`**

In the `ADMIN_NAV` array (lines ~50–57 in `Layout.jsx`), add the Subscription Plans entry after the Subscriptions entry:

```js
{ label: 'Subscription Plans', href: '/admin/subscription-plans', icon: CreditCardIcon, iconActive: CreditCardSolid },
```

(Use `CreditCardIcon` / `CreditCardSolid` — both are already imported.)

- [ ] **Step 3: Add breadcrumb label**

In the `BREADCRUMB_LABELS` object (around line 70 in Layout.jsx), add:
```js
'subscription-plans': 'Subscription Plans',
```

- [ ] **Step 4: Build and verify no errors**

```bash
cd ~/helpdesk-system/frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ built in XX.XXs` with 0 errors.

- [ ] **Step 5: Commit all frontend changes**

```bash
git add frontend/src/pages/admin/SubscriptionsPage.jsx \
        frontend/src/pages/admin/SubscriptionPlansPage.jsx \
        frontend/src/pages/ServicesPage.jsx \
        frontend/src/App.jsx \
        frontend/src/components/layout/Layout.jsx
git commit -m "feat: subscription plans page, create-subscription form UX, billing cycle badges"
```
