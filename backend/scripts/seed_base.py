"""
seed_base.py — Idempotent base-data seeder for CustomerHub.

Run from backend/:
    source venv/bin/activate && python scripts/seed_base.py

Idempotency: each record is looked up by natural key (code / email)
before creation. Existing records are skipped and logged.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set SEED_ADMIN_PASSWORD env var before running in production
SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "change-me-in-production")

from app.database import SessionLocal
from app.models.organization import Organization
from app.models.user import User
from app.models.contact import Contact
from app.models.item import Item
from app.models.team import StaffOrgAssignment
from app.core.security import hash_password

# ── tiny helpers ──────────────────────────────────────────────────────────────

def _ok(msg):    print(f"  [OK]     {msg}")
def _skip(msg):  print(f"  [exists] {msg}")
def _section(t): print(f"\n{'='*58}\n  {t}\n{'='*58}")


def upsert_org(db, code, name, status="active"):
    obj = db.query(Organization).filter(Organization.code == code).first()
    if obj:
        _skip(f"Org  '{code}'")
        return obj
    obj = Organization(name=name, code=code, status=status)
    db.add(obj); db.flush()
    _ok(f"Org  '{code}' → id={obj.id}")
    return obj


def upsert_user(db, email, password, full_name, role, org_id,
                is_active=True, must_change_password=False):
    email = email.lower()
    obj = db.query(User).filter(User.email == email).first()
    if obj:
        _skip(f"User '{email}'")
        return obj
    obj = User(
        org_id=org_id,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=is_active,
        must_change_password=must_change_password,
    )
    db.add(obj); db.flush()
    _ok(f"User '{email}' (role={role}) → id={obj.id}")
    return obj


def upsert_contact(db, org_id, email, name, phone, role="primary"):
    obj = (db.query(Contact)
             .filter(Contact.org_id == org_id, Contact.email == email)
             .first())
    if obj:
        _skip(f"Contact '{email}'")
        return obj
    obj = Contact(
        org_id=org_id,
        name=name,
        email=email,
        phone=phone,
        role=role,
        is_active=True,
    )
    db.add(obj); db.flush()
    _ok(f"Contact '{name}' <{email}> → id={obj.id}")
    return obj


def upsert_item(db, code, name, unit_price, description,
                item_type="hosting", unit="month"):
    obj = db.query(Item).filter(Item.code == code).first()
    if obj:
        if not obj.description:
            obj.description = description
            db.flush()
            _ok(f"Item '{code}' — description patched")
        else:
            _skip(f"Item '{code}'")
        return obj
    obj = Item(
        code=code,
        name=name,
        type=item_type,
        unit_price=unit_price,
        unit=unit,
        description=description,
        is_active=True,
    )
    db.add(obj); db.flush()
    _ok(f"Item '{code}' — {name} @ {unit_price:,} VND")
    return obj


def upsert_staff_assignment(db, user_id, org_id, org_code):
    obj = (db.query(StaffOrgAssignment)
             .filter(StaffOrgAssignment.user_id == user_id,
                     StaffOrgAssignment.org_id == org_id)
             .first())
    if obj:
        _skip(f"StaffAssignment user_id={user_id} → org '{org_code}'")
        return obj
    obj = StaffOrgAssignment(user_id=user_id, org_id=org_id)
    db.add(obj); db.flush()
    _ok(f"StaffAssignment user_id={user_id} → org '{org_code}'")
    return obj


def patch_user_password(db, email, new_password):
    """Force-update password for a specific user (seed/dev only)."""
    email = email.lower()
    obj = db.query(User).filter(User.email == email).first()
    if obj:
        obj.password_hash = hash_password(new_password)
        db.flush()
        _ok(f"User '{email}' — password updated")


# ── seed data ─────────────────────────────────────────────────────────────────

# (code, name, price, description)
ITEMS = [
    # ── Vietnam hosting ───────────────────────────────────────────────────────
    (
        "HOST-VN-TINY", "LS-TINY (VN)", 50_000,
        "HDD: 600 Mb | Lưu lượng: 15.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 1 | FTP: 1 | MySQL: 1",
    ),
    (
        "HOST-VN-S", "LS-S (VN)", 70_000,
        "HDD: 1.200 Mb | Lưu lượng: 36.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 2 | FTP: 2 | MySQL: 2",
    ),
    (
        "HOST-VN-M", "LS-M (VN)", 100_000,
        "HDD: 2.000 Mb | Lưu lượng: 60.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 3 | FTP: 3 | MySQL: 3",
    ),
    (
        "HOST-VN-L", "LS-L (VN)", 130_000,
        "HDD: 2.400 Mb | Lưu lượng: 72.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 4 | FTP: 6 | MySQL: 6",
    ),
    (
        "HOST-VN-E", "LS-E (VN)", 150_000,
        "HDD: 3.000 Mb | Lưu lượng: 90.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 5 | FTP: 5 | MySQL: 5",
    ),
    (
        "HOST-VN-F", "LS-F (VN)", 299_000,
        "HDD: 6.000 Mb | Lưu lượng: 200.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 6 | FTP: 6 | MySQL: 6",
    ),
    (
        "HOST-VN-P", "LS-P (VN)", 450_000,
        "HDD: 13.000 Mb | Lưu lượng: 400.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 6 | FTP: 6 | MySQL: 6",
    ),
    # ── Offshore hosting ──────────────────────────────────────────────────────
    (
        "HOST-OS-TINY", "LS-TINY (OS)", 50_000,
        "HDD: 600 Mb | Lưu lượng: 30.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 1 | FTP: 1 | MySQL: 1 | "
        "Mailbox: 10 | Mailbox space: 10 Mb",
    ),
    (
        "HOST-OS-S", "LS-S (OS)", 70_000,
        "HDD: 1.200 Mb | Lưu lượng: 72.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 2 | FTP: 2 | MySQL: 2 | "
        "Mailbox: 20 | Mailbox space: 20 Mb",
    ),
    (
        "HOST-OS-M", "LS-M (OS)", 100_000,
        "HDD: 2.000 Mb | Lưu lượng: 120.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 3 | FTP: 3 | MySQL: 3 | "
        "Mailbox: 30 | Mailbox space: 30 Mb",
    ),
    (
        "HOST-OS-L", "LS-L (OS)", 130_000,
        "HDD: 2.400 Mb | Lưu lượng: 150.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 4 | FTP: 6 | MySQL: 6 | "
        "Mailbox: 40 | Mailbox space: 40 Mb",
    ),
    (
        "HOST-OS-E", "LS-E (OS)", 150_000,
        "HDD: 3.000 Mb | Lưu lượng: 180.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 5 | FTP: 5 | MySQL: 5 | "
        "Mailbox: 50 | Mailbox space: 50 Mb",
    ),
    (
        "HOST-OS-ES", "LS-ES (OS)", 190_000,
        "HDD: 4.000 Mb | Lưu lượng: 300.000 Mb/tháng | "
        "Add-on domain: 1 | Alias domain: 5 | FTP: 5 | MySQL: 5 | "
        "Mailbox: 50 | Mailbox space: 50 Mb",
    ),
]


def run():
    db = SessionLocal()
    counts = dict(orgs=0, users=0, contacts=0, items=0)

    try:
        # ── 1. Provider org + admin ───────────────────────────────────────────
        _section("1. Provider Org + Admin")

        provider = upsert_org(db, "PROVIDER", "OSD Provider")

        upsert_user(
            db,
            email="ticket@osd.vn",
            password=SEED_ADMIN_PASSWORD,
            full_name="Admin OSD",
            role="admin",
            org_id=provider.id,
            is_active=True,
            must_change_password=False,
        )

        # ── 2. Items ─────────────────────────────────────────────────────────
        _section("2. Service Catalogue — 13 Hosting Items")

        item_created = 0
        for code, name, price, desc in ITEMS:
            before = db.query(Item).filter(Item.code == code).first()
            upsert_item(db, code, name, price, desc)
            if before is None:
                item_created += 1

        # ── 3. Customer orgs ─────────────────────────────────────────────────
        _section("3. Customer Orgs + Contacts + Users")

        # Org A — Đức Thành
        duc_thanh = upsert_org(
            db, "DUC-THANH",
            "Công ty Sản xuất và Dịch vụ Đức Thành",
        )
        upsert_contact(
            db,
            org_id=duc_thanh.id,
            email="acm12112005@gmail.com",        # giữ nguyên bản cho contact
            name="Nguyễn Văn Thuận",
            phone="123456789",
        )
        upsert_user(
            db,
            email="acm12112005@gmail.com",         # lowercase (đã lowercase sẵn)
            password="customer123",
            full_name="Nguyễn Văn Thuận",
            role="customer",
            org_id=duc_thanh.id,
            is_active=True,
            must_change_password=True,
        )

        # Org B — Aloha Vietnam
        aloha = upsert_org(
            db, "ALOHA-VN",
            "Aloha Vietnam Travel & Guide",
        )
        upsert_contact(
            db,
            org_id=aloha.id,
            email="minhdc.23BI14287@USTH.edu.vn",  # giữ nguyên bản cho contact
            name="Anh Tân",
            phone="0987654321",
        )
        upsert_user(
            db,
            email="minhdc.23bi14287@usth.edu.vn",  # lowercase cho user login
            password=SEED_ADMIN_PASSWORD,
            full_name="Anh Tân",
            role="customer",
            org_id=aloha.id,
            is_active=True,
            must_change_password=True,
        )
        # Nếu user đã tồn tại từ seed cũ (password=customer123), patch lại
        patch_user_password(db, "minhdc.23bi14287@usth.edu.vn", SEED_ADMIN_PASSWORD)

        # ── 4. Staff users ────────────────────────────────────────────────────
        _section("4. Staff Users + Org Assignments")

        staff1 = upsert_user(
            db,
            email="staff1@osd.vn",
            password="staff123",
            full_name="Staff 1",
            role="staff",
            org_id=provider.id,
            is_active=True,
            must_change_password=False,
        )
        staff2 = upsert_user(
            db,
            email="staff2@osd.vn",
            password="staff123",
            full_name="Staff 2",
            role="staff",
            org_id=provider.id,
            is_active=True,
            must_change_password=False,
        )

        upsert_staff_assignment(db, staff1.id, duc_thanh.id, "DUC-THANH")
        upsert_staff_assignment(db, staff1.id, aloha.id,     "ALOHA-VN")
        upsert_staff_assignment(db, staff2.id, duc_thanh.id, "DUC-THANH")
        upsert_staff_assignment(db, staff2.id, aloha.id,     "ALOHA-VN")

        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # ── summary ───────────────────────────────────────────────────────────────
    _section("Summary")

    db2 = SessionLocal()
    try:
        n_users  = db2.query(User).count()
        n_orgs   = db2.query(Organization).count()
        n_items  = db2.query(Item).count()
        n_conts  = db2.query(Contact).count()
        n_assign = db2.query(StaffOrgAssignment).count()
    finally:
        db2.close()

    print(f"  Items trong DB       : {n_items}  (phải 13)")
    print(f"  Users trong DB       : {n_users}  (phải 5: 1 admin + 2 staff + 2 customer)")
    print(f"  Orgs trong DB        : {n_orgs}  (phải 3: PROVIDER + 2 khách)")
    print(f"  Contacts trong DB    : {n_conts} (phải 2)")
    print(f"  Staff assignments    : {n_assign} (phải 4)")
    print()
    print("  Đăng nhập xác nhận:")
    print("    admin     : ticket@osd.vn                    / $SEED_ADMIN_PASSWORD")
    print("    staff1    : staff1@osd.vn                    / staff123")
    print("    staff2    : staff2@osd.vn                    / staff123")
    print("    customer1 : acm12112005@gmail.com            / customer123")
    print("    customer2 : minhdc.23bi14287@usth.edu.vn     / $SEED_ADMIN_PASSWORD")


if __name__ == "__main__":
    run()
