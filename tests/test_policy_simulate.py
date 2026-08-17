"""Feature A2 — Permission Preview: GET /policy/simulate + PolicyEngine.simulate_access."""


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _simulate(client, token, role, department, classification):
    return client.get(
        "/policy/simulate",
        params={"role": role, "department": department, "classification": classification},
        headers=_auth(token),
    )


def test_simulate_allows(client, login):
    token = login("ceo01")  # system admin
    r = _simulate(client, token, "accountant", "finance", "CONFIDENTIAL")
    assert r.status_code == 200
    assert r.json()["decision"] == "ALLOW"


def test_simulate_denies(client, login):
    token = login("ceo01")
    r = _simulate(client, token, "accountant", "it", "INTERNAL")
    assert r.status_code == 200
    assert r.json()["decision"] == "DENY"


def test_simulate_unknown_role_denies(client, login):
    token = login("ceo01")
    r = _simulate(client, token, "ghost", "finance", "PUBLIC")
    assert r.status_code == 200
    assert r.json()["decision"] == "DENY"


def test_simulate_invalid_classification(client, login):
    token = login("ceo01")
    r = _simulate(client, token, "ceo", "it", "MEGA_SECRET")
    assert r.status_code == 400


def test_simulate_requires_system_admin(client, login):
    token = login("cfo01")
    assert _simulate(client, token, "ceo", "it", "TOP_SECRET").status_code == 403


def test_simulate_access_matches_can_access(policy_engine):
    """The wrapper exposes exactly the same deterministic check."""
    for role in policy_engine.roles():
        for dept in ["finance", "it", "hr", "security", "executive", "general"]:
            for level in policy_engine.all_classifications():
                assert policy_engine.simulate_access(role, dept, level) == policy_engine.can_access_document(role, dept, level)
