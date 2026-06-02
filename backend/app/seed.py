"""
Idempotent seed script — populate demo data for the helpdesk system.

Run with:
    cd /home/acm/helpdesk-system/backend
    source venv/bin/activate
    python -m app.seed
"""

from decimal import Decimal

from app.database import SessionLocal
from app.models import Organization, User, ServiceCategory, Service
from app.models.item import Item, PriceList, PriceListItem
from app.models.contact import Contact
from app.models.address import Address
from app.models.subscription import SubscriptionPlan, Subscription
from app.models.invoice import Invoice, InvoiceLine, InvoiceNumberSeq
from app.core.security import hash_password


def get_or_create_org(session, name: str, code: str, contact_email: str) -> Organization:
    org = session.query(Organization).filter_by(code=code).first()
    if org is None:
        org = Organization(
            name=name,
            code=code,
            contact_email=contact_email,
            status="active",
        )
        session.add(org)
        session.flush()
    return org


def get_or_create_user(
    session,
    email: str,
    password: str,
    full_name: str,
    role: str,
    org_id: int,
) -> User:
    user = session.query(User).filter_by(email=email).first()
    if user is None:
        user = User(
            org_id=org_id,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
        )
        session.add(user)
        session.flush()
    return user


def get_or_create_service(
    session,
    org_id: int,
    category_id: int,
    service_type: str,
    name: str,
) -> Service:
    svc = session.query(Service).filter_by(org_id=org_id, name=name).first()
    if svc is None:
        svc = Service(
            org_id=org_id,
            category_id=category_id,
            type=service_type,
            name=name,
            status="active",
        )
        session.add(svc)
        session.flush()
    return svc


def get_or_create_item(session, code: str, name: str, item_type: str, unit_price, unit: str) -> Item:
    item = session.query(Item).filter_by(code=code).first()
    if item is None:
        item = Item(code=code, name=name, type=item_type, unit_price=unit_price, unit=unit, is_active=True)
        session.add(item)
        session.flush()
    return item


def get_or_create_price_list(session, name: str) -> PriceList:
    pl = session.query(PriceList).filter_by(name=name).first()
    if pl is None:
        pl = PriceList(name=name, currency="VND", is_active=True)
        session.add(pl)
        session.flush()
    return pl


def get_or_create_price_list_item(session, price_list_id: int, item_id: int, unit_price) -> PriceListItem:
    pli = session.query(PriceListItem).filter_by(price_list_id=price_list_id, item_id=item_id).first()
    if pli is None:
        pli = PriceListItem(price_list_id=price_list_id, item_id=item_id, unit_price=unit_price)
        session.add(pli)
        session.flush()
    else:
        pli.unit_price = unit_price  # update price if re-running
        session.flush()
    return pli


def get_or_create_contact(session, org_id: int, email: str, name: str, role: str, phone: str) -> Contact:
    contact = session.query(Contact).filter_by(org_id=org_id, email=email).first()
    if contact is None:
        contact = Contact(org_id=org_id, name=name, email=email, role=role, phone=phone, is_active=True)
        session.add(contact)
        session.flush()
    return contact


def get_or_create_address(session, org_id: int, label: str, **kwargs) -> Address:
    address = session.query(Address).filter_by(org_id=org_id, label=label).first()
    if address is None:
        address = Address(org_id=org_id, label=label, **kwargs)
        session.add(address)
        session.flush()
    return address


def get_or_create_subscription_plan(session, code: str, name: str, item_code: str, billing_cycle: str, trial_days: int = 0, **kwargs) -> SubscriptionPlan:
    plan = session.query(SubscriptionPlan).filter_by(code=code).first()
    if plan is None:
        item = session.query(Item).filter_by(code=item_code).first()
        if item is None:
            raise RuntimeError(f"Item {item_code!r} not found — run seed after items are created")
        plan = SubscriptionPlan(
            code=code, name=name, item_id=item.id,
            billing_cycle=billing_cycle, trial_days=trial_days, **kwargs
        )
        session.add(plan)
        session.flush()
    return plan


