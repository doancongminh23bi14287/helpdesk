# backend/app/api/analytics.py
import csv
from io import StringIO
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.invoice import Invoice
from app.models.organization import Organization
from app.models.ticket import Ticket
from app.models.user import User
from app.core.deps import require_admin, require_staff_or_admin
from app.core.scoping import scope_tickets

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _parse_to_date(value: Optional[str]) -> Optional[datetime]:
    """Parse to_date, extending date-only values to end-of-day (23:59:59)."""
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    # If no time component was provided (date-only), advance to end of that day
    if 'T' not in str(value) and ':' not in str(value):
        dt = dt + timedelta(days=1) - timedelta(seconds=1)
    return dt


# ── GET /api/analytics/tickets ────────────────────────────────────────────────

@router.get("/tickets")
def ticket_analytics(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    q = db.query(Ticket).filter(Ticket.is_deleted == False)
    q = scope_tickets(q, user, db)

    if from_date:
        q = q.filter(Ticket.created_at >= _parse_date(from_date))
    if to_date:
        q = q.filter(Ticket.created_at <= _parse_to_date(to_date))
    if org_id is not None:
        q = q.filter(Ticket.org_id == org_id)

    tickets = q.all()
    total = len(tickets)

    by_status: dict = {}
    by_priority: dict = {}
    by_type: dict = {}
    daily: dict = {}
    resolution_hours: list = []

    for t in tickets:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        by_type[t.ticket_type] = by_type.get(t.ticket_type, 0) + 1

        day = t.created_at.date().isoformat() if t.created_at else None
        if day:
            daily[day] = daily.get(day, 0) + 1

        if t.resolved_at and t.created_at:
            delta = (t.resolved_at - t.created_at).total_seconds() / 3600
            resolution_hours.append(delta)

    avg_resolution = (
        round(sum(resolution_hours) / len(resolution_hours), 1)
        if resolution_hours else None
    )

    daily_trend = [{"date": d, "count": c} for d, c in sorted(daily.items())]

    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "by_type": by_type,
        "daily_trend": daily_trend,
        "avg_resolution_hours": avg_resolution,
    }


@router.get("/tickets.csv")
def ticket_analytics_csv(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    q = db.query(Ticket).filter(Ticket.is_deleted == False)
    q = scope_tickets(q, user, db)

    if from_date:
        q = q.filter(Ticket.created_at >= _parse_date(from_date))
    if to_date:
        q = q.filter(Ticket.created_at <= _parse_to_date(to_date))
    if org_id is not None:
        q = q.filter(Ticket.org_id == org_id)

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "org_id", "status", "priority", "ticket_type", "created_at", "resolved_at"])
    for t in q.order_by(Ticket.created_at.asc()).all():
        writer.writerow([
            t.id,
            t.org_id,
            t.status,
            t.priority,
            t.ticket_type,
            t.created_at.isoformat() if t.created_at else "",
            t.resolved_at.isoformat() if t.resolved_at else "",
        ])
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tickets-analytics.csv"'},
    )


# ── GET /api/analytics/sla ────────────────────────────────────────────────────

