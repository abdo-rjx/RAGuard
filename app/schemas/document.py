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
