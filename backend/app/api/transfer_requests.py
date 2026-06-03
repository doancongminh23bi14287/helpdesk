"""Ticket transfer request endpoints — staff-to-staff handoff with mutual consent."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ticket import Ticket
from app.models.user import User
from app.models.transfer_request import TicketTransferRequest
from app.core.deps import get_current_user
from app.services.notify import create_notification

router = APIRouter(prefix="/api/tickets", tags=["transfer-requests"])


class TransferRequestCreate(BaseModel):
    to_staff_id: int


def _req_out(req: TicketTransferRequest) -> dict:
    return {
        "id": req.id,
        "ticket_id": req.ticket_id,
        "from_staff_id": req.from_staff_id,
        "from_staff_name": req.from_staff.full_name if req.from_staff else f"Staff #{req.from_staff_id}",
        "to_staff_id": req.to_staff_id,
        "to_staff_name": req.to_staff.full_name if req.to_staff else f"Staff #{req.to_staff_id}",
        "status": req.status,
        "created_at": req.created_at.isoformat(),
    }


@router.post("/{ticket_id}/transfer-request")
def create_transfer_request(
    ticket_id: int,
    payload: TransferRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "customer":
        raise HTTPException(403, "Customers cannot transfer tickets")
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if user.role == "staff" and ticket.assignee_id != user.id:
        raise HTTPException(403, "You are not the current assignee")
    target = db.query(User).filter(User.id == payload.to_staff_id, User.role == "staff").first()
    if not target:
        raise HTTPException(404, "Target staff not found")
    if payload.to_staff_id == user.id:
        raise HTTPException(400, "Cannot transfer to yourself")
    # Cancel any existing pending request
    db.query(TicketTransferRequest).filter(
        TicketTransferRequest.ticket_id == ticket_id,
        TicketTransferRequest.status == "pending",
    ).update({"status": "declined", "resolved_at": datetime.utcnow()})
    req = TicketTransferRequest(
        ticket_id=ticket_id,
        from_staff_id=user.id,
        to_staff_id=payload.to_staff_id,
    )
    db.add(req)
    db.flush()
    create_notification(
        db,
        user_id=payload.to_staff_id,
        title=f"Transfer request — Ticket #{ticket_id}",
        content=f"{user.full_name} wants to transfer '{ticket.subject}' to you",
        type="assignment",
        ref_ticket_id=ticket_id,
    )
    db.commit()
    db.refresh(req)
    return _req_out(req)


@router.get("/{ticket_id}/transfer-request")
def get_transfer_request(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.query(TicketTransferRequest).filter(
        TicketTransferRequest.ticket_id == ticket_id,
        TicketTransferRequest.status == "pending",
    ).first()
    return _req_out(req) if req else None


@router.put("/{ticket_id}/transfer-request/{req_id}/accept")
def accept_transfer(
    ticket_id: int,
    req_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.query(TicketTransferRequest).filter(
        TicketTransferRequest.id == req_id,
        TicketTransferRequest.ticket_id == ticket_id,
        TicketTransferRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(404, "Transfer request not found or already resolved")
    if req.to_staff_id != user.id:
        raise HTTPException(403, "Only the target staff can accept")
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    ticket.assignee_id = user.id
    req.status = "accepted"
    req.resolved_at = datetime.utcnow()
    create_notification(
        db,
        user_id=req.from_staff_id,
        title=f"Transfer accepted — Ticket #{ticket_id}",
        content=f"{user.full_name} accepted the transfer of '{ticket.subject}'",
        type="assignment",
        ref_ticket_id=ticket_id,
    )
    db.commit()
    return {"status": "accepted", "assignee_id": user.id}


@router.put("/{ticket_id}/transfer-request/{req_id}/decline")
def decline_transfer(
    ticket_id: int,
    req_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.query(TicketTransferRequest).filter(
        TicketTransferRequest.id == req_id,
        TicketTransferRequest.ticket_id == ticket_id,
        TicketTransferRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(404, "Transfer request not found or already resolved")
    if req.to_staff_id != user.id and user.role != "admin":
        raise HTTPException(403, "Only the target staff or admin can decline")
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    req.status = "declined"
    req.resolved_at = datetime.utcnow()
    create_notification(
        db,
        user_id=req.from_staff_id,
        title=f"Transfer declined — Ticket #{ticket_id}",
        content=f"{user.full_name} declined the transfer of '{ticket.subject}'",
        type="assignment",
        ref_ticket_id=ticket_id,
    )
    db.commit()
    return {"status": "declined"}
