"""Audit logging — one row per decision point (plan Section 6, Phase 6)."""
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit_event(
    db: Session,
    action: str,
    *,
    user_id: int | None = None,
    username: str | None = None,
    role: str | None = None,
    query_text: str | None = None,
    decision: str | None = None,
    reason: str | None = None,
    details_json: dict[str, Any] | None = None,
) -> None:
    """Write an audit row. Never raises — logging must not break the request path."""
    try:
        entry = AuditLog(
            user_id=user_id,
            username=username,
            role=role,
            action=action,
            query_text=query_text,
            decision=decision,
            reason=reason,
            details_json=details_json,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