def get_or_create_invoice(session, invoice_number: str, org_id: int, **kwargs) -> Invoice:
    inv = session.query(Invoice).filter_by(invoice_number=invoice_number).first()
    if inv is None:
        # Ensure InvoiceNumberSeq row exists for the year
        year = int(invoice_number.split('-')[1])
        seq_num = int(invoice_number.split('-')[2])
        seq = session.query(InvoiceNumberSeq).filter_by(year=year).first()
        if seq is None:
            seq = InvoiceNumberSeq(year=year, last_seq=0)
            session.add(seq)
            session.flush()
        if seq.last_seq < seq_num:
            seq.last_seq = seq_num
            session.flush()
        inv = Invoice(invoice_number=invoice_number, org_id=org_id, **kwargs)
        session.add(inv)
        session.flush()
    return inv


def seed() -> None:
    session = SessionLocal()
    try:
        # ------------------------------------------------------------------
        # Look up PROVIDER org (inserted by SCHEMA.sql — do NOT recreate)
        # ------------------------------------------------------------------
        provider_org = session.query(Organization).filter_by(code="PROVIDER").first()
        if provider_org is None:
            raise RuntimeError(
                "PROVIDER org not found in DB. Make sure SCHEMA.sql has been applied."
            )

        # ------------------------------------------------------------------
        # Admin user
        # ------------------------------------------------------------------
        get_or_create_user(
            session,
            email="admin@osd.vn",
            password="admin123",
            full_name="Admin OSD",
            role="admin",
            org_id=provider_org.id,
        )

        # ------------------------------------------------------------------
        # Staff users
        # ------------------------------------------------------------------
        for n in (1, 2):
            get_or_create_user(
                session,
                email=f"staff{n}@osd.vn",
                password="staff123",
                full_name=f"Staff {n}",
                role="staff",
                org_id=provider_org.id,
            )

        # ------------------------------------------------------------------
        # Service category look-ups
        # ------------------------------------------------------------------
        saas_cat = session.query(ServiceCategory).filter_by(slug="saas").first()
        hosting_cat = session.query(ServiceCategory).filter_by(slug="hosting").first()
        if saas_cat is None or hosting_cat is None:
            raise RuntimeError(
                "ServiceCategory rows for 'saas'/'hosting' not found. "
                "Make sure SCHEMA.sql has been applied."
            )

        # ------------------------------------------------------------------
        # Client orgs, their services and customers
        # ------------------------------------------------------------------
        client_orgs = [
            {
                "name": "Cong ty A",
                "code": "CTY-A",
                "contact_email": "contact@cty-a.vn",
                "customer_emails": ["a1@cty-a.vn", "a2@cty-a.vn"],
            },
            {
                "name": "Cong ty B",
                "code": "CTY-B",
                "contact_email": "contact@cty-b.vn",
                "customer_emails": ["b1@cty-b.vn", "b2@cty-b.vn"],
            },
            {
                "name": "Cong ty C",
                "code": "CTY-C",
                "contact_email": "contact@cty-c.vn",
                "customer_emails": ["c1@cty-c.vn", "c2@cty-c.vn"],
            },
        ]

        org_map = {}
        for org_data in client_orgs:
            org = get_or_create_org(
                session,
                name=org_data["name"],
                code=org_data["code"],
                contact_email=org_data["contact_email"],
            )
            org_map[org_data["code"]] = org

            # 2 services
            get_or_create_service(
                session,
                org_id=org.id,
                category_id=saas_cat.id,
                service_type="saas",
                name=f"{org_data['name']} Business Pro",
            )
            get_or_create_service(
                session,
                org_id=org.id,
                category_id=hosting_cat.id,
                service_type="hosting",
                name=f"{org_data['name']} Web Hosting",
            )

            # 2 customers
            for idx, email in enumerate(org_data["customer_emails"], start=1):
                get_or_create_user(
                    session,
                    email=email,
                    password="customer123",
                    full_name=f"Customer {idx} {org_data['name']}",
                    role="customer",
                    org_id=org.id,
                )

        # ------------------------------------------------------------------
        # Items (service catalog)
        # ------------------------------------------------------------------
        items_data = [
            ("SaaS-001", "Business Basic",      "saas",    Decimal("300000"),  "month"),
            ("SaaS-002", "Business Pro",         "saas",    Decimal("500000"),  "month"),
            ("SaaS-003", "Business Enterprise",  "saas",    Decimal("1200000"), "month"),
            ("HOST-001", "Hosting Starter",      "hosting", Decimal("150000"),  "month"),
            ("HOST-002", "Hosting Business",     "hosting", Decimal("350000"),  "month"),
            ("DOM-001",  "Domain .vn",           "domain",  Decimal("350000"),  "year"),
            ("SUP-001",  "Support Basic",        "support", Decimal("200000"),  "month"),
        ]

        items = []
        for code, name, item_type, unit_price, unit in items_data:
            item = get_or_create_item(session, code=code, name=name, item_type=item_type, unit_price=unit_price, unit=unit)
            items.append(item)

        # ------------------------------------------------------------------
        # Price Lists
        # ------------------------------------------------------------------
        pl_standard   = get_or_create_price_list(session, "Standard")
        pl_premium    = get_or_create_price_list(session, "Premium")
        pl_enterprise = get_or_create_price_list(session, "Enterprise")

        # PriceListItems for each price list
        for item in items:
            base = item.unit_price
            # Standard: base price (1.0x)
            get_or_create_price_list_item(
                session,
                price_list_id=pl_standard.id,
                item_id=item.id,
                unit_price=base,
            )
            # Premium: 10% off (0.9x)
            get_or_create_price_list_item(
                session,
                price_list_id=pl_premium.id,
                item_id=item.id,
                unit_price=Decimal(int(base * Decimal("0.9"))),
            )
            # Enterprise: 20% off (0.8x)
            get_or_create_price_list_item(
                session,
                price_list_id=pl_enterprise.id,
                item_id=item.id,
                unit_price=Decimal(int(base * Decimal("0.8"))),
            )

        # ------------------------------------------------------------------
        # Contacts (2 per client org)
        # ------------------------------------------------------------------
        # CTY-A contacts
        cty_a = org_map["CTY-A"]
        get_or_create_contact(session, org_id=cty_a.id, email="a-primary@cty-a.vn",
                              name="Nguyen Van A", role="primary", phone="0901000001")
        get_or_create_contact(session, org_id=cty_a.id, email="a-billing@cty-a.vn",
                              name="Le Thi B", role="billing", phone="0901000002")

        # CTY-B contacts
        cty_b = org_map["CTY-B"]
        get_or_create_contact(session, org_id=cty_b.id, email="c-primary@cty-b.vn",
                              name="Tran Van C", role="primary", phone="0902000001")
        get_or_create_contact(session, org_id=cty_b.id, email="d-technical@cty-b.vn",
                              name="Pham Thi D", role="technical", phone="0902000002")

        # CTY-C contacts
        cty_c = org_map["CTY-C"]
        get_or_create_contact(session, org_id=cty_c.id, email="e-primary@cty-c.vn",
                              name="Hoang Van E", role="primary", phone="0903000001")
        get_or_create_contact(session, org_id=cty_c.id, email="f-billing@cty-c.vn",
                              name="Nguyen Thi F", role="billing", phone="0903000002")

        # ------------------------------------------------------------------
        # Addresses (1 per client org)
        # ------------------------------------------------------------------
        get_or_create_address(session, org_id=cty_a.id, label="HQ",
                              street="123 Nguyen Hue", city="Ho Chi Minh City",
                              province="Ho Chi Minh", country="Vietnam", is_default=True)

        get_or_create_address(session, org_id=cty_b.id, label="HQ",
                              street="456 Tran Hung Dao", city="Ha Noi",
                              province="Ha Noi", country="Vietnam", is_default=True)

        get_or_create_address(session, org_id=cty_c.id, label="HQ",
                              street="789 Le Loi", city="Da Nang",
                              province="Da Nang", country="Vietnam", is_default=True)

        # ------------------------------------------------------------------
        # Assign price lists to orgs
        # ------------------------------------------------------------------
        cty_a.price_list_id = pl_standard.id
        cty_b.price_list_id = pl_premium.id
        cty_c.price_list_id = pl_enterprise.id
        session.flush()

        # ------------------------------------------------------------------
        # Subscription Plans
        # ------------------------------------------------------------------
        plan_saas_basic = get_or_create_subscription_plan(
            session, "PLAN-001", "SaaS Basic Monthly", "SaaS-001", "monthly"
        )
        plan_saas_pro = get_or_create_subscription_plan(
            session, "PLAN-002", "SaaS Pro Monthly", "SaaS-002", "monthly"
        )
        plan_saas_enterprise = get_or_create_subscription_plan(
            session, "PLAN-003", "SaaS Enterprise Yearly", "SaaS-003", "yearly"
        )
        plan_hosting_starter = get_or_create_subscription_plan(
            session, "PLAN-004", "Hosting Starter Monthly", "HOST-001", "monthly", trial_days=14
        )
        plan_hosting_pro = get_or_create_subscription_plan(
            session, "PLAN-005", "Hosting Pro Quarterly", "HOST-002", "quarterly"
        )

        session.commit()

        # ------------------------------------------------------------------
        # Subscriptions
        # ------------------------------------------------------------------
        from datetime import date
        from app.services.billing import create_subscription

        # Look up orgs
        cty_a = session.query(Organization).filter_by(code="CTY-A").first()
        cty_b = session.query(Organization).filter_by(code="CTY-B").first()
        cty_c = session.query(Organization).filter_by(code="CTY-C").first()

        # CTY-A: 2 active subscriptions
        if not session.query(Subscription).filter_by(org_id=cty_a.id, subscription_plan_id=plan_saas_basic.id).first():
            create_subscription(session, cty_a.id, plan_saas_basic.id, date(2025, 1, 1))

        if not session.query(Subscription).filter_by(org_id=cty_a.id, subscription_plan_id=plan_hosting_starter.id).first():
            create_subscription(session, cty_a.id, plan_hosting_starter.id, date(2025, 3, 1))

        # CTY-B: 1 active subscription
        if not session.query(Subscription).filter_by(org_id=cty_b.id, subscription_plan_id=plan_saas_pro.id).first():
            create_subscription(session, cty_b.id, plan_saas_pro.id, date(2025, 2, 1))

        # CTY-C: 1 subscription on trial (PLAN-004 has trial_days=14)
        if not session.query(Subscription).filter_by(org_id=cty_c.id, subscription_plan_id=plan_hosting_starter.id).first():
            create_subscription(session, cty_c.id, plan_hosting_starter.id, date.today())

        # ------------------------------------------------------------------
        # Invoices
        # ------------------------------------------------------------------
        from datetime import timedelta, datetime as dt_datetime

        today = date.today()

        # Look up subscriptions
        sub_cty_a_saas = session.query(Subscription).join(
            SubscriptionPlan, Subscription.subscription_plan_id == SubscriptionPlan.id
        ).filter(
            Subscription.org_id == cty_a.id,
            SubscriptionPlan.code == "PLAN-001",
        ).first()

        sub_cty_a_hosting = session.query(Subscription).join(
            SubscriptionPlan, Subscription.subscription_plan_id == SubscriptionPlan.id
        ).filter(
            Subscription.org_id == cty_a.id,
            SubscriptionPlan.code == "PLAN-004",
        ).first()

        sub_cty_b_saas = session.query(Subscription).join(
            SubscriptionPlan, Subscription.subscription_plan_id == SubscriptionPlan.id
        ).filter(
            Subscription.org_id == cty_b.id,
            SubscriptionPlan.code == "PLAN-002",
        ).first()

        # INV-2026-0001: CTY-A SaaS April, status=paid
        inv1 = get_or_create_invoice(
            session, "INV-2026-0001", cty_a.id,
            subscription_id=sub_cty_a_saas.id if sub_cty_a_saas else None,
            status="paid",
            issue_date=date(2026, 4, 1),
            due_date=date(2026, 4, 16),
            subtotal=Decimal("300000.00"),
            tax_rate=Decimal("10.00"),
            tax_amount=Decimal("30000.00"),
            total=Decimal("330000.00"),
            paid_at=dt_datetime(2026, 4, 10),
        )
        if not session.query(InvoiceLine).filter_by(invoice_id=inv1.id).first():
            session.add(InvoiceLine(
                invoice_id=inv1.id,
                description="SaaS Basic Monthly — 2026-04-01 to 2026-04-30",
                quantity=Decimal("1.00"),
                unit_price=Decimal("300000.00"),
                line_total=Decimal("300000.00"),
            ))
            session.flush()

        # INV-2026-0002: CTY-A SaaS May, status=sent
        inv2 = get_or_create_invoice(
            session, "INV-2026-0002", cty_a.id,
            subscription_id=sub_cty_a_saas.id if sub_cty_a_saas else None,
            status="sent",
            issue_date=date(2026, 5, 1),
            due_date=today + timedelta(days=5),
            subtotal=Decimal("300000.00"),
            tax_rate=Decimal("10.00"),
            tax_amount=Decimal("30000.00"),
            total=Decimal("330000.00"),
        )
        if not session.query(InvoiceLine).filter_by(invoice_id=inv2.id).first():
            session.add(InvoiceLine(
                invoice_id=inv2.id,
                description="SaaS Basic Monthly — 2026-05-01 to 2026-05-31",
                quantity=Decimal("1.00"),
                unit_price=Decimal("300000.00"),
                line_total=Decimal("300000.00"),
            ))
            session.flush()

        # INV-2026-0003: CTY-A Hosting May, status=draft
        inv3 = get_or_create_invoice(
            session, "INV-2026-0003", cty_a.id,
            subscription_id=sub_cty_a_hosting.id if sub_cty_a_hosting else None,
            status="draft",
            issue_date=date(2026, 5, 1),
            due_date=date(2026, 5, 16),
            subtotal=Decimal("150000.00"),
            tax_rate=Decimal("10.00"),
            tax_amount=Decimal("15000.00"),
            total=Decimal("165000.00"),
        )
        if not session.query(InvoiceLine).filter_by(invoice_id=inv3.id).first():
            session.add(InvoiceLine(
                invoice_id=inv3.id,
                description="Hosting Starter Monthly — 2026-05-01 to 2026-05-31",
                quantity=Decimal("1.00"),
                unit_price=Decimal("150000.00"),
                line_total=Decimal("150000.00"),
            ))
            session.flush()

        # INV-2026-0004: CTY-B Annual, status=paid
        inv4 = get_or_create_invoice(
            session, "INV-2026-0004", cty_b.id,
            subscription_id=sub_cty_b_saas.id if sub_cty_b_saas else None,
            status="paid",
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 16),
            subtotal=Decimal("450000.00"),
            tax_rate=Decimal("10.00"),
            tax_amount=Decimal("45000.00"),
            total=Decimal("495000.00"),
            paid_at=dt_datetime(2026, 1, 10),
        )
        if not session.query(InvoiceLine).filter_by(invoice_id=inv4.id).first():
            session.add(InvoiceLine(
                invoice_id=inv4.id,
                description="SaaS Pro Monthly — 2026-01-01 to 2026-01-31",
                quantity=Decimal("1.00"),
                unit_price=Decimal("450000.00"),
                line_total=Decimal("450000.00"),
            ))
            session.flush()

        session.commit()

        # ------------------------------------------------------------------
        # Verification counts
        # ------------------------------------------------------------------
        org_count = session.query(Organization).count()
        user_count = session.query(User).count()
        service_count = session.query(Service).count()
        item_count = session.query(Item).count()
        pl_count = session.query(PriceList).count()
        pli_count = session.query(PriceListItem).count()
        contact_count = session.query(Contact).count()
        address_count = session.query(Address).count()
        sp_count = session.query(SubscriptionPlan).count()
        sub_count = session.query(Subscription).count()
        inv_count = session.query(Invoice).count()
        line_count = session.query(InvoiceLine).count()

        print("Seed complete.")
        print(f"  Organizations: {org_count}")
        print(f"  Users: {user_count}")
        print(f"  Services: {service_count}")
        print(f"  Items: {item_count}")
        print(f"  PriceLists: {pl_count}")
        print(f"  PriceListItems: {pli_count}")
        print(f"  Contacts: {contact_count}")
        print(f"  Addresses: {address_count}")
        print(f"  SubscriptionPlans: {sp_count}")
        print(f"  Subscriptions: {sub_count}")
        print(f"  Invoices: {inv_count}")
        print(f"  InvoiceLines: {line_count}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
