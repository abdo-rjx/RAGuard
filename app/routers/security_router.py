"""Security admin surfaces (features A4, A5, A6).

Separation of duties (A1):
  * Guard-pattern management (/security/patterns) is SYSTEM admin config work.
  * Reading alerts and user-submitted security reports is SECURITY admin work.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_security_admin, require_system_admin
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.feature_models import GuardPattern, SecurityAlert
from app.schemas.audit import AuditLogInfo, AuditLogPage
from app.schemas.security import GuardPatternIn, GuardPatternOut, SecurityAlertInfo
from app.security.pattern_store import refresh_pattern_cache

router = APIRouter(prefix="/security", tags=["security"])


# ---- A4: editable guard patterns (system admin) ------------------------------

@router.get("/patterns", response_model=list[GuardPatternOut])
def list_patterns(
    type: str | None = Query(default=None, pattern="^(injection|leak)$"),
    admin: CurrentUser = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> list[GuardPatternOut]:
    q = db.query(GuardPattern)
    if type:
        q = q.filter(GuardPattern.type == type)
    rows = q.order_by(GuardPattern.type, GuardPattern.id).all()
    return [_out(p) for p in rows]


@router.post("/patterns", response_model=GuardPatternOut, status_code=201)
def create_pattern(
    body: GuardPatternIn,
    admin: CurrentUser = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> GuardPatternOut:
    existing = db.query(GuardPattern).filter(GuardPattern.pattern == body.pattern).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Pattern already exists")
    row = GuardPattern(pattern=body.pattern, type=body.type, active=body.active)
    db.add(row)
    db.commit()
    db.refresh(row)
    refresh_pattern_cache()
    return _out(row)


@router.patch("/patterns/{pattern_id}", response_model=GuardPatternOut)
def update_pattern(
    pattern_id: int,
    body: GuardPatternIn,
    admin: CurrentUser = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> GuardPatternOut:
    row = db.query(GuardPattern).filter(GuardPattern.id == pattern_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    row.pattern = body.pattern
    row.type = body.type
    row.active = body.active
    db.commit()
    refresh_pattern_cache()
    return _out(row)


@router.delete("/patterns/{pattern_id}", status_code=204)
def delete_pattern(
    pattern_id: int,
    admin: CurrentUser = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    row = db.query(GuardPattern).filter(GuardPattern.id == pattern_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    db.delete(row)
    db.commit()
    refresh_pattern_cache()


def _out(p: GuardPattern) -> GuardPatternOut:
    return GuardPatternOut(
        id=p.id,
        pattern=p.pattern,
        type=p.type,
        active=p.active,
        created_at=p.created_at.isoformat() if p.created_at else None,
    )


# ---- A5: anomaly alerts (security admin) -------------------------------------

@router.get("/alerts", response_model=list[SecurityAlertInfo])
def list_alerts(
    admin: CurrentUser = Depends(require_security_admin),
    db: Session = Depends(get_db),
) -> list[SecurityAlertInfo]:
    """Users flagged \"needs review\" by the non-ML anomaly check (feature A5)."""
    rows = db.query(SecurityAlert).order_by(SecurityAlert.created_at.desc()).limit(200).all()
    return [SecurityAlertInfo(**r.as_dict()) for r in rows]


# ---- A6: user-submitted security reports (security admin) --------------------

@router.get("/reports", response_model=AuditLogPage)
def security_reports(
    user: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    admin: CurrentUser = Depends(require_security_admin),
    db: Session = Depends(get_db),
) -> AuditLogPage:
    """High-priority triage inbox: only user-submitted security concerns (feature B3),
    kept separate from generic quality feedback (CHAT_FEEDBACK)."""
    clauses = [AuditLog.action == "USER_REPORTED_SECURITY_CONCERN"]
    if user:
        clauses.append(AuditLog.username == user)
    if date_from:
        clauses.append(AuditLog.timestamp >= date_from)
    if date_to:
        clauses.append(AuditLog.timestamp <= date_to)

    total = db.query(AuditLog).filter(*clauses).count()
    rows = (
        db.query(AuditLog)
        .filter(*clauses)
        .order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AuditLogPage(total=total, items=[AuditLogInfo(**r.as_dict()) for r in rows])
