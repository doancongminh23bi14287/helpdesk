"""Create only synthetic load-test identities in the isolated database."""
import os

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.organization import Organization
from app.models.team import StaffOrgAssignment
from app.models.user import User


def upsert_user(db, email, password, name, role, org_id):
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=name,
            role=role,
            org_id=org_id,
            is_active=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
    else:
        user.password_hash = hash_password(password)
        user.org_id = org_id
        user.is_active = True
    return user


def main():
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.code == "LOADTEST-ORG").one_or_none()
        if org is None:
            org = Organization(code="LOADTEST-ORG", name="LOADTEST Synthetic Organisation", status="active")
            db.add(org)
            db.flush()
        password = os.environ.get("LOAD_TEST_PASSWORD", "loadtest-local-password")
        admin = upsert_user(db, "load-admin@example.net", password, "LOADTEST Admin", "admin", org.id)
        upsert_user(db, "load-customer@example.com", password, "LOADTEST Customer", "customer", org.id)
        staff = upsert_user(db, "load-staff@example.org", password, "LOADTEST Staff", "staff", org.id)
        if db.query(StaffOrgAssignment).filter_by(user_id=staff.id, org_id=org.id).one_or_none() is None:
            db.add(StaffOrgAssignment(user_id=staff.id, org_id=org.id))
        db.commit()
        print({"organisation_id": org.id, "admin_id": admin.id, "staff_id": staff.id})
    finally:
        db.close()


if __name__ == "__main__":
    main()
