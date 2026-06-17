#!/usr/bin/env python3
"""
Backfill: create a Service record for every Subscription that has no linked service.

Run from the backend/ directory:
    python scripts/backfill_service_links.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.subscription import Subscription
from app.models.service import Service
from app.services.service_sync import sync_service_from_subscription


def main():
    db = SessionLocal()
    try:
        subs = db.query(Subscription).all()
        created = 0
        skipped = 0
        for sub in subs:
            existing = db.query(Service).filter(Service.subscription_id == sub.id).first()
            if existing:
                skipped += 1
                continue
            svc = sync_service_from_subscription(db, sub, create_if_missing=True)
            print(f"  Created service id={svc.id} name={svc.name!r} for subscription id={sub.id}")
            created += 1

        print(f"\nBackfill complete: {created} service(s) created, {skipped} already linked.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
