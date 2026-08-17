"""Document upload/list/delete response models."""
from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: int
    filename: str
    department: str
    classification: str
    chunks_created: int


class DocumentInfo(BaseModel):
    id: int
    filename: str
    department: str
    classification: str
    uploaded_at: str | None = None
    chunk_count: int = 0
    ingestion_status: str = "success"
    ingestion_error: str | None = None


class DocumentStatusResponse(BaseModel):
    """Feature A3 — ingestion status for one document."""
    document_id: int
    filename: str
    department: str
    classification: str
    status: str  # success | failed
    error: str | None = None
    chunk_count: int
    chroma_chunk_ids: list[str] = []
