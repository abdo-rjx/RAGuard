"""Policy simulation schema (feature A2)."""
from pydantic import BaseModel


class SimulateResponse(BaseModel):
    role: str
    department: str
    classification: str
    decision: str  # "ALLOW" | "DENY"
