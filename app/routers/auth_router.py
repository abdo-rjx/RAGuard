"""POST /auth/login and GET /auth/me."""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.jwt_handler import create_access_token
from app.auth.password import verify_password
from app.audit.logger import write_audit_event
from app.database import get_db
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.auth import LoginRequest, LoginResponse, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")  # brute-force protection; disabled when ENVIRONMENT=test
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.username == body.username).first()

    if user is None or not verify_password(body.password, user.hashed_password):
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
            "is_admin": user.is_admin,
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
        is_admin=user.is_admin,
    )


@router.get("/me", response_model=UserInfo)
def me(user: CurrentUser = Depends(get_current_user)) -> UserInfo:
    return UserInfo(
        id=user.id,
        username=user.username,
        role=user.role,
        department=user.department,
        is_admin=user.is_admin,
    )
