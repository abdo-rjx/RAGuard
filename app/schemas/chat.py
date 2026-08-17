"""Chat request/response models.

Design decision (plan Section 9 step 1): the chat request schema deliberately has NO
role/department field. Identity comes only from the verified JWT.
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    # Optional multi-turn support (feature B1): continue an existing conversation.
    conversation_id: int | None = None


class SourceInfo(BaseModel):
    document_id: int | None = None
    filename: str | None = None
    department: str | None = None
    classification: str | None = None  # feature B2 — surfaced so users see the badge


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceInfo] = []
    retrieval_note: str | None = None  # e.g. "no context retrieved" for debugging
    conversation_id: int | None = None  # feature B1 — id of the (possibly new) thread


class FeedbackRequest(BaseModel):
    """Feature B3 — feedback on an assistant answer. security_concern is a
    high-priority signal (surfaced in /security/reports), distinct from the
    generic satisfaction thumbs."""
    message: str = Field(..., min_length=1, max_length=8000)  # the user query being rated
    feedback: str = Field(..., pattern="^(thumbs_up|thumbs_down|security_concern)$")
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    ok: bool = True


class ConversationInfo(BaseModel):
    id: int
    title: str
    created_at: str | None = None
    message_count: int = 0


class MessageInfo(BaseModel):
    id: int
    role: str
    content: str
    sources: dict | list | None = None
    created_at: str | None = None
