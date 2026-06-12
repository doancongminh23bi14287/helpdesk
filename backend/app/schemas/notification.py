# backend/app/schemas/notification.py
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    content: Optional[str] = None
    type: str
    ref_ticket_id: Optional[int] = None
    is_read: bool
    created_at: datetime
