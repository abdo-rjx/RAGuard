"""Auth request/response models."""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    department: str
    is_system_admin: bool
    is_security_admin: bool


class UserInfo(BaseModel):
    id: int
    username: str
    role: str
    department: str
    is_system_admin: bool
    is_security_admin: bool


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class QueryHistoryItem(BaseModel):
    query_text: str
    timestamp: str | None = None
    decision: str | None = None
    reason: str | None = None
