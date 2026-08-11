"""Audit log response models."""
from pydantic import BaseModel


class AuditLogInfo(BaseModel):
    id: int
    timestamp: str | None = None
    user_id: int | None = None
    username: str | None = None
    role: str | None = None
    action: str
    query_text: str | None = None
    decision: str | None = None
    reason: str | None = None
    details_json: dict | None = None


class AuditLogPage(BaseModel):
    total: int
    items: list[AuditLogInfo]
