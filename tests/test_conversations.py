"""Feature B1 — multi-turn conversations.

POST /chat creates a Conversation on first turn and returns its id; a follow-up
with conversation_id continues the thread and prior turns are included in the
LLM prompt. Conversations are strictly scoped to their owner.
"""
from app.models.feature_models import Conversation, Message
from app.retrieval.secure_retriever import SecureRetriever
from app.routers.chat_router import PROMPT_TEMPLATE

from tests.conftest import FakeVectorStore, make_chunk


def _patch_retrieval(monkeypatch, policy_engine):
    monkeypatch.setattr("app.retrieval.secure_retriever.embed_text", lambda text: [0.0] * 384)
    monkeypatch.setattr(
        "app.retrieval.secure_retriever._retriever",
        SecureRetriever(policy_engine, FakeVectorStore([make_chunk(1, "finance", "CONFIDENTIAL", 101)])),
    )


def _patch_llm(monkeypatch, captured=None):
    def fake(system_prompt, user_prompt):
        if captured is not None:
            captured.append(user_prompt)
        return iter(["48.2 million."])

    monkeypatch.setattr("app.routers.chat_router.stream_chat", fake)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_chat_creates_conversation(monkeypatch, client, login, policy_engine, db_session_factory):
    _patch_retrieval(monkeypatch, policy_engine)
    _patch_llm(monkeypatch)
    token = login("accountant01")

    r = client.post("/chat", headers=_auth(token), json={"message": "What was revenue?"})
    assert r.status_code == 200
    conv_id = r.json()["conversation_id"]
    assert conv_id is not None

    db = db_session_factory()
    try:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        assert conv is not None
        assert conv.user_id is not None
        msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.id).all()
        assert [m.role for m in msgs] == ["user", "assistant"]
        assert msgs[0].content == "What was revenue?"
        assert msgs[1].sources_json  # sources persisted with the assistant message
    finally:
        db.close()


def test_followup_continues_same_conversation(monkeypatch, client, login, policy_engine, db_session_factory):
    _patch_retrieval(monkeypatch, policy_engine)
    _patch_llm(monkeypatch)
    token = login("accountant01")
    h = _auth(token)

    conv_id = client.post("/chat", headers=h, json={"message": "first question"}).json()["conversation_id"]
    r = client.post("/chat", headers=h, json={"message": "follow up", "conversation_id": conv_id})
    assert r.status_code == 200
    assert r.json()["conversation_id"] == conv_id

    db = db_session_factory()
    try:
        assert db.query(Message).filter(Message.conversation_id == conv_id).count() == 4
    finally:
        db.close()


def test_history_included_in_prompt(monkeypatch, client, login, policy_engine):
    _patch_retrieval(monkeypatch, policy_engine)
    captured = []
    _patch_llm(monkeypatch, captured)
    token = login("accountant01")
    h = _auth(token)

    conv_id = client.post("/chat", headers=h, json={"message": "hello there"}).json()["conversation_id"]
    client.post("/chat", headers=h, json={"message": "and again", "conversation_id": conv_id})

    # The second prompt must include the first turn's user message as history.
    prompt = captured[-1]
    assert "hello there" in prompt
    assert "CONVERSATION_HISTORY" in prompt


def test_conversation_ownership_enforced(monkeypatch, client, login, policy_engine):
    _patch_retrieval(monkeypatch, policy_engine)
    _patch_llm(monkeypatch)

    accountant = login("accountant01")
    conv_id = client.post("/chat", headers=_auth(accountant), json={"message": "private"}).json()["conversation_id"]

    # cfo01 must not be able to continue or read accountant01's thread.
    cfo = login("cfo01")
    r = client.post("/chat", headers=_auth(cfo), json={"message": "snoop", "conversation_id": conv_id})
    assert r.status_code == 404
    assert client.get(f"/conversations/{conv_id}", headers=_auth(cfo)).status_code == 404


def test_list_conversations_own_only(monkeypatch, client, login, policy_engine):
    _patch_retrieval(monkeypatch, policy_engine)
    _patch_llm(monkeypatch)

    accountant = login("accountant01")
    cfo = login("cfo01")
    client.post("/chat", headers=_auth(accountant), json={"message": "a1"})
    client.post("/chat", headers=_auth(accountant), json={"message": "a2"})
    client.post("/chat", headers=_auth(cfo), json={"message": "c1"})

    mine = client.get("/conversations", headers=_auth(accountant)).json()
    theirs = client.get("/conversations", headers=_auth(cfo)).json()
    assert len(mine) == 2
    assert len(theirs) == 1


def test_get_conversation_messages(monkeypatch, client, login, policy_engine):
    _patch_retrieval(monkeypatch, policy_engine)
    _patch_llm(monkeypatch)
    token = login("accountant01")
    h = _auth(token)

    conv_id = client.post("/chat", headers=h, json={"message": "what is revenue?"}).json()["conversation_id"]
    msgs = client.get(f"/conversations/{conv_id}", headers=h).json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "48.2 million."
