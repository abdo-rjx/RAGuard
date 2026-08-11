"""Auth request/response models."""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    department: str
    is_admin: bool


class UserInfo(BaseModel):
    id: int
    username: str
    role: str
    department: str
    is_admin: bool
