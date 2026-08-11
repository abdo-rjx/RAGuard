"""CLI batch ingest of documents into RAGGuard.

Ingests every file in a directory (or a set of explicit paths) into Chroma + SQLite
using the same pipeline as POST /documents: extract → chunk → embed → upsert.

Usage:
    python scripts/ingest_documents.py                          # ingests data/sample_docs/*
    python scripts/ingest_documents.py path/to/doc.pdf other.md
    python scripts/ingest_documents.py --dir data/sample_docs
    python scripts/ingest_documents.py --dry-run

Document metadata (department/classification) can come from a sidecar `<file>.meta.yaml`
or from a `--defaults "department=it classification=INTERNAL"` flag. Without either,
the script refuses to ingest a file whose department/classification is unknown.
"""
import argparse
import sys
import uuid
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audit.logger import write_audit_event  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.ingestion.chunker import chunk_text  # noqa: E402
from app.ingestion.embedder import embed_texts  # noqa: E402
from app.ingestion.extractor import extract_text  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.user import Department  # noqa: E402
from app.policy.policy_engine import get_policy_engine  # noqa: E402
from app.retrieval.vector_store import get_vector_store  # noqa: E402

DEFAULT_DIR = settings.uploads_dir.parent / "sample_docs"


def _resolve_meta(path: Path, defaults: dict) -> tuple[str, str]:
    sidecar = path.with_suffix(path.suffix + ".meta.yaml")
    if sidecar.exists():
        meta = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
        return meta.get("department", ""), meta.get("classification", "")

    dept = defaults.get("department", "")
    classification = defaults.get("classification", "")
    if dept and classification:
        return dept, classification

    raise SystemExit(
        f"No metadata for {path.name}. Provide a '{sidecar.name}' sidecar or pass "
        "--defaults 'department=<name> classification=<level>'."
    )


def ingest(path: Path, defaults: dict, dry_run: bool) -> None:
    department_name, classification = _resolve_meta(path, defaults)
    policy = get_policy_engine()

    db = SessionLocal()
    try:
        dept = db.query(Department).filter(Department.name == department_name).first()
        if dept is None:
            print(f"SKIP {path.name}: unknown department '{department_name}'")
            return
        if not policy.valid_classification(classification):
            print(f"SKIP {path.name}: unknown classification '{classification}'")
            return

        raw_text = extract_text(path)
        chunks = chunk_text(raw_text)
        if not chunks:
            print(f"SKIP {path.name}: no text extracted")
            return

        if dry_run:
            print(f"DRY {path.name}: {len(chunks)} chunks ({department_name}/{classification})")
            return

        embeddings = embed_texts(chunks)
        chunk_ids = [f"doc-{uuid.uuid4().hex}" for _ in chunks]
        metadatas = [
            {
                "document_id": 0,
                "department": department_name,
                "classification": classification,
                "chunk_index": i,
                "source_filename": path.name,
            }
            for i in range(len(chunks))
        ]

        doc = Document(
            filename=path.name,
            department_id=dept.id,
            classification=classification,
            owner_id=None,  # system ingest; owner not meaningful here
            chroma_chunk_ids=[],
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        for m in metadatas:
            m["document_id"] = doc.id
        get_vector_store().upsert(ids=chunk_ids, embeddings=embeddings, metadatas=metadatas, documents=chunks)

        doc.chroma_chunk_ids = chunk_ids
        db.add(doc)
        db.commit()

        write_audit_event(
            db,
            action="DOCUMENT_UPLOAD",
            username="system",
            role="system",
            decision="ALLOW",
            details_json={
                "document_id": doc.id,
                "filename": doc.filename,
                "department": department_name,
                "classification": classification,
                "chunks_created": len(chunks),
            },
        )
        print(f"OK  {path.name}: {len(chunks)} chunks → doc #{doc.id} ({department_name}/{classification})")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-ingest documents into RAGGuard.")
    parser.add_argument("paths", nargs="*", help="explicit file paths")
    parser.add_argument("--dir", default=None, help="directory to scan (default: data/sample_docs)")
    parser.add_argument("--defaults", default="", help="'department=<x> classification=<y>' for files without a sidecar")
    parser.add_argument("--dry-run", action="store_true", help="only report what would be ingested")
    args = parser.parse_args()

    defaults: dict = {}
    for token in args.defaults.split():
        if "=" in token:
            k, v = token.split("=", 1)
            defaults[k] = v

    if args.paths:
        files = [Path(p) for p in args.paths]
    else:
        directory = Path(args.dir) if args.dir else DEFAULT_DIR
        files = sorted(directory.glob("*")) if directory.exists() else []
        files = [f for f in files if f.is_file() and f.suffix.lower() in {".pdf", ".txt", ".md"}]

    if not files:
        print(f"No ingestible files found in {args.dir or DEFAULT_DIR}")

    init_db()
    for f in files:
        try:
            ingest(f, defaults, dry_run=args.dry_run)
        except SystemExit as e:
            print(str(e))


if __name__ == "__main__":
    main()
