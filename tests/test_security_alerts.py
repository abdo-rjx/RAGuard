"""Feature A5 — non-ML anomaly flagging: >5 denied/injection-suspected events for
one user within 10 minutes writes a SecurityAlert (\"needs review\")."""
from app.audit.logger import write_audit_event
from app.models.audit_log import AuditLog
from app.models.feature_models import SecurityAlert


def _fire_denied(db, user_id, username, count):
    for i in range(count):
        write_audit_event(
            db,
            action="ACCESS_DENIED",
            user_id=user_id,
            username=username,
            role="accountant",
            query_text=f"probe {i}",
            decision="DENY",
            reason="recheck_failed",
        )


def test_no_alert_below_threshold(db_session_factory):
    db = db_session_factory()
    try:
        _fire_denied(db, 1, "accountant01", 5)  # exactly 5 → not more than 5
        assert db.query(SecurityAlert).count() == 0
    finally:
        db.close()


def test_alert_when_threshold_crossed(db_session_factory):
    db = db_session_factory()
    try:
        _fire_denied(db, 1, "accountant01", 6)
        alerts = db.query(SecurityAlert).all()
        assert len(alerts) == 1
        assert alerts[0].user_id == 1
        assert alerts[0].username == "accountant01"
        assert alerts[0].event_action == "ACCESS_DENIED"
        assert alerts[0].event_count > 5
    finally:
        db.close()


def test_alert_deduped_within_window(db_session_factory):
    db = db_session_factory()
    try:
        _fire_denied(db, 1, "accountant01", 12)  # keeps tripping
        assert db.query(SecurityAlert).count() == 1  # one flag, not one per event
    finally:
        db.close()


def test_injection_events_also_count(db_session_factory):
    db = db_session_factory()
    try:
        for i in range(6):
            write_audit_event(
                db,
                action="INJECTION_SUSPECTED_QUERY",
                user_id=2,
                username="cfo01",
                role="cfo",
                query_text=f"inject {i}",
                decision="ALLOW",
            )
        assert db.query(SecurityAlert).count() == 1
        assert db.query(SecurityAlert).first().username == "cfo01"
    finally:
        db.close()


def test_benign_actions_do_not_alert(db_session_factory):
    db = db_session_factory()
    try:
        for i in range(20):
            write_audit_event(db, action="CHAT_QUERY", user_id=1, username="accountant01", query_text=f"q{i}")
        assert db.query(SecurityAlert).count() == 0
    finally:
        db.close()


def test_alerts_endpoint_lists_flags(client, login, db_session_factory):
    db = db_session_factory()
    try:
        _fire_denied(db, 1, "accountant01", 6)
    finally:
        db.close()

    r = client.get("/security/alerts", headers={"Authorization": f"Bearer {login('seceng01')}"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["username"] == "accountant01"
    assert body[0]["event_count"] > 5


def test_anomaly_rows_still_audited(db_session_factory):
    """The flagged user's events themselves remain in the audit log (A5 adds, never removes)."""
    db = db_session_factory()
    try:
        _fire_denied(db, 1, "accountant01", 6)
        denied = db.query(AuditLog).filter(AuditLog.action == "ACCESS_DENIED").count()
        assert denied == 6
    finally:
        db.close()
