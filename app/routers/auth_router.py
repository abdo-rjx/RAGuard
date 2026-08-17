"""POST /auth/login, GET /auth/me, plus self-service endpoints (feature B4)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.jwt_handler import create_access_token
from app.auth.password import hash_password, verify_password
from app.audit.logger import write_audit_event
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    QueryHistoryItem,
    UserInfo,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Precomputed lazily: a real bcrypt hash used only to equalize response timing
# when the username doesn't exist, so login latency doesn't reveal whether an
# account is registered (username-enumeration side channel).
_dummy_hash: str | None = None


def _get_dummy_hash() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("dummy-password-for-timing-equalization")
    return _dummy_hash


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")  # brute-force protection; disabled when ENVIRONMENT=test
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.username == body.username).first()

    if user is None:
        # Verify against a dummy hash so the bcrypt cost runs regardless of
        # whether the username exists (timing side-channel defense).
        verify_password(body.password, _get_dummy_hash())
        write_audit_event(
            db=db,
            action="LOGIN_FAILED",
            username=body.username,
            role=None,
            reason="invalid_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not verify_password(body.password, user.hashed_password):
        write_audit_event(
            db=db,
            action="LOGIN_FAILED",
            username=body.username,
            role=None,
            reason="invalid_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        write_audit_event(
            db=db,
            action="LOGIN_FAILED",
            user_id=user.id,
            username=user.username,
            role=user.role.name if user.role else None,
            reason="account_inactive",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    token = create_access_token(
        {
            "user_id": user.id,
            "username": user.username,
            "role": user.role.name if user.role else None,
            "department": user.department.name if user.department else None,
            "is_system_admin": user.is_system_admin,
            "is_security_admin": user.is_security_admin,
            "ver": user.token_version,  # revocation: bump on password change
        }
    )

    write_audit_event(
        db=db,
        action="LOGIN",
        user_id=user.id,
        username=user.username,
        role=user.role.name if user.role else None,
        decision="ALLOW",
        reason="login_success",
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        role=user.role.name if user.role else "",
        department=user.department.name if user.department else "",
        is_system_admin=user.is_system_admin,
        is_security_admin=user.is_security_admin,
    )


@router.get("/me", response_model=UserInfo)
def me(user: CurrentUser = Depends(get_current_user)) -> UserInfo:
    return UserInfo(
        id=user.id,
        username=user.username,
        role=user.role,
        department=user.department,
        is_system_admin=user.is_system_admin,
        is_security_admin=user.is_security_admin,
    )


@router.get("/me/queries", response_model=list[QueryHistoryItem])
def my_query_history(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[QueryHistoryItem]:
    """Feature B4 — the caller's own recent chat queries (self-service; their data only)."""
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user.id, AuditLog.action == "CHAT_QUERY")
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        QueryHistoryItem(
            query_text=r.query_text or "",
            timestamp=r.timestamp.isoformat() if r.timestamp else None,
            decision=r.decision,
            reason=r.reason,
        )
        for r in rows
    ]


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")  # guards brute-forcing the current password

def change_password(
    request: Request,
    body: PasswordChangeRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Feature B4 — change the caller's own password (verify current first).
    Bumps token_version so all previously issued JWTs are revoked immediately."""
    db_user = db.query(User).filter(User.id == user.id).first()
    if db_user is None or not verify_password(body.current_password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    db_user.hashed_password = hash_password(body.new_password)
    db_user.token_version += 1  # revoke every outstanding token
    db.commit()
    write_audit_event(
        db,
        action="PASSWORD_CHANGED",
        user_id=user.id,
        username=user.username,
        role=user.role,
        decision="ALLOW",
        reason="password_changed",
    )
