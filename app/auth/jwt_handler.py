"""JWT create/decode. The user's role and department come ONLY from the verified JWT."""
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import settings


def create_access_token(subject: dict[str, Any], expires_minutes: int | None = None) -> str:
    """subject carries the identity claims: user_id, username, role, department."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES
    )
    payload = {**subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode + verify signature/expiry. Raises jwt.PyJWTError on any failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
