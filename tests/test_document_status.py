"""Feature A3 — GET /documents/{id}/status: ingestion state, chunk count, chunk ids."""
from app.models.document import Document
from app.models.user import Department


def _add_doc(db, filename, department_name, classification, status="success", error=None):
    dept = db.query(Department).filter(Department.name == department_name).first()
    doc = Document(
        filename=filename,
        department_id=dept.id,
        classification=classification,
        chroma_chunk_ids=[f"c-{i}" for i in range(3)] if status == "success" else [],
        ingestion_status=status,
        ingestion_error=error,
    )
    db.add(doc)
    db.commit()
    return doc


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_status_success(client, login, db_session_factory):
    db = db_session_factory()
    try:
        doc = _add_doc(db, "revenue.txt", "finance", "CONFIDENTIAL")
        doc_id = doc.id
    finally:
        db.close()

    r = client.get(f"/documents/{doc_id}/status", headers=_auth(login("cfo01")))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["chunk_count"] == 3
    assert len(body["chroma_chunk_ids"]) == 3
    assert body["error"] is None


def test_status_failed_records_reason(client, login, db_session_factory):
    db = db_session_factory()
    try:
        doc = _add_doc(db, "broken.pdf", "it", "INTERNAL", status="failed", error="embedding model unavailable")
        doc_id = doc.id
    finally:
        db.close()

    r = client.get(f"/documents/{doc_id}/status", headers=_auth(login("ceo01")))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert "unavailable" in (body["error"] or "")


def test_status_hides_docs_above_ceiling(client, login, db_session_factory):
    """Same policy as the listing: an IT doc must 404 for cfo01, not reveal existence."""
    db = db_session_factory()
    try:
        doc = _add_doc(db, "network.txt", "it", "INTERNAL")
        doc_id = doc.id
    finally:
        db.close()

    r = client.get(f"/documents/{doc_id}/status", headers=_auth(login("cfo01")))
    assert r.status_code == 404

    # ceo sees everything.
    assert client.get(f"/documents/{doc_id}/status", headers=_auth(login("ceo01"))).status_code == 200


def test_status_requires_auth(client):
    assert client.get("/documents/1/status").status_code == 401
