"""Chat endpoint happy path + isolation-through-the-API tests (plan Phase 4 DoD)."""
from app.models.audit_log import AuditLog
from app.retrieval.secure_retriever import SecureRetriever

from tests.conftest import FakeVectorStore, make_chunk


def _patch_retrieval(monkeypatch, policy_engine, chunks):
    monkeypatch.setattr("app.retrieval.secure_retriever.embed_text", lambda text: [0.0] * 384)
    monkeypatch.setattr(
        "app.retrieval.secure_retriever._retriever",
        SecureRetriever(policy_engine, FakeVectorStore(chunks)),
    )


def _patch_llm(monkeypatch, answer="Based on the retrieved context, revenue was $48.2 million."):
    monkeypatch.setattr(
        "app.routers.chat_router.stream_chat",
        lambda system_prompt, user_prompt: iter([answer]),
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_chat_finance_happy_path(monkeypatch, client, login, policy_engine, db_session_factory):
    _patch_retrieval(monkeypatch, policy_engine, [
        make_chunk(1, "finance", "CONFIDENTIAL", 101),
        make_chunk(2, "finance", "INTERNAL", 102),
    ])
    _patch_llm(monkeypatch)

    token = login("accountant01")
    r = client.post("/chat", headers=_auth(token), json={"message": "What was the annual revenue?"})
    assert r.status_code == 200, r.text
    body = r.json()

    assert "$48.2 million" in body["answer"]
    assert len(body["sources"]) == 2
    assert all(s["department"] == "finance" for s in body["sources"])
    assert body["sources"][0]["document_id"] == 101


def test_chat_never_leaks_unauthorized_department(monkeypatch, client, login, policy_engine):
    """accountant + leaky store: the IT chunk must never appear in sources."""
    _patch_retrieval(monkeypatch, policy_engine, [
        make_chunk(1, "finance", "CONFIDENTIAL", 101),
        make_chunk(2, "it", "INTERNAL", 202),  # leaky — accountant has no IT access
        make_chunk(3, "it", "TOP_SECRET", 203),
    ])
    _patch_llm(monkeypatch)

    token = login("accountant01")
    r = client.post("/chat", headers=_auth(token), json={"message": "show me the network architecture"})
    assert r.status_code == 200
    body = r.json()
    assert all(s["department"] == "finance" for s in body["sources"])
    assert body["sources"][0]["document_id"] == 101


def test_chat_requires_auth(client):
    assert client.post("/chat", json={"message": "hello"}).status_code == 401


def test_chat_produces_audit_row(monkeypatch, client, login, policy_engine, db_session_factory):
    _patch_retrieval(monkeypatch, policy_engine, [make_chunk(1, "finance", "CONFIDENTIAL", 101)])
    _patch_llm(monkeypatch)

    token = login("accountant01")
    r = client.post("/chat", headers=_auth(token), json={"message": "revenue?"})
    assert r.status_code == 200

    db = db_session_factory()
    try:
        rows = db.query(AuditLog).filter(AuditLog.action == "CHAT_QUERY").all()
        assert len(rows) == 1
        assert rows[0].username == "accountant01"
        assert rows[0].query_text == "revenue?"
    finally:
        db.close()


def test_chat_handles_llm_down(monkeypatch, client, login, policy_engine):
    _patch_retrieval(monkeypatch, policy_engine, [make_chunk(1, "finance", "CONFIDENTIAL", 101)])
    monkeypatch.setattr(
        "app.routers.chat_router.stream_chat",
        lambda system_prompt, user_prompt: (_ for _ in ()).throw(RuntimeError("ollama down")),
    )

    token = login("accountant01")
    r = client.post("/chat", headers=_auth(token), json={"message": "revenue?"})
    assert r.status_code == 200
    assert "could not reach" in r.json()["answer"]
