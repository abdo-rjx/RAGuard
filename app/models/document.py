"""Document model (plan Section 6). Stores origin + chunk IDs for later Chroma deletion."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # None for CLI/system ingest
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    # JSON list of Chroma chunk IDs — enables deleting a doc's chunks later
    chroma_chunk_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Ingestion state (feature A3): "success" (default) or "failed" + reason,
    # surfaced via GET /documents/{id}/status.
    ingestion_status: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    ingestion_error: Mapped[str | None] = mapped_column(String, nullable=True)

    department: Mapped["Department"] = relationship(back_populates="documents")
    owner: Mapped["User"] = relationship()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "department": self.department.name if self.department else None,
            "classification": self.classification,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "chunk_count": len(self.chroma_chunk_ids or []),
            "ingestion_status": self.ingestion_status,
            "ingestion_error": self.ingestion_error,
        }
