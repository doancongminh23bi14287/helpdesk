"""
Idempotent seed script — populate demo data for the helpdesk system.

Run with:
    cd /home/acm/helpdesk-system/backend
    source venv/bin/activate
    python -m app.seed
"""

from app.database import SessionLocal
from app.models import Organization, User, ServiceCategory, Service
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

        for org_data in client_orgs:
            org = get_or_create_org(
                session,
                name=org_data["name"],
                code=org_data["code"],
                contact_email=org_data["contact_email"],
            )

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

        session.commit()

        # ------------------------------------------------------------------
        # Verification counts
        # ------------------------------------------------------------------
        org_count = session.query(Organization).count()
        user_count = session.query(User).count()
        service_count = session.query(Service).count()

        print("Seed complete.")
        print(f"  Organizations: {org_count}")
        print(f"  Users: {user_count}")
        print(f"  Services: {service_count}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
