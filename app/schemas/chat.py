"""Chat request/response models.

Design decision (plan Section 9 step 1): the chat request schema deliberately has NO
role/department field. Identity comes only from the verified JWT.
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


class SourceInfo(BaseModel):
    document_id: int | None = None
    filename: str | None = None
    department: str | None = None
    classification: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceInfo] = []
    retrieval_note: str | None = None  # e.g. "no context retrieved" for debugging
