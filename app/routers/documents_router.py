"""POST/GET/DELETE /documents (plan Sections 8, 12). Upload/delete are system-admin
only (feature A1); listing is policy-filtered; status (A3) is policy-visible."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.audit.logger import write_audit_event
from app.auth.dependencies import CurrentUser, get_current_user, require_system_admin
from app.database import get_db
from app.ingestion.chunker import chunk_text
from app.ingestion.embedder import embed_texts
from app.ingestion.extractor import extract_text
from app.models.document import Document
from app.models.user import Department
from app.policy.policy_engine import get_policy_engine
from app.retrieval.vector_store import get_vector_store
from app.schemas.document import DocumentInfo, DocumentStatusResponse, DocumentUploadResponse
from app.config import settings

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
# Cap uploads so a single request can't balloon memory (whole file is read for
# extraction). 10 MB matches the frontend's stated limit.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _get_department(db: Session, name: str) -> Department:
    dept = db.query(Department).filter(Department.name == name).first()
    if dept is None:
        raise HTTPException(status_code=400, detail=f"Unknown department: {name}")
    return dept


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    department: str = Form(...),
    classification: str = Form(...),
    file: UploadFile = File(...),
    admin: CurrentUser = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    policy = get_policy_engine()

    # Validate department + classification against the policy source of truth.
    _get_department(db, department)
    if not policy.valid_classification(classification):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid classification: {classification} (valid: {', '.join(policy.all_classifications())})",
        )

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type (supported: {', '.join(sorted(ALLOWED_EXTENSIONS))})")

    # Reject oversized uploads up front (Content-Length when available, else the
    # actual read) so a huge file can't be buffered into memory.
    declared = getattr(file, "size", None)
    if declared is not None and declared > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")

    # Save the raw file to the uploads dir (reading at most MAX_UPLOAD_BYTES+1).
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    upload_path = settings.uploads_dir / safe_name
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    upload_path.write_bytes(content)

    # Create the Document row first so ingestion failures leave a traceable
    # "failed" record (feature A3) instead of an untracked exception.
    doc = Document(
        filename=file.filename or safe_name,
        department_id=_get_department(db, department).id,
        classification=classification,
        owner_id=admin.id,
        chroma_chunk_ids=[],
        ingestion_status="success",
        ingestion_error=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        # Extract → chunk → embed.
        raw_text = extract_text(upload_path)
        chunks = chunk_text(raw_text)
        if not chunks:
            raise HTTPException(status_code=400, detail="No text extracted from the uploaded file")

        embeddings = embed_texts(chunks)

        # Upsert into Chroma with access metadata on every chunk.
        chunk_ids = [f"doc-{uuid.uuid4().hex}" for _ in chunks]
        metadatas = [
            {
                "document_id": 0,  # filled below after the DB row exists
                "department": department,
                "classification": classification,
                "chunk_index": i,
                "source_filename": file.filename,
            }
            for i in range(len(chunks))
        ]

        # Fill real document_id into metadata + persist to Chroma.
        for m in metadatas:
            m["document_id"] = doc.id
        get_vector_store().upsert(ids=chunk_ids, embeddings=embeddings, metadatas=metadatas, documents=chunks)

        doc.chroma_chunk_ids = chunk_ids
        doc.ingestion_status = "success"
        doc.ingestion_error = None
        db.add(doc)
        db.commit()
    except HTTPException:
        _mark_failed(doc, db, "request_rejected")
        raise
    except Exception as e:  # noqa: BLE001 — record any pipeline failure for A3
        _mark_failed(doc, db, str(e)[:500])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {e}",
        )

    write_audit_event(
        db,
        action="DOCUMENT_UPLOAD",
        user_id=admin.id,
        username=admin.username,
        role=admin.role,
        decision="ALLOW",
        details_json={
            "document_id": doc.id,
            "filename": doc.filename,
            "department": department,
            "classification": classification,
            "chunks_created": len(chunks),
        },
    )

    return DocumentUploadResponse(
        document_id=doc.id,
        filename=doc.filename,
        department=department,
        classification=classification,
        chunks_created=len(chunks),
    )


def _mark_failed(doc: Document, db: Session, error: str) -> None:
    """Feature A3 — record a failed ingestion so /documents/{id}/status can report it."""
    try:
        doc.ingestion_status = "failed"
        doc.ingestion_error = error
        db.add(doc)
        db.commit()
    except Exception:
        db.rollback()


@router.get("", response_model=list[DocumentInfo])
def list_documents(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentInfo]:
    # Filter to the departments AND classifications the caller's role may access
    # (plan Section 12) — the same policy as the retrieval path, so the listing
    # never reveals documents above the caller's ceiling.
    policy = get_policy_engine()
    clauses = [
        and_(
            Department.name == dept,
            Document.classification.in_(policy.allowed_classifications(user.role, dept)),
        )
        for dept in policy.allowed_departments(user.role)
    ]
    if not clauses:
        return []
    docs = (
        db.query(Document)
        .join(Department)
        .filter(or_(*clauses))
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return [DocumentInfo(**d.as_dict()) for d in docs]


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def document_status(
    document_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentStatusResponse:
    """Feature A3 — ingestion status for one document. Visible only to callers whose
    role can access the document (same policy as the listing), so it never reveals
    the existence of a document above the caller's ceiling."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    policy = get_policy_engine()
    dept_name = doc.department.name if doc.department else ""
    if not policy.can_access_document(user.role, dept_name, doc.classification):
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentStatusResponse(
        document_id=doc.id,
        filename=doc.filename,
        department=dept_name,
        classification=doc.classification,
        status=doc.ingestion_status,
        error=doc.ingestion_error,
        chunk_count=len(doc.chroma_chunk_ids or []),
        chroma_chunk_ids=doc.chroma_chunk_ids or [],
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    admin: CurrentUser = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_ids = doc.chroma_chunk_ids or []
    if chunk_ids:
        get_vector_store().delete_by_ids(chunk_ids)

    write_audit_event(
        db,
        action="DOCUMENT_DELETE",
        user_id=admin.id,
        username=admin.username,
        role=admin.role,
        decision="ALLOW",
        details_json={"document_id": doc.id, "filename": doc.filename, "chunks_deleted": len(chunk_ids)},
    )

    db.delete(doc)
    db.commit()