@router.get("/sla")
def sla_analytics(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    q = db.query(Ticket).filter(Ticket.is_deleted == False)
    q = scope_tickets(q, user, db)

    if from_date:
        q = q.filter(Ticket.created_at >= _parse_date(from_date))
    if to_date:
        q = q.filter(Ticket.created_at <= _parse_to_date(to_date))
    if org_id is not None:
        q = q.filter(Ticket.org_id == org_id)

    # Only tickets with a deadline set are counted for SLA
    q = q.filter(Ticket.resolution_by != None)  # noqa: E711
    tickets = q.all()

    total = len(tickets)
    sla_met = 0
    sla_breached = 0
    by_priority: dict = {}

    for t in tickets:
        pri = t.priority
        if pri not in by_priority:
            by_priority[pri] = {"met": 0, "breached": 0, "rate": 0.0}

        resolved = t.resolved_at is not None
        if resolved:
            met = t.resolved_at <= t.resolution_by
        else:
            met = t.resolution_by >= now

        if met:
            sla_met += 1
            by_priority[pri]["met"] += 1
        else:
            sla_breached += 1
            by_priority[pri]["breached"] += 1

    # Compute per-priority rates
    for pri, counts in by_priority.items():
        subtotal = counts["met"] + counts["breached"]
        counts["rate"] = round(counts["met"] / subtotal * 100, 1) if subtotal else 0.0

    compliance_rate = round(sla_met / total * 100, 1) if total else 0.0

    return {
        "total_tickets": total,
        "sla_met": sla_met,
        "sla_breached": sla_breached,
        "compliance_rate": compliance_rate,
        "by_priority": by_priority,
    }


# ── GET /api/analytics/agents ─────────────────────────────────────────────────

@router.get("/agents")
def agent_analytics(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    q = db.query(Ticket).filter(
        Ticket.is_deleted == False,
        Ticket.assignee_id != None,  # noqa: E711
    )
    if from_date:
        q = q.filter(Ticket.created_at >= _parse_date(from_date))
    if to_date:
        q = q.filter(Ticket.created_at <= _parse_to_date(to_date))

    tickets = q.all()

    agents: dict = {}
    for t in tickets:
        aid = t.assignee_id
        if aid not in agents:
            agents[aid] = {
                "assigned": 0,
                "resolved": 0,
                "resolution_hours": [],
                "sla_met": 0,
                "sla_total": 0,
            }
        agents[aid]["assigned"] += 1

        if t.status in ("Resolved", "Closed") and t.resolved_at:
            agents[aid]["resolved"] += 1
            if t.created_at:
                delta = (t.resolved_at - t.created_at).total_seconds() / 3600
                agents[aid]["resolution_hours"].append(delta)

        if t.resolution_by:
            agents[aid]["sla_total"] += 1
            resolved = t.resolved_at is not None
            if resolved:
                met = t.resolved_at <= t.resolution_by
            else:
                met = t.resolution_by >= now
            if met:
                agents[aid]["sla_met"] += 1

    # Fetch user info for all assignees
    user_rows = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(list(agents.keys()))).all()
    }

    result = []
    for aid, stats in agents.items():
        u = user_rows.get(aid)
        hours = stats["resolution_hours"]
        avg_hours = round(sum(hours) / len(hours), 1) if hours else None
        sla_rate = (
            round(stats["sla_met"] / stats["sla_total"] * 100, 1)
            if stats["sla_total"] else None
        )
        result.append({
            "user_id": aid,
            "name": u.full_name if u else None,
            "email": u.email if u else None,
            "tickets_assigned": stats["assigned"],
            "tickets_resolved": stats["resolved"],
            "avg_resolution_hours": avg_hours,
            "sla_compliance_rate": sla_rate,
        })

    result.sort(key=lambda x: x["tickets_assigned"], reverse=True)

    return {"agents": result}


# ── GET /api/analytics/revenue ────────────────────────────────────────────────

@router.get("/revenue")
def revenue_analytics(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    q = db.query(Invoice).filter(Invoice.status != "cancelled")

    if from_date:
        fd = _parse_date(from_date)
        q = q.filter(Invoice.issue_date >= fd.date() if fd else fd)
    if to_date:
        td = _parse_to_date(to_date)
        q = q.filter(Invoice.issue_date <= td.date() if td else td)
    if org_id is not None:
        q = q.filter(Invoice.org_id == org_id)

    invoices = q.all()

    total_invoiced = sum(float(inv.total) for inv in invoices)
    total_paid = sum(float(inv.total) for inv in invoices if inv.status == "paid")
    total_overdue = sum(float(inv.total) for inv in invoices if inv.status == "overdue")

    # Monthly breakdown
    monthly: dict = {}
    for inv in invoices:
        month = inv.issue_date.strftime("%Y-%m") if inv.issue_date else None
        if not month:
            continue
        if month not in monthly:
            monthly[month] = {"invoiced": 0.0, "paid": 0.0}
        monthly[month]["invoiced"] += float(inv.total)
        if inv.status == "paid":
            monthly[month]["paid"] += float(inv.total)

    by_month = [
        {"month": m, "invoiced": v["invoiced"], "paid": v["paid"]}
        for m, v in sorted(monthly.items())
    ]

    # Per-org breakdown
    org_totals: dict = {}
    for inv in invoices:
        oid = inv.org_id
        org_totals[oid] = org_totals.get(oid, 0.0) + float(inv.total)

    org_rows = {
        o.id: o
        for o in db.query(Organization).filter(Organization.id.in_(list(org_totals.keys()))).all()
    }

    by_org = [
        {
            "org_id": oid,
            "org_name": org_rows[oid].name if oid in org_rows else None,
            "total": total,
        }
        for oid, total in sorted(org_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_overdue": total_overdue,
        "by_month": by_month,
        "by_org": by_org,
    }
