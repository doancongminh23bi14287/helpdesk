from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AiPredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    predicted_category: str
    predicted_priority: str
    predicted_department: Optional[str] = None
    confidence: Optional[float] = None
    model_name: str
    created_at: datetime


class AiSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    summary_text: str
    summary_count: int
    created_at: datetime
    cooldown_remaining: int = 0
    max_summaries: int = 10


class AiReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    generated_text: str
    accepted: bool
    edited: bool
    created_at: datetime
