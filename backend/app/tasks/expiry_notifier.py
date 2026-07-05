# backend/app/tasks/expiry_notifier.py
import html
from app.tasks.celery_app import celery_app
from app.core.redis_client import redis_client
from app.database import SessionLocal


def _fmt_vnd(amount) -> str:
    return f"{round(amount):,}".replace(",", ".") + " ₫"


def _get_plan_name(sub, item_map, plan_map) -> str:
    if sub.subscription_plan_id:
        plan = plan_map.get(sub.subscription_plan_id)
        if plan:
            return plan.name
    if sub.item_id:
        item = item_map.get(sub.item_id)
        if item:
            return item.name
    return f"Subscription #{sub.id}"


@celery_app.task(name="app.tasks.expiry_notifier.notify_expiring")
def notify_expiring():
    """
    Daily at 09:00 UTC.
    1. next_billing_date == today+30: 30-day renewal reminder email.
    2. next_billing_date == today+7:  7-day renewal reminder email.
    3. current_period_end == today:   expiry notification email.
    Also creates in-app notifications for admin users.

    Idempotency: Redis keys gate each (subscription, reminder_type, date) triple.
    A task re-run on the same day skips any already-processed subscription.
    Keys use TTL=2 days so they self-clean after the notification window closes.

    Returns {"warned_30": N, "warned_7": N, "expired": N}
    """
    db = SessionLocal()
    try:
        from app.models.subscription import Subscription, SubscriptionPlan
        from app.models.organization import Organization
        from app.models.item import Item
        from app.models.user import User
        from app.services.notify import create_notification
        from app.services.email_sender import send_email
        from app.services.email_templates import render_template
        from datetime import date, timedelta

        today = date.today()
        today_str = today.isoformat()
        date_7 = today + timedelta(days=7)
        date_30 = today + timedelta(days=30)

        admins = db.query(User).filter(
            User.role == "admin",
            User.is_active == True,
        ).all()

        # Collect all subs that need reminders
        subs_30 = db.query(Subscription).filter(
            Subscription.status == "active",
            Subscription.next_billing_date == date_30,
        ).all()
        subs_7 = db.query(Subscription).filter(
            Subscription.status == "active",
            Subscription.next_billing_date == date_7,
        ).all()
        subs_expired = db.query(Subscription).filter(
            Subscription.status == "active",
            Subscription.current_period_end == today,
        ).all()

        all_subs = subs_30 + subs_7 + subs_expired

        # Batch fetch supporting data
        org_ids = {s.org_id for s in all_subs}
        plan_ids = {s.subscription_plan_id for s in all_subs if s.subscription_plan_id}
        item_ids = {s.item_id for s in all_subs if s.item_id}

        org_map = {o.id: o for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()} if org_ids else {}
        plan_map = {p.id: p for p in db.query(SubscriptionPlan).filter(SubscriptionPlan.id.in_(plan_ids)).all()} if plan_ids else {}
        item_map = {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}

        def _send_renewal_reminder(sub, days_until: int):
            org = org_map.get(sub.org_id)
            if not org or not org.contact_email:
                return
            plan_name = _get_plan_name(sub, item_map, plan_map)
            org_name = org.name
            billing_date_fmt = sub.next_billing_date.strftime("%d/%m/%Y")
            amount_fmt = _fmt_vnd(sub.unit_price)

            body_html = render_template(
                "renewal_reminder.html",
                org_name=html.escape(org_name or ""),
                plan_name=html.escape(plan_name or ""),
                next_billing_date=billing_date_fmt,
                days_until=days_until,
                amount_fmt=amount_fmt,
            )
            body_text = (
                f"Kính gửi {org_name},\n\n"
                f"Gói dịch vụ {plan_name} sẽ đến hạn gia hạn vào {billing_date_fmt} "
                f"(còn {days_until} ngày).\n"
                f"Số tiền: {amount_fmt}\n\n"
                f"Liên hệ: ticket@osd.vn"
            )
            subject = f"[OSD] Nhắc gia hạn dịch vụ — {plan_name} ({days_until} ngày)"
            send_email(org.contact_email, subject, body_html, body_text, db=db)

        # --- 30-day renewal reminder ---
        warned_30 = 0
        for sub in subs_30:
            dedup_key = f"expiry_notif:{sub.id}:30:{today_str}"
            if redis_client.exists(dedup_key):
                continue
            _send_renewal_reminder(sub, 30)
            org = org_map.get(sub.org_id)
            org_name = org.name if org else f"org#{sub.org_id}"
            plan_name = _get_plan_name(sub, item_map, plan_map)
            for admin in admins:
                create_notification(
                    db,
                    user_id=admin.id,
                    title="Subscription renewing in 30 days",
                    content=f"Subscription #{sub.id} for {org_name} ({plan_name}) renews on {date_30}",
                    type="expiry",
                )
            redis_client.setex(dedup_key, 86400 * 2, "1")
            warned_30 += 1

        # --- 7-day renewal reminder ---
        warned_7 = 0
        for sub in subs_7:
            dedup_key = f"expiry_notif:{sub.id}:7:{today_str}"
            if redis_client.exists(dedup_key):
                continue
            _send_renewal_reminder(sub, 7)
            org = org_map.get(sub.org_id)
            org_name = org.name if org else f"org#{sub.org_id}"
            plan_name = _get_plan_name(sub, item_map, plan_map)
            for admin in admins:
                create_notification(
                    db,
                    user_id=admin.id,
                    title="Subscription renewing in 7 days",
                    content=f"Subscription #{sub.id} for {org_name} ({plan_name}) renews on {date_7}",
                    type="expiry",
                )
            redis_client.setex(dedup_key, 86400 * 2, "1")
            warned_7 += 1

        # --- Expiry notification (period ended today) ---
        expired_count = 0
        for sub in subs_expired:
            dedup_key = f"expiry_notif:{sub.id}:expired:{today_str}"
            if redis_client.exists(dedup_key):
                continue
            org = org_map.get(sub.org_id)
            org_name = org.name if org else f"org#{sub.org_id}"
            plan_name = _get_plan_name(sub, item_map, plan_map)

            if org and org.contact_email:
                subject = f"[OSD] Gói dịch vụ đã hết hạn — {plan_name}"
                body_html = (
                    f'<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px">'
                    f'<h2 style="color:#dc2626">Thông báo: Gói dịch vụ đã hết hạn</h2>'
                    f'<p>Kính gửi <strong>{html.escape(org_name or "")}</strong>,</p>'
                    f'<p>Gói dịch vụ <strong>{html.escape(plan_name or "")}</strong> của quý khách đã hết hạn vào ngày <strong>{today.strftime("%d/%m/%Y")}</strong>.</p>'
                    f'<p>Dịch vụ đã kết thúc. Vui lòng liên hệ với chúng tôi nếu quý khách muốn gia hạn hoặc đăng ký gói mới.</p>'
                    f'<p style="color:#6b7280;font-size:12px;margin-top:24px">OSD Support System</p>'
                    f'</body></html>'
                )
                body_text = f"Gói dịch vụ {plan_name} của {org_name} đã hết hạn vào {today}. Vui lòng liên hệ để gia hạn."
                send_email(org.contact_email, subject, body_html, body_text, db=db)

            for admin in admins:
                create_notification(
                    db,
                    user_id=admin.id,
                    title="Subscription expired",
                    content=f"Subscription #{sub.id} for org {org_name} expired on {today}",
                    type="expiry",
                )
            redis_client.setex(dedup_key, 86400 * 2, "1")
            expired_count += 1

        db.commit()
        return {"warned_30": warned_30, "warned_7": warned_7, "expired": expired_count}
    finally:
        db.close()
