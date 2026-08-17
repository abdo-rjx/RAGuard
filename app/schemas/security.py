"""Guard-pattern (A4) and security-alert (A5) schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class GuardPatternIn(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=512)
    type: str = Field(..., pattern="^(injection|leak)$")
    active: bool = True


class GuardPatternOut(BaseModel):
    id: int
    pattern: str
    type: str
    active: bool
    created_at: str | None = None


class SecurityAlertInfo(BaseModel):
    id: int
    user_id: int | None = None
    username: str | None = None
    event_action: str
    event_count: int
    created_at: str | None = None
