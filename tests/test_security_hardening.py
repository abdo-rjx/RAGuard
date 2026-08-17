"""Security hardening regression tests:
  * upload size cap (memory DoS) → 413
  * security headers on every response
  * JWT revocation on password change (token_version)
  * control-character sanitization in the audit log (log injection)
"""
from app.audit.logger import write_audit_event
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.user import User

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---- upload size limit -------------------------------------------------------

def test_upload_rejects_oversized_file(client, login, db_session_factory):
    """A file over 10 MB is rejected with 413 and leaves no Document row behind."""
    token = login("ceo01")  # system admin
    big = b"x" * (MAX_UPLOAD_BYTES + 1)
    r = client.post(
        "/documents",
        data={"department": "finance", "classification": "INTERNAL"},
        files={"file": ("huge.txt", big, "text/plain")},
        headers=_auth(token),
    )
    assert r.status_code == 413
    assert "too large" in r.json()["detail"].lower()

    db = db_session_factory()
    try:
        assert db.query(Document).count() == 0
    finally:
        db.close()


def test_upload_accepts_below_limit(client, login, db_session_factory):
    """A small file passes the size check (rejected later only by pipeline limits)."""
    token = login("ceo01")
    r = client.post(
        "/documents",
        data={"department": "finance", "classification": "INTERNAL"},
        files={"file": ("tiny.txt", b"hello world", "text/plain")},
        headers=_auth(token),
    )
    # Either 201 (fully ingested, unlikely in tests without the embedding model)
    # or 500 with a marked-failed record — but never 413.
    assert r.status_code != 413


# ---- security headers --------------------------------------------------------

def test_security_headers_present(client):
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]


def test_security_headers_on_api_too(client):
    r = client.post("/chat", json={"message": "hi"})  # 401 but headers still set
    assert r.status_code == 401
    assert r.headers.get("X-Frame-Options") == "DENY"


# ---- token revocation on password change -------------------------------------

def test_old_token_revoked_after_password_change(client, login):
    old_token = login("accountant01")
    assert client.get("/auth/me", headers=_auth(old_token)).status_code == 200

    r = client.post(
        "/auth/me/password",
        json={"current_password": "Password123!", "new_password": "NewPass123!"},
        headers=_auth(old_token),
    )
    assert r.status_code == 204

    # The pre-change token must now be rejected...
    assert client.get("/auth/me", headers=_auth(old_token)).status_code == 401

    # ...while a fresh login works.
    new_token = client.post("/auth/login", json={"username": "accountant01", "password": "NewPass123!"}).json()["access_token"]
    assert client.get("/auth/me", headers=_auth(new_token)).status_code == 200


# ---- log-injection sanitization ---------------------------------------------

def test_audit_log_sanitizes_control_characters(db_session_factory):
    db = db_session_factory()
    try:
        evil = "normal query\nFAKE LOGIN SUCCESS\r\n[attacker]"
        write_audit_event(db, action="CHAT_QUERY", user_id=1, username="accountant01", query_text=evil, decision="ALLOW")
        row = db.query(AuditLog).filter(AuditLog.action == "CHAT_QUERY").first()
        assert "\n" not in (row.query_text or "")
        assert "\r" not in (row.query_text or "")
        # The payload can no longer forge a new log line: it is flattened onto
        # one line with spaces where the control characters were.
        assert " FAKE LOGIN SUCCESS " in (row.query_text or "")
    finally:
        db.close()


def test_audit_log_sanitizes_username(db_session_factory):
    db = db_session_factory()
    try:
        write_audit_event(db, action="LOGIN_FAILED", username="bob\x00\x1f\x7f", reason="invalid_credentials")
        row = db.query(AuditLog).filter(AuditLog.action == "LOGIN_FAILED").first()
        assert row.username is not None
        assert all(ord(c) >= 0x20 and c != "\x7f" for c in row.username)
    finally:
        db.close()
