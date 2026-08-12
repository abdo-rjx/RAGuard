"""Rate limiting is the one control the rest of the suite runs with disabled
(ENVIRONMENT=test). These tests pin the two properties that matter:
the toggle really disables it, and enabling it blocks brute-forcing /auth/login.
"""
from app.main import app


def test_limiter_disabled_in_test_env():
    # ENVIRONMENT=test must disable enforcement; otherwise every test that
    # hits /auth/login more than `10/minute` times would spuriously 429.
    assert app.state.limiter.enabled is False


def test_login_rate_limited_when_enabled(client):
    limiter = app.state.limiter
    limiter.enabled = True
    try:
        for _ in range(10):
            r = client.post("/auth/login", json={"username": "ceo01", "password": "wrong"})
            assert r.status_code == 401
        # 11th attempt inside the same window -> brute-force protection kicks in
        r = client.post("/auth/login", json={"username": "ceo01", "password": "wrong"})
        assert r.status_code == 429
    finally:
        limiter.enabled = False
