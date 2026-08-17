"""Shared test fixtures. Tests run against a throwaway SQLite DB + a fake vector
store so the isolation guarantee is verified without the embedding model or Chroma.
"""
import os
import tempfile

# MUST be set before app.config is imported so pydantic-settings picks these up
# over the real .env.
#
# Guard against double import: pytest loads this file both as its `conftest`
# plugin AND as `tests.conftest` whenever a test does `from tests.conftest
# import ...`. Without the guard, the second import re-runs the setup below and
# clobbers DATABASE_URL with a fresh temp dir, silently splitting the app engine
# (settings, first dir) from the fixture engines (second dir).
if os.environ.get("RAGGUARD_TEST_DIR"):
    _TEST_DIR = os.environ["RAGGUARD_TEST_DIR"]
else:
    _TEST_DIR = tempfile.mkdtemp(prefix="ragguard_test_")
    os.environ["RAGGUARD_TEST_DIR"] = _TEST_DIR
    os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR}/test.db"
    os.environ["CHROMA_PERSIST_DIR"] = os.path.join(_TEST_DIR, "chroma")
    os.environ["ENVIRONMENT"] = "test"  # Disable rate limiter during tests
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-hermetic-not-production"  # hermetic tests

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.auth.password import hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import Department, Role, User  # noqa: E402
from app.policy.policy_engine import get_policy_engine  # noqa: E402
from app.retrieval.vector_store import RetrievedChunk  # noqa: E402

DEPARTMENTS = ["finance", "it", "hr", "security", "executive", "general"]
ROLES = ["ceo", "cfo", "cto", "hr_manager", "security_engineer", "it_engineer", "accountant", "employee"]

# username → (role, home department, is_system_admin, is_security_admin)
USERS = {
    "ceo01": ("ceo", "executive", True, False),
    "cfo01": ("cfo", "finance", False, False),
    "cto01": ("cto", "it", False, False),
    "hr01": ("hr_manager", "hr", False, False),
    "seceng01": ("security_engineer", "security", False, True),
    "iteng01": ("it_engineer", "it", False, False),
    "accountant01": ("accountant", "finance", False, False),
    "employee01": ("employee", "general", False, False),
}

DEMO_PASSWORD = "Password123!"


def _seed(session) -> None:
    for n in DEPARTMENTS:
        session.add(Department(name=n))
    for n in ROLES:
        session.add(Role(name=n))
    session.commit()
    roles = {r.name: r for r in session.query(Role).all()}
    depts = {d.name: d for d in session.query(Department).all()}
    for username, (role_name, dept_name, is_system_admin, is_security_admin) in USERS.items():
        session.add(
            User(
                username=username,
                hashed_password=hash_password(DEMO_PASSWORD),
                role_id=roles[role_name].id,
                department_id=depts[dept_name].id,
                is_system_admin=is_system_admin,
                is_security_admin=is_security_admin,
                is_active=True,
            )
        )
    session.commit()


@pytest.fixture(scope="session")
def policy_engine():
    return get_policy_engine()


@pytest.fixture()
def db_session_factory():
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    _seed(db)
    db.close()
    yield Session
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session_factory):
    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def login(client):
    def _login(username: str, password: str = DEMO_PASSWORD) -> str:
        r = client.post("/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, r.text
        return r.json()["access_token"]

    return _login


class FakeVectorStore:
    """Returns every seeded chunk regardless of the `where` filter — simulates a
    broken/leaky Chroma filter so the defense-in-depth re-check is the real gate.
    """

    def __init__(self, chunks: list[RetrievedChunk]):
        self._chunks = chunks

    def query(self, embedding, where=None, n_results: int = 5):
        return self._chunks[:n_results]


def make_chunk(index: int, department: str, classification: str, document_id: int = 1) -> RetrievedChunk:
    return RetrievedChunk(
        id=f"c{index}",
        document_id=document_id,
        department=department,
        classification=classification,
        source_filename=f"doc{document_id}-{department}.txt",
        text=f"chunk {index} content from {department}/{classification}",
    )
