"""Auth endpoint tests (plan Phase 1 DoD)."""
from app.auth.jwt_handler import create_access_token
from app.schemas.auth import LoginResponse

DEMO_PASSWORD = "Password123!"


def test_login_success(client, login):
    token = login("accountant01")
    assert token

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "accountant01"
    assert body["role"] == "accountant"
    assert body["department"] == "finance"
    assert body["is_admin"] is False


def test_login_response_contract(client, login):
    r = client.post("/auth/login", json={"username": "accountant01", "password": DEMO_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["role"] == "accountant"
    assert body["department"] == "finance"


def test_login_wrong_password(client):
    r = client.post("/auth/login", json={"username": "accountant01", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/auth/login", json={"username": "nobody", "password": DEMO_PASSWORD})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_garbage_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


def test_me_rejects_expired_token(client):
    token = create_access_token(
        {"user_id": 1, "username": "accountant01", "role": "accountant", "department": "finance"},
        expires_minutes=-1,
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_admin_sees_admin_flag(client, login):
    body = client.get("/auth/me", headers={"Authorization": f"Bearer {login('ceo01')}"}).json()
    assert body["is_admin"] is True
