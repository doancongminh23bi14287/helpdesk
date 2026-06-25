"""
seed_ai_demo.py — Idempotent AI demo ticket seeder.

Run from backend/:
    source venv/bin/activate && python scripts/seed_ai_demo.py

Creates 5 realistic Vietnamese-language tickets on the Aloha Vietnam org
so that the AI classify feature can be demonstrated live.
Idempotent: tickets identified by subject; existing ones are skipped.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.organization import Organization
from app.models.service import ServiceCategory, Service
from app.models.ticket import Ticket
from app.models.user import User

ALOHA_CODE = "ALOHA-VN"

DEMO_TICKETS = [
    dict(
        subject="Website bị lỗi 500 sau khi cập nhật",
        description=(
            "Sau khi thực hiện cập nhật plugin WooCommerce lên phiên bản mới nhất vào chiều hôm qua, "
            "toàn bộ trang web của chúng tôi trả về lỗi HTTP 500 Internal Server Error. "
            "Khách hàng không thể truy cập được trang chủ lẫn trang thanh toán, ảnh hưởng nghiêm trọng đến doanh thu. "
            "Chúng tôi đã thử rollback plugin nhưng lỗi vẫn còn, có thể do cache hoặc database bị ảnh hưởng."
        ),
        priority="High",
        ticket_type="Bug",
        source="portal",
    ),
    dict(
        subject="Gia hạn gói hosting LS-M cho tháng tới",
        description=(
            "Gói hosting LS-M của chúng tôi sẽ hết hạn vào ngày 15 tháng tới, "
            "chúng tôi muốn gia hạn thêm 12 tháng với chu kỳ thanh toán hàng năm để được chiết khấu. "
            "Xin hỏi quy trình gia hạn như thế nào và có cần xuất hoá đơn VAT hay không? "
            "Chúng tôi cũng muốn hỏi về việc nâng cấp dung lượng đĩa từ 20GB lên 50GB trong đợt gia hạn này."
        ),
        priority="Medium",
        ticket_type="Renewal",
        source="portal",
    ),
    dict(
        subject="Không nhận được email từ domain aloha-vn.com",
        description=(
            "Từ sáng nay, toàn bộ hộp thư đến của domain aloha-vn.com đều không nhận được email mới. "
            "Chúng tôi đã kiểm tra MX record và DKIM nhưng không phát hiện thay đổi gì. "
            "Một số email quan trọng từ đối tác và khách hàng đang bị trả lại với thông báo 'mailbox unavailable'. "
            "Sự cố này ảnh hưởng đến toàn bộ 12 tài khoản email trong tổ chức kể từ 08:00 sáng."
        ),
        priority="High",
        ticket_type="Incident",
        source="portal",
    ),
    dict(
        subject="Hỏi về nâng cấp lên gói hosting LS-L",
        description=(
            "Hiện tại chúng tôi đang dùng gói LS-M với dung lượng 20GB và băng thông 500GB/tháng. "
            "Do lưu lượng truy cập tăng đáng kể trong quý vừa rồi, chúng tôi muốn tìm hiểu về gói LS-L. "
            "Bạn có thể cho biết sự khác biệt về tài nguyên, hiệu năng và chi phí giữa hai gói không? "
            "Đồng thời chúng tôi muốn biết thời gian chuyển đổi gói có gây downtime không."
        ),
        priority="Low",
        ticket_type="Question",
        source="portal",
    ),
    dict(
        subject="Website load chậm vào giờ cao điểm",
        description=(
            "Mỗi ngày từ 19:00 đến 22:00, website của chúng tôi có thời gian tải trang trung bình trên 8 giây, "
            "trong khi giờ bình thường chỉ khoảng 1.5 giây. "
            "Chúng tôi đã cài GTmetrix và thấy thời gian TTFB (Time to First Byte) từ server rất cao trong khung giờ này. "
            "Nghi ngờ đây là vấn đề về tài nguyên CPU/RAM trên server hoặc cần bật thêm cơ chế caching phía server."
        ),
        priority="Medium",
        ticket_type="Incident",
        source="portal",
    ),
]


def main():
    db = SessionLocal()
    try:
        print("\n" + "=" * 58)
        print("  AI Demo Ticket Seeder")
        print("=" * 58)

        aloha = db.query(Organization).filter(Organization.code == ALOHA_CODE).first()
        if not aloha:
            print(f"  [ERROR] Org '{ALOHA_CODE}' not found. Run seed_base.py first.")
            return

        print(f"  Org: {aloha.name} (id={aloha.id})")

        # Get or create a hosting service for Aloha
        service = db.query(Service).filter(Service.org_id == aloha.id).first()
        if not service:
            cat = db.query(ServiceCategory).filter(ServiceCategory.slug == "hosting").first()
            service = Service(
                org_id=aloha.id,
                category_id=cat.id if cat else None,
                type="hosting",
                name="Hosting LS-M",
                status="active",
            )
            db.add(service)
            db.flush()
            print(f"  [OK] Created service 'Hosting LS-M' id={service.id}")
        else:
            print(f"  [exists] Service '{service.name}' id={service.id}")

        # Get customer user for Aloha
        customer = db.query(User).filter(
            User.org_id == aloha.id,
            User.role == "customer",
        ).first()
        raised_by_email = customer.email if customer else "customer@aloha-vn.com"
        raised_by_id = customer.id if customer else None

        print(f"\n  Creating tickets for org '{aloha.name}':")
        created_ids = []
        for t in DEMO_TICKETS:
            existing = db.query(Ticket).filter(
                Ticket.org_id == aloha.id,
                Ticket.subject == t["subject"],
                Ticket.is_deleted == False,
            ).first()
            if existing:
                print(f"  [exists] #{existing.id} — {t['subject'][:50]}")
                created_ids.append(existing.id)
                continue

            ticket = Ticket(
                org_id=aloha.id,
                service_id=service.id,
                subject=t["subject"],
                description=t["description"],
                priority=t["priority"],
                ticket_type=t["ticket_type"],
                source=t["source"],
                status="Open",
                raised_by=raised_by_id,
                raised_by_email=raised_by_email,
            )
            db.add(ticket)
            db.flush()
            created_ids.append(ticket.id)
            print(f"  [OK]     #{ticket.id} — {t['subject'][:50]}")

        db.commit()
        print(f"\n  Done. Ticket IDs: {created_ids}")
        print("  → Go to the UI, open each ticket, click 'Phân tích AI' to demo live classification.")
        print("=" * 58 + "\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
