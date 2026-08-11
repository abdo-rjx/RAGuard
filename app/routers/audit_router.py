"""GET /audit/logs and GET /security/events (plan Section 12, Phase 6).

/security/events is a filtered view over the same audit table: rows where decision=DENY
or the action starts with INJECTION_ / OUTPUT_.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_admin
from app.database import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogInfo, AuditLogPage

router = APIRouter(tags=["audit"])

SECURITY_PREFIXES = ("INJECTION_", "OUTPUT_", "ACCESS_DENIED")


def _build_filters(
    user: str | None,
    decision: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    security_only: bool,
):
    clauses = []
    if user:
        clauses.append(AuditLog.username == user)
    if decision:
        clauses.append(AuditLog.decision == decision)
    if date_from:
        clauses.append(AuditLog.timestamp >= date_from)
    if date_to:
        clauses.append(AuditLog.timestamp <= date_to)
    if security_only:
        clauses.append(
            or_(
                AuditLog.decision == "DENY",
                *[AuditLog.action.startswith(p) for p in SECURITY_PREFIXES],
            )
        )
    return clauses


@router.get("/audit/logs", response_model=AuditLogPage)
def audit_logs(
    user: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AuditLogPage:
    clauses = _build_filters(user, decision, date_from, date_to, security_only=False)

    total = db.query(AuditLog).filter(and_(*clauses)).count() if clauses else db.query(AuditLog).count()
    rows = (
        db.query(AuditLog)
        .filter(and_(*clauses))
        .order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AuditLogPage(total=total, items=[AuditLogInfo(**r.as_dict()) for r in rows])


@router.get("/security/events", response_model=AuditLogPage)
def security_events(
    user: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AuditLogPage:
    clauses = _build_filters(user, decision, date_from, date_to, security_only=True)

    total = db.query(AuditLog).filter(and_(*clauses)).count()
    rows = (
        db.query(AuditLog)
        .filter(and_(*clauses))
        .order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AuditLogPage(total=total, items=[AuditLogInfo(**r.as_dict()) for r in rows])
