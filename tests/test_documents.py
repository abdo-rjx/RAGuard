"""Document listing must respect the caller's policy ceiling — regression tests
for the fix: list_documents previously filtered by department only, so a user
could see the names/classifications of documents above their ceiling (e.g. a
CFO seeing executive/TOP_SECRET filenames in the list).
"""
from app.models.document import Document
from app.models.user import Department


def _add_doc(db, filename, department_name, classification):
    dept = db.query(Department).filter(Department.name == department_name).first()
    doc = Document(
        filename=filename,
        department_id=dept.id,
        classification=classification,
        chroma_chunk_ids=[],
    )
    db.add(doc)
    db.commit()
    return doc


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _names(body):
    return {d["filename"] for d in body}


def test_list_hides_docs_above_ceiling(client, login, db_session_factory):
    """cfo (finance/CONFIDENTIAL ceiling) must not see finance/TOP_SECRET or IT docs."""
    db = db_session_factory()
    try:
        _add_doc(db, "revenue_internal.txt", "finance", "INTERNAL")
        _add_doc(db, "merger_secret.txt", "finance", "TOP_SECRET")
        _add_doc(db, "it_network.txt", "it", "INTERNAL")
    finally:
        db.close()

    r = client.get("/documents", headers=_auth(login("cfo01")))
    assert r.status_code == 200
    names = _names(r.json())
    assert "revenue_internal.txt" in names       # below ceiling → visible
    assert "merger_secret.txt" not in names      # above ceiling → hidden
    assert "it_network.txt" not in names         # other department → hidden


def test_ceo_sees_everything(client, login, db_session_factory):
    """ceo has TOP_SECRET everywhere (incl. general) → sees all documents."""
    db = db_session_factory()
    try:
        _add_doc(db, "merger_secret.txt", "executive", "TOP_SECRET")
        _add_doc(db, "incident.txt", "security", "RESTRICTED")
        _add_doc(db, "overview.txt", "general", "PUBLIC")
    finally:
        db.close()

    r = client.get("/documents", headers=_auth(login("ceo01")))
    assert r.status_code == 200
    names = _names(r.json())
    assert "merger_secret.txt" in names
    assert "incident.txt" in names
    assert "overview.txt" in names


def test_all_roles_see_public_general_docs(client, login, db_session_factory):
    """general is the PUBLIC department — every role reads general/PUBLIC docs;
    only ceo (TOP_SECRET ceiling) may go above PUBLIC there."""
    db = db_session_factory()
    try:
        _add_doc(db, "overview.txt", "general", "PUBLIC")
        _add_doc(db, "internal_notes.txt", "general", "INTERNAL")
    finally:
        db.close()

    everyone = ["ceo01", "cfo01", "cto01", "hr01", "seceng01", "iteng01", "accountant01", "employee01"]
    for username in everyone:
        r = client.get("/documents", headers=_auth(login(username)))
        assert r.status_code == 200
        assert "overview.txt" in _names(r.json()), f"{username} should see general/PUBLIC docs"

    for username in [u for u in everyone if u != "ceo01"]:
        names = _names(client.get("/documents", headers=_auth(login(username))).json())
        assert "internal_notes.txt" not in names, f"{username} must not see general/INTERNAL"


def test_employee_sees_only_public_general(client, login, db_session_factory):
    """employee (general/PUBLIC only) sees nothing else — not even general/INTERNAL."""
    db = db_session_factory()
    try:
        _add_doc(db, "overview.txt", "general", "PUBLIC")
        _add_doc(db, "internal_notes.txt", "general", "INTERNAL")
        _add_doc(db, "finance_report.txt", "finance", "PUBLIC")
    finally:
        db.close()

    r = client.get("/documents", headers=_auth(login("employee01")))
    assert r.status_code == 200
    names = _names(r.json())
    assert "overview.txt" in names
    assert "internal_notes.txt" not in names
    assert "finance_report.txt" not in names


def test_list_requires_auth(client):
    assert client.get("/documents").status_code == 401
