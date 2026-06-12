from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.attachment import TicketAttachment
from app.models.user import User
from app.core.deps import get_current_user
from app.core.scoping import get_ticket_in_scope
from app.services.file_storage import get_attachment_path

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attachment = db.query(TicketAttachment).filter(TicketAttachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Verify access via ticket scope
    ticket_id = attachment.ticket_id
    if ticket_id is None and attachment.reply_id:
        from app.models.ticket import TicketReply
        reply = db.query(TicketReply).filter(TicketReply.id == attachment.reply_id).first()
        ticket_id = reply.ticket_id if reply else None

    if ticket_id is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    try:
        get_ticket_in_scope(ticket_id, user, db)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Attachment not found")

    abs_path = get_attachment_path(attachment.file_path)
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(abs_path),
        filename=attachment.file_name,
        media_type=attachment.mime_type,
        content_disposition_type="attachment",
    )
