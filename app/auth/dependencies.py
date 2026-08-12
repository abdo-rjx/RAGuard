"""FastAPI dependencies: get_current_user, require_admin.

The JWT authenticates WHO you are; the DB is the source of truth for WHAT you
are right now. Every request re-checks that the account still exists and is
active, and reads the current role/department/admin flag from the DB — so a
deactivation, deletion, or role change takes effect immediately, not when the
token expires. Identity never comes from the request body or message text
(plan Section 4, property 1).
"""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt_handler import decode_token
from app.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    role: str
    department: str
    is_admin: bool

    @property
    def department_id(self) -> int:
        raise AttributeError("department_id is not available on the JWT-derived identity")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The DB — not the token — decides what this user can do right now.
    # Deactivated or deleted accounts lose access immediately; role changes
    # apply on the next request instead of waiting for token expiry.
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled or no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        id=user.id,
        username=user.username,
        role=user.role.name if user.role else "",
        department=user.department.name if user.department else "",
        is_admin=user.is_admin,
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


def get_active_user_db(username: str, db: Session = Depends(get_db)) -> User | None:
    return db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
