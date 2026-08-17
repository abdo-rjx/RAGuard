"""Feature B4 — self-service: GET /auth/me/queries (own history only) and
POST /auth/me/password (verify current, then change)."""
from app.retrieval.secure_retriever import SecureRetriever

from tests.conftest import FakeVectorStore, make_chunk


def _patch_retrieval(monkeypatch, policy_engine):
    monkeypatch.setattr("app.retrieval.secure_retriever.embed_text", lambda text: [0.0] * 384)
    monkeypatch.setattr(
        "app.retrieval.secure_retriever._retriever",
        SecureRetriever(policy_engine, FakeVectorStore([make_chunk(1, "finance", "CONFIDENTIAL", 101)])),
    )


def _patch_llm(monkeypatch):
    monkeypatch.setattr("app.routers.chat_router.stream_chat", lambda s, u: iter(["ok"]))


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_own_query_history(monkeypatch, client, login, policy_engine):
    _patch_retrieval(monkeypatch, policy_engine)
    _patch_llm(monkeypatch)

    accountant = login("accountant01")
    cfo = login("cfo01")
    client.post("/chat", headers=_auth(accountant), json={"message": "my private question"})
    client.post("/chat", headers=_auth(cfo), json={"message": "someone else's question"})

    mine = client.get("/auth/me/queries", headers=_auth(accountant)).json()
    assert len(mine) == 1
    assert mine[0]["query_text"] == "my private question"
    # ...and the other user's query is never visible.
    assert all(q["query_text"] != "someone else's question" for q in mine)


def test_change_password_success(client, login, db_session_factory):
    token = login("accountant01")
    r = client.post(
        "/auth/me/password",
        json={"current_password": "Password123!", "new_password": "NewPass123!"},
        headers=_auth(token),
    )
    assert r.status_code == 204

    # Old password no longer works; new one does.
    assert client.post("/auth/login", json={"username": "accountant01", "password": "Password123!"}).status_code == 401
    assert client.post("/auth/login", json={"username": "accountant01", "password": "NewPass123!"}).status_code == 200


def test_change_password_wrong_current(client, login):
    token = login("accountant01")
    r = client.post(
        "/auth/me/password",
        json={"current_password": "wrong", "new_password": "NewPass123!"},
        headers=_auth(token),
    )
    assert r.status_code == 400


def test_change_password_requires_auth(client):
    assert client.post(
        "/auth/me/password", json={"current_password": "x", "new_password": "y"}
    ).status_code == 401
