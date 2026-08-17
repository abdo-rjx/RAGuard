"""AuditLog model (plan Section 6). One row per decision point."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Allowed action values — keep in sync with audit/logger.py
AUDIT_ACTIONS = [
    "LOGIN",
    "LOGIN_FAILED",
    "CHAT_QUERY",
    "CHAT_FEEDBACK",
    "USER_REPORTED_SECURITY_CONCERN",
    "DOCUMENT_UPLOAD",
    "DOCUMENT_DELETE",
    "ACCESS_DENIED",
    "INJECTION_SUSPECTED_QUERY",
    "INJECTION_SUSPECTED_CONTEXT",
    "OUTPUT_BLOCKED",
    "PASSWORD_CHANGED",
]


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # null for pre-auth
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query_text: Mapped[str | None] = mapped_column(String, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)  # ALLOW / DENY
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "action": self.action,
            "query_text": self.query_text,
            "decision": self.decision,
            "reason": self.reason,
            "details_json": self.details_json,
        }
