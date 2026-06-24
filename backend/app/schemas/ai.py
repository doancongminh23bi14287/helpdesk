from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AiPredictionOut(BaseModel):
    id: int
    ticket_id: int
    predicted_category: str
    predicted_priority: str
    predicted_department: Optional[str] = None
    confidence: Optional[float] = None
    model_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class AiReplyOut(BaseModel):
    id: int
    ticket_id: int
    generated_text: str
    accepted: bool
    edited: bool
    created_at: datetime

    class Config:
        from_attributes = True
