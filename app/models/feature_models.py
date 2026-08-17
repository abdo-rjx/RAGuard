"""Feature models: DB-backed guard patterns (A4), security alerts (A5),
and multi-turn conversations + messages (B1)."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GuardPattern(Base):
    """Editable, DB-backed guard patterns (feature A4).

    Replaces the hardcoded INJECTION_PATTERNS / LEAK_PATTERNS lists. Guards load
    only `active` patterns of their `type`; changes take effect after a cache refresh.
    """

    __tablename__ = "guard_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # "injection" | "leak"
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class SecurityAlert(Base):
    """Anomaly flag (feature A5): a user crossed the threshold of >5 denied /
    injection-suspected events within 10 minutes. Surfaces as \"needs review\"
    in the admin UI. Non-ML, written inline by the audit layer."""

    __tablename__ = "security_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_action: Mapped[str] = mapped_column(String(64), nullable=False)  # triggering action
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)  # events in the window
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "event_action": self.event_action,
            "event_count": self.event_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Conversation(Base):
    """A multi-turn chat thread (feature B1)."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(Base):
    """One turn in a conversation (feature B1)."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(String, nullable=False)
    sources_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "sources": self.sources_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
