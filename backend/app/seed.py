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


def get_or_create_service_with_item(session, org_id, category_id, name, service_type, monthly_cost, start_date, expiry_date, subscription_id=None):
    svc = session.query(Service).filter_by(org_id=org_id, name=name).first()
    if svc is None:
        svc = Service(
            org_id=org_id, category_id=category_id, type=service_type, name=name,
            status="active", monthly_cost=monthly_cost, start_date=start_date,
            expiry_date=expiry_date, subscription_id=subscription_id,
        )
        session.add(svc)
        session.flush()
    return svc


def get_or_create_item(session, code: str, name: str, item_type: str, unit_price, unit: str, description: str = None) -> Item:
    item = session.query(Item).filter_by(code=code).first()
    if item is None:
        item = Item(code=code, name=name, type=item_type, unit_price=unit_price, unit=unit, is_active=True, description=description)
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
        # Real customer orgs
        # ------------------------------------------------------------------
        duc_thanh_org = get_or_create_org(
            session,
            name="Công ty Sản xuất và Dịch vụ Đức Thành",
            code="DUC-THANH",
            contact_email="duc-thanh@example.vn",
        )

        aloha_vn_org = get_or_create_org(
            session,
            name="Aloha Vietnam Travel & Guide",
            code="ALOHA-VN",
            contact_email="aloha@example.vn",
        )

        # DUC-THANH contact
        get_or_create_contact(
            session,
            org_id=duc_thanh_org.id,
            email="lminhdc.23bi14287@usth.edu.vn",
            name="Nguyễn Văn Thuận",
            role="primary",
            phone="123456789",
        )

        # DUC-THANH customer user
        get_or_create_user(
            session,
            email="thuan@duc-thanh.vn",
            password="customer123",
            full_name="Nguyễn Văn Thuận",
            role="customer",
            org_id=duc_thanh_org.id,
        )

        # ALOHA-VN contact
        get_or_create_contact(
            session,
            org_id=aloha_vn_org.id,
            email="acm12112005@gmail.com",
            name="Anh Tân",
            role="primary",
            phone="0987654321",
        )

        # ALOHA-VN customer user
        get_or_create_user(
            session,
            email="tan@aloha-vn.vn",
            password="customer123",
            full_name="Anh Tân",
            role="customer",
            org_id=aloha_vn_org.id,
        )

        # ------------------------------------------------------------------
        # Items (service catalog)
        # ------------------------------------------------------------------
        items_data = [
            # Existing SaaS / hosting / domain / support items (kept for backward compat)
            ("SaaS-001", "Business Basic",      "saas",    Decimal("300000"),  "month", None),
            ("SaaS-002", "Business Pro",         "saas",    Decimal("500000"),  "month", None),
            ("SaaS-003", "Business Enterprise",  "saas",    Decimal("1200000"), "month", None),
            ("HOST-001", "Hosting Starter",      "hosting", Decimal("150000"),  "month", None),
            ("HOST-002", "Hosting Business",     "hosting", Decimal("350000"),  "month", None),
            ("DOM-001",  "Domain .vn",           "domain",  Decimal("350000"),  "year",  None),
            ("SUP-001",  "Support Basic",        "support", Decimal("200000"),  "month", None),
            # Vietnam Hosting items
            ("HOST-VN-TINY", "LS-TINY (VN)", "hosting", Decimal("50000"),  "month", "HDD 1GB, Băng thông 5GB/tháng, 1 domain, 1 FTP, 1 MySQL"),
            ("HOST-VN-S",    "LS-S (VN)",    "hosting", Decimal("70000"),  "month", "HDD 2GB, Băng thông 10GB/tháng, 2 domain, 2 FTP, 2 MySQL"),
            ("HOST-VN-M",    "LS-M (VN)",    "hosting", Decimal("100000"), "month", "HDD 5GB, Băng thông 20GB/tháng, 5 domain, 5 FTP, 5 MySQL"),
            ("HOST-VN-L",    "LS-L (VN)",    "hosting", Decimal("130000"), "month", "HDD 10GB, Băng thông 30GB/tháng, 10 domain, 10 FTP, 10 MySQL"),
            ("HOST-VN-E",    "LS-E (VN)",    "hosting", Decimal("150000"), "month", "HDD 20GB, Băng thông 50GB/tháng, 20 domain, 20 FTP, 20 MySQL"),
            ("HOST-VN-F",    "LS-F (VN)",    "hosting", Decimal("299000"), "month", "HDD 50GB, Băng thông 100GB/tháng, Unlimited domain, Unlimited FTP, Unlimited MySQL"),
            ("HOST-VN-P",    "LS-P (VN)",    "hosting", Decimal("450000"), "month", "HDD 100GB, Băng thông 200GB/tháng, Unlimited domain, Unlimited FTP, Unlimited MySQL, Free SSL"),
            # Offshore Hosting items
            ("HOST-OS-TINY", "LS-TINY (Offshore)", "hosting", Decimal("50000"),  "month", "HDD 1GB, Băng thông 5GB/tháng, 1 domain, 1 FTP, 1 MySQL, Offshore server"),
            ("HOST-OS-S",    "LS-S (Offshore)",    "hosting", Decimal("70000"),  "month", "HDD 2GB, Băng thông 10GB/tháng, 2 domain, 2 FTP, 2 MySQL, Offshore server"),
            ("HOST-OS-M",    "LS-M (Offshore)",    "hosting", Decimal("100000"), "month", "HDD 5GB, Băng thông 20GB/tháng, 5 domain, 5 FTP, 5 MySQL, Offshore server"),
            ("HOST-OS-L",    "LS-L (Offshore)",    "hosting", Decimal("130000"), "month", "HDD 10GB, Băng thông 30GB/tháng, 10 domain, 10 FTP, 10 MySQL, Offshore server"),
            ("HOST-OS-E",    "LS-E (Offshore)",    "hosting", Decimal("150000"), "month", "HDD 20GB, Băng thông 50GB/tháng, 20 domain, 20 FTP, 20 MySQL, Offshore server"),
            ("HOST-OS-ES",   "LS-ES (Offshore)",   "hosting", Decimal("190000"), "month", "HDD 30GB, Băng thông 80GB/tháng, 30 domain, 30 FTP, 30 MySQL, Offshore server SSD"),
            # SaaS support
            ("SUP-SAAS-001", "Support SaaS - Standard", "saas", Decimal("200000"), "month", "Standard support package for SaaS customers"),
        ]

        items = []
        for code, name, item_type, unit_price, unit, description in items_data:
            item = get_or_create_item(session, code=code, name=name, item_type=item_type, unit_price=unit_price, unit=unit, description=description)
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
        # Assign price lists to new orgs
        # ------------------------------------------------------------------
        duc_thanh_org.price_list_id = pl_standard.id
        aloha_vn_org.price_list_id = pl_standard.id
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

        plan_host_vn_tiny = get_or_create_subscription_plan(session, "PLAN-HOST-VN-TINY", "Hosting LS-TINY VN Monthly", "HOST-VN-TINY", "monthly")
        plan_host_vn_m    = get_or_create_subscription_plan(session, "PLAN-HOST-VN-M",    "Hosting LS-M VN Monthly",    "HOST-VN-M",    "monthly")
        plan_host_os_s    = get_or_create_subscription_plan(session, "PLAN-HOST-OS-S",    "Hosting LS-S Offshore Monthly", "HOST-OS-S", "monthly")
        plan_host_os_tiny = get_or_create_subscription_plan(session, "PLAN-HOST-OS-TINY", "Hosting LS-TINY Offshore Monthly", "HOST-OS-TINY", "monthly")

        session.commit()

        # ------------------------------------------------------------------
        # Subscriptions
        # ------------------------------------------------------------------
        from datetime import date, timedelta as td
        from app.services.billing import create_subscription

        # Look up orgs
        cty_a = session.query(Organization).filter_by(code="CTY-A").first()
        cty_b = session.query(Organization).filter_by(code="CTY-B").first()
        cty_c = session.query(Organization).filter_by(code="CTY-C").first()
        duc_thanh = session.query(Organization).filter_by(code="DUC-THANH").first()
        aloha_vn  = session.query(Organization).filter_by(code="ALOHA-VN").first()

        # CTY-A: 2 active subscriptions
        if cty_a and not session.query(Subscription).filter_by(org_id=cty_a.id, subscription_plan_id=plan_saas_basic.id).first():
            create_subscription(session, cty_a.id, plan_saas_basic.id, date(2025, 1, 1))

        if cty_a and not session.query(Subscription).filter_by(org_id=cty_a.id, subscription_plan_id=plan_hosting_starter.id).first():
            create_subscription(session, cty_a.id, plan_hosting_starter.id, date(2025, 3, 1))

        # CTY-B: 1 active subscription
        if cty_b and not session.query(Subscription).filter_by(org_id=cty_b.id, subscription_plan_id=plan_saas_pro.id).first():
            create_subscription(session, cty_b.id, plan_saas_pro.id, date(2025, 2, 1))

        # CTY-C: 1 subscription on trial (PLAN-004 has trial_days=14)
        if cty_c and not session.query(Subscription).filter_by(org_id=cty_c.id, subscription_plan_id=plan_hosting_starter.id).first():
            create_subscription(session, cty_c.id, plan_hosting_starter.id, date.today())

        # DUC-THANH and ALOHA-VN subscriptions
        if duc_thanh and not session.query(Subscription).filter_by(org_id=duc_thanh.id, subscription_plan_id=plan_host_vn_m.id).first():
            create_subscription(session, duc_thanh.id, plan_host_vn_m.id, date.today() - td(days=30))

        if aloha_vn and not session.query(Subscription).filter_by(org_id=aloha_vn.id, subscription_plan_id=plan_host_os_s.id).first():
            create_subscription(session, aloha_vn.id, plan_host_os_s.id, date.today() - td(days=60))

        # ------------------------------------------------------------------
        # Services for new real customers
        # ------------------------------------------------------------------
        today = date.today()
        sub_duc_thanh = session.query(Subscription).filter_by(org_id=duc_thanh.id, subscription_plan_id=plan_host_vn_m.id).first() if duc_thanh else None
        sub_aloha_os  = session.query(Subscription).filter_by(org_id=aloha_vn.id,  subscription_plan_id=plan_host_os_s.id).first() if aloha_vn else None

        if duc_thanh:
            get_or_create_service_with_item(
                session, duc_thanh.id, hosting_cat.id, "DUC-THANH LS-M VN Hosting", "hosting",
                monthly_cost=Decimal("100000"), start_date=today - td(days=30),
                expiry_date=today + td(days=60), subscription_id=sub_duc_thanh.id if sub_duc_thanh else None
            )
        if aloha_vn:
            get_or_create_service_with_item(
                session, aloha_vn.id, hosting_cat.id, "ALOHA-VN LS-S Offshore Hosting", "hosting",
                monthly_cost=Decimal("70000"), start_date=today - td(days=60),
                expiry_date=today + td(days=90), subscription_id=sub_aloha_os.id if sub_aloha_os else None
            )
            get_or_create_service_with_item(
                session, aloha_vn.id, hosting_cat.id, "ALOHA-VN LS-TINY VN Hosting", "hosting",
                monthly_cost=Decimal("50000"), start_date=today - td(days=30),
                expiry_date=today + td(days=30), subscription_id=None
            )

        # ------------------------------------------------------------------
        # Invoices (only if CTY-A and CTY-B exist in DB)
        # ------------------------------------------------------------------
        from datetime import timedelta, datetime as dt_datetime

        if cty_a and cty_b:
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
