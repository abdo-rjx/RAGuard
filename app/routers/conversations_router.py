"""Conversation listing (feature B1) — a user sees only their own threads."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_db
from app.models.feature_models import Conversation, Message
from app.schemas.chat import ConversationInfo, MessageInfo

router = APIRouter(prefix="/conversations", tags=["chat"])


@router.get("", response_model=list[ConversationInfo])
def list_conversations(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationInfo]:
    """The caller's own conversations, most recent first."""
    rows = (
        db.query(Conversation, func.count(Message.id).label("msg_count"))
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user.id)
        .group_by(Conversation.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return [
        ConversationInfo(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at.isoformat() if conv.created_at else None,
            message_count=count or 0,
        )
        for conv, count in rows
    ]


@router.get("/{conversation_id}", response_model=list[MessageInfo])
def get_conversation(
    conversation_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageInfo]:
    """Messages of one of the caller's conversations (ownership enforced)."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
        .all()
    )
    return [MessageInfo(**m.as_dict()) for m in rows]
