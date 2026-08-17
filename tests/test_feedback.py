"""Feature B3/A6 — feedback: thumbs up/down (CHAT_FEEDBACK) vs a high-priority
\"report as security concern\" (USER_REPORTED_SECURITY_CONCERN), surfaced in a
separate admin security inbox (GET /security/reports)."""
from app.models.audit_log import AuditLog


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_thumbs_up_writes_feedback_audit(client, login, db_session_factory):
    token = login("accountant01")
    r = client.post(
        "/chat/feedback",
        json={"message": "What was revenue?", "feedback": "thumbs_up"},
        headers=_auth(token),
    )
    assert r.status_code == 200

    db = db_session_factory()
    try:
        rows = db.query(AuditLog).filter(AuditLog.action == "CHAT_FEEDBACK").all()
        assert len(rows) == 1
        assert rows[0].username == "accountant01"
        assert rows[0].query_text == "What was revenue?"
    finally:
        db.close()


def test_security_concern_writes_high_priority_action(client, login, db_session_factory):
    token = login("accountant01")
    r = client.post(
        "/chat/feedback",
        json={"message": "why can I see salary data", "feedback": "security_concern", "comment": "looks like a prompt injection"},
        headers=_auth(token),
    )
    assert r.status_code == 200

    db = db_session_factory()
    try:
        rows = db.query(AuditLog).filter(AuditLog.action == "USER_REPORTED_SECURITY_CONCERN").all()
        assert len(rows) == 1
        assert rows[0].details_json["feedback"] == "security_concern"
        assert rows[0].reason == "looks like a prompt injection"
    finally:
        db.close()


def test_reports_inbox_separate_from_general_feedback(client, login, db_session_factory):
    token = login("accountant01")
    h = _auth(token)
    client.post("/chat/feedback", json={"message": "q1", "feedback": "thumbs_down"}, headers=h)
    client.post("/chat/feedback", json={"message": "q2", "feedback": "security_concern", "comment": "suspicious"}, headers=h)

    # The security inbox shows ONLY the high-priority concern.
    sec = login("seceng01")
    data = client.get("/security/reports", headers=_auth(sec)).json()
    assert data["total"] == 1
    assert data["items"][0]["query_text"] == "q2"
    assert data["items"][0]["action"] == "USER_REPORTED_SECURITY_CONCERN"


def test_invalid_feedback_rejected(client, login):
    token = login("accountant01")
    r = client.post("/chat/feedback", json={"message": "q", "feedback": "maybe"}, headers=_auth(token))
    assert r.status_code == 422


def test_feedback_requires_auth(client):
    assert client.post("/chat/feedback", json={"message": "q", "feedback": "thumbs_up"}).status_code == 401
