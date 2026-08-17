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
    assert body["is_system_admin"] is False
    assert body["is_security_admin"] is False


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


def test_admin_flags_split(client, login):
    """Feature A1 — ceo01 is a System Admin (configures), seceng01 is a Security
    Admin (reads audit content). No single demo account holds both powers."""
    ceo = client.get("/auth/me", headers={"Authorization": f"Bearer {login('ceo01')}"}).json()
    assert ceo["is_system_admin"] is True
    assert ceo["is_security_admin"] is False

    sec = client.get("/auth/me", headers={"Authorization": f"Bearer {login('seceng01')}"}).json()
    assert sec["is_system_admin"] is False
    assert sec["is_security_admin"] is True


# ---- DB is the source of truth on every request (not the token) ------------

def test_deactivated_user_loses_access_immediately(client, login, db_session_factory):
    """A token minted before deactivation must stop working right away."""
    token = login("accountant01")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    db = db_session_factory()
    try:
        from app.models.user import User

        user = db.query(User).filter(User.username == "accountant01").first()
        user.is_active = False
        db.commit()
    finally:
        db.close()

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_deleted_user_loses_access_immediately(client, login, db_session_factory):
    token = login("accountant01")
    db = db_session_factory()
    try:
        from app.models.user import User

        user = db.query(User).filter(User.username == "accountant01").first()
        db.delete(user)
        db.commit()
    finally:
        db.close()

    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_role_change_takes_effect_immediately(client, login, db_session_factory):
    """Demote accountant01 → employee; the next request must see the new role."""
    token = login("accountant01")
    body = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert body["role"] == "accountant"

    db = db_session_factory()
    try:
        from app.models.user import Role, User

        user = db.query(User).filter(User.username == "accountant01").first()
        employee_role = db.query(Role).filter(Role.name == "employee").first()
        user.role_id = employee_role.id
        db.commit()
    finally:
        db.close()

    body = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert body["role"] == "employee"
