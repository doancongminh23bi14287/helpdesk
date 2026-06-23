# backend/app/api/analytics.py
import csv
from io import StringIO
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.invoice import Invoice
from app.models.organization import Organization
from app.models.ticket import Ticket
from app.models.user import User
from app.core.deps import require_admin, require_staff_or_admin
from app.core.scoping import scope_tickets

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_OPEN_STATUSES = ("Open", "In Progress", "Waiting")
_RESOLVED_STATUSES = ("Resolved", "Closed")


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _parse_to_date(value: Optional[str]) -> Optional[datetime]:
    """Parse to_date, extending date-only values to end-of-day (23:59:59)."""
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if 'T' not in str(value) and ':' not in str(value):
        dt = dt + timedelta(days=1) - timedelta(seconds=1)
    return dt


def _apply_filters(q, from_date, to_date, org_id):
    if from_date:
        q = q.filter(Ticket.created_at >= _parse_date(from_date))
    if to_date:
        q = q.filter(Ticket.created_at <= _parse_to_date(to_date))
    if org_id is not None:
        q = q.filter(Ticket.org_id == org_id)
    return q


# ── GET /api/analytics/tickets ────────────────────────────────────────────────

@router.get("/tickets")
def ticket_analytics(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    base_q = db.query(Ticket).filter(Ticket.is_deleted == False)
    base_q = scope_tickets(base_q, user, db)
    base_q = _apply_filters(base_q, from_date, to_date, org_id)

    # Total count at DB level
    total = base_q.count()

    # Group-by counts — no Python-side iteration
    by_status: dict = dict(
        base_q.with_entities(Ticket.status, func.count(Ticket.id))
        .group_by(Ticket.status)
        .all()
    )
    by_priority: dict = dict(
        base_q.with_entities(Ticket.priority, func.count(Ticket.id))
        .group_by(Ticket.priority)
        .all()
    )
    by_type: dict = dict(
        base_q.with_entities(Ticket.ticket_type, func.count(Ticket.id))
        .group_by(Ticket.ticket_type)
        .all()
    )

    # Daily trend — group by date at DB level
    daily_rows = (
        base_q
        .with_entities(func.date(Ticket.created_at).label("day"), func.count(Ticket.id))
        .group_by("day")
        .order_by("day")
        .all()
    )
    daily_trend = [{"date": str(row[0]), "count": row[1]} for row in daily_rows]

    # Avg resolution — fetch only 2 columns for resolved tickets (avoids loading full rows)
    res_rows = (
        base_q
        .filter(Ticket.resolved_at.isnot(None), Ticket.created_at.isnot(None))
        .with_entities(Ticket.created_at, Ticket.resolved_at)
        .all()
    )
    resolution_hours = [
        (row[1] - row[0]).total_seconds() / 3600
        for row in res_rows
    ]
    avg_resolution = (
        round(sum(resolution_hours) / len(resolution_hours), 1)
        if resolution_hours else None
    )

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
    q = _apply_filters(q, from_date, to_date, org_id)

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

    base_q = db.query(Ticket).filter(Ticket.is_deleted == False)
    base_q = scope_tickets(base_q, user, db)
    base_q = _apply_filters(base_q, from_date, to_date, org_id)

    # ── sla_state distribution (all tickets, column-based) ────────────────────
    sla_state_rows = (
        base_q
        .with_entities(Ticket.sla_state, func.count(Ticket.id))
        .group_by(Ticket.sla_state)
        .all()
    )
    by_sla_state: dict = {row[0]: row[1] for row in sla_state_rows if row[0] is not None}

    sla_total_all = sum(by_sla_state.values())
    sla_state_breached = by_sla_state.get("breached", 0)
    sla_state_compliance_rate = (
        round((sla_total_all - sla_state_breached) / sla_total_all * 100, 1)
        if sla_total_all else 0.0
    )

    # ── deadline-based compliance (tickets with resolution_by set) ────────────
    dl_q = base_q.filter(Ticket.resolution_by.isnot(None))
    dl_tickets = (
        dl_q.with_entities(Ticket.resolved_at, Ticket.resolution_by).all()
    )

    total = len(dl_tickets)
    sla_met = 0
    sla_breached_deadline = 0
    by_priority: dict = {}

    # Group by priority counts for deadline-based compliance
    priority_rows = (
        dl_q.with_entities(Ticket.priority, Ticket.resolved_at, Ticket.resolution_by).all()
    )
    for pri, resolved_at, resolution_by in priority_rows:
        if pri not in by_priority:
            by_priority[pri] = {"met": 0, "breached": 0, "rate": 0.0}
        if resolved_at is not None:
            met = resolved_at <= resolution_by
        else:
            met = resolution_by >= now
        if met:
            by_priority[pri]["met"] += 1
        else:
            by_priority[pri]["breached"] += 1

    for pri, counts in by_priority.items():
        subtotal = counts["met"] + counts["breached"]
        counts["rate"] = round(counts["met"] / subtotal * 100, 1) if subtotal else 0.0

    sla_met = sum(c["met"] for c in by_priority.values())
    sla_breached_deadline = sum(c["breached"] for c in by_priority.values())
    compliance_rate = round(sla_met / total * 100, 1) if total else 0.0

    return {
        # Deadline-based fields (existing — kept for backward compat)
        "total_tickets": total,
        "sla_met": sla_met,
        "sla_breached": sla_breached_deadline,
        "compliance_rate": compliance_rate,
        "by_priority": by_priority,
        # New: sla_state column-based distribution
        "by_sla_state": by_sla_state,
        "sla_state_compliance_rate": sla_state_compliance_rate,
        "sla_state_breached": sla_state_breached,
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
        Ticket.assignee_id.isnot(None),
    )
    q = _apply_filters(q, from_date, to_date, org_id=None)

    tickets = q.all()

    agents: dict = {}
    for t in tickets:
        aid = t.assignee_id
        if aid not in agents:
            agents[aid] = {
                "open": 0,
                "assigned": 0,
                "resolved": 0,
                "resolution_hours": [],
                "sla_met": 0,
                "sla_total": 0,
            }
        agents[aid]["assigned"] += 1

        if t.status in _OPEN_STATUSES:
            agents[aid]["open"] += 1

        if t.status in _RESOLVED_STATUSES and t.resolved_at:
            agents[aid]["resolved"] += 1
            if t.created_at:
                delta = (t.resolved_at - t.created_at).total_seconds() / 3600
                agents[aid]["resolution_hours"].append(delta)

        if t.resolution_by:
            agents[aid]["sla_total"] += 1
            if t.resolved_at is not None:
                met = t.resolved_at <= t.resolution_by
            else:
                met = t.resolution_by >= now
            if met:
                agents[aid]["sla_met"] += 1

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
            "tickets_open": stats["open"],
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
    year: Optional[int] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    from datetime import date
    target_year = None

    if year is not None or (from_date is None and to_date is None):
        target_year = year if year is not None else datetime.now().year
        range_start = date(target_year, 1, 1)
        range_end = date(target_year, 12, 31)
        q = db.query(Invoice).filter(
            Invoice.status != "cancelled",
            Invoice.issue_date >= range_start,
            Invoice.issue_date <= range_end,
        )
    else:
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

    active_year = target_year if (year is not None or (from_date is None and to_date is None)) else None
    if active_year:
        monthly: dict = {f"{active_year}-{m:02d}": {"invoiced": 0.0, "paid": 0.0} for m in range(1, 13)}
    else:
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
        "year": active_year,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_overdue": total_overdue,
        "by_month": by_month,
        "by_org": by_org,
    }
