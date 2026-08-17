"""Feature A1 — separation of duties: System Admin vs Security Admin.

/audit/logs requires is_security_admin; /policy/simulate requires is_system_admin.
No demo account holds both powers.
"""


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_system_admin_cannot_read_audit(client, login):
    """ceo01 configures the system but must NOT read sensitive audit content."""
    token = login("ceo01")
    r = client.get("/audit/logs", headers=_auth(token))
    assert r.status_code == 403

    # ...but CAN use the policy simulation endpoint.
    r = client.get(
        "/policy/simulate",
        params={"role": "accountant", "department": "finance", "classification": "CONFIDENTIAL"},
        headers=_auth(token),
    )
    assert r.status_code == 200


def test_security_admin_cannot_configure_policy(client, login):
    """seceng01 reads audit content but has no system-configuration rights."""
    token = login("seceng01")
    r = client.get("/audit/logs", headers=_auth(token))
    assert r.status_code == 200

    r = client.get(
        "/policy/simulate",
        params={"role": "accountant", "department": "finance", "classification": "CONFIDENTIAL"},
        headers=_auth(token),
    )
    assert r.status_code == 403


def test_regular_user_denied_both(client, login):
    token = login("accountant01")
    assert client.get("/audit/logs", headers=_auth(token)).status_code == 403
    assert client.get("/policy/simulate", params={"role": "ceo", "department": "it", "classification": "TOP_SECRET"}, headers=_auth(token)).status_code == 403


def test_guard_patterns_require_system_admin(client, login):
    """Feature A4 config work is system-admin territory — security admin is 403."""
    sec = login("seceng01")
    assert client.get("/security/patterns", headers=_auth(sec)).status_code == 403

    sys = login("ceo01")
    assert client.get("/security/patterns", headers=_auth(sys)).status_code == 200


def test_alerts_and_reports_require_security_admin(client, login):
    """Feature A5/A6 views are security-admin territory — system admin is 403."""
    sys = login("ceo01")
    assert client.get("/security/alerts", headers=_auth(sys)).status_code == 403
    assert client.get("/security/reports", headers=_auth(sys)).status_code == 403

    sec = login("seceng01")
    assert client.get("/security/alerts", headers=_auth(sec)).status_code == 200
    assert client.get("/security/reports", headers=_auth(sec)).status_code == 200
