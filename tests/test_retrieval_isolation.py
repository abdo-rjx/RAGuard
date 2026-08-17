"""THE critical security test (plan Section 14 / spec Section 47).

Verifies by inspecting the retrieved chunk list itself — not the final answer — that
a document a user is not authorized to see NEVER enters the LLM context, even when
the vector-DB filter leaks everything (FakeVectorStore ignores the `where` clause).
"""
from itertools import product

import pytest

from app.retrieval.secure_retriever import SecureRetriever
from app.models.audit_log import AuditLog

from tests.conftest import FakeVectorStore, make_chunk

DEPARTMENTS = ["finance", "it", "hr", "security", "executive", "general"]
LEVELS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "TOP_SECRET"]


@pytest.fixture()
def leaky_store():
    """One chunk per department × classification — returned unfiltered, simulating a
    broken Chroma filter that hands back everything."""
    chunks = [
        make_chunk(i, dept, level, document_id=i + 1)
        for i, (dept, level) in enumerate(product(DEPARTMENTS, LEVELS))
    ]
    return FakeVectorStore(chunks)


def _retrieve_for_role(monkeypatch, policy_engine, db, store, role):
    monkeypatch.setattr("app.retrieval.secure_retriever.embed_text", lambda text: [0.0] * 384)
    retriever = SecureRetriever(policy_engine, store)
    return retriever.retrieve(
        db,
        user_id=1,
        username=f"{role}_user",
        role=role,
        message="show me everything",
        n_results=100,  # ask for more than exist → fake store returns all
    )


def test_unauthorized_chunk_never_enters_context(monkeypatch, policy_engine, db_session_factory, leaky_store):
    """The plan's headline test: accountant asking for everything must never see IT."""
    db = db_session_factory()
    try:
        result = _retrieve_for_role(monkeypatch, policy_engine, db, leaky_store, "accountant")

        returned_ids = {c.id for c in result.chunks}
        it_chunk_ids = {
            c.id for c in leaky_store._chunks
            if c.department == "it"
        }

        assert not (returned_ids & it_chunk_ids), (
            "IT chunks entered the context — isolation guarantee violated!"
        )

        # and every chunk that WAS returned must be one the role may access
        for chunk in result.chunks:
            assert policy_engine.can_access_document(
                "accountant", chunk.department, chunk.classification
            ), f"accountant leaked {chunk.department}/{chunk.classification}"
    finally:
        db.close()


def test_full_isolation_matrix(monkeypatch, policy_engine, db_session_factory, leaky_store):
    """Every role: nothing unauthorized survives; everything disallowed is dropped by
    the re-check (the defense-in-depth path), not silently absent."""
    db = db_session_factory()
    try:
        for role in policy_engine.roles():
            result = _retrieve_for_role(monkeypatch, policy_engine, db, leaky_store, role)

            returned = {c.id for c in result.chunks}
            rechecked = {c.id for c in result.dropped_by_recheck}
            all_chunks = {c.id for c in leaky_store._chunks}

            for chunk in leaky_store._chunks:
                allowed = policy_engine.can_access_document(role, chunk.department, chunk.classification)
                if allowed:
                    # authorized chunks may be returned
                    assert chunk.id not in rechecked, f"{role}: authorized {chunk.department}/{chunk.classification} was dropped"
                else:
                    # unauthorized chunks MUST be dropped by the re-check, never returned
                    assert chunk.id not in returned, f"{role} leaked {chunk.department}/{chunk.classification}"
                    assert chunk.id in rechecked, f"{role}: {chunk.department}/{chunk.classification} not routed through re-check"

            # everything in candidates is either returned or dropped — nothing vanishes silently
            assert returned | rechecked == all_chunks
    finally:
        db.close()


def test_role_specific_isolations(monkeypatch, policy_engine, db_session_factory, leaky_store):
    """A few concrete spec-derived assertions: engineer vs finance, employee vs everything."""
    db = db_session_factory()
    try:
        cases = [
            ("it_engineer", "finance", False),   # IT engineer must never see finance
            ("it_engineer", "it", True),
            ("hr_manager", "it", False),
            ("hr_manager", "hr", True),
            ("employee", "general", True),
            ("employee", "finance", False),
            ("employee", "executive", False),
            ("security_engineer", "security", True),
            ("security_engineer", "hr", False),
            ("cfo", "finance", True),
            ("cfo", "security", False),
            ("cfo", "general", True),    # public dept is visible to every role
            ("ceo", "executive", True),
            ("ceo", "general", True),   # ceo sees everything, incl. public general docs
        ]
        for role, dept, expect_present in cases:
            result = _retrieve_for_role(monkeypatch, policy_engine, db, leaky_store, role)
            dept_ids = {c.id for c in result.chunks if c.department == dept}
            if expect_present:
                assert dept_ids, f"{role} expected to see {dept} but saw none"
            else:
                assert not dept_ids, f"{role} should NOT see {dept} but got {len(dept_ids)} chunks"
    finally:
        db.close()


def test_recheck_failure_is_audited(monkeypatch, policy_engine, db_session_factory, leaky_store):
    """Every dropped chunk produces an ACCESS_DENIED audit row."""
    db = db_session_factory()
    try:
        _retrieve_for_role(monkeypatch, policy_engine, db, leaky_store, "accountant")
        denied = db.query(AuditLog).filter(AuditLog.action == "ACCESS_DENIED").count()
        # accountant's ceiling is finance/CONFIDENTIAL + general/PUBLIC → denied on
        # finance/RESTRICTED, finance/TOP_SECRET (2) + general/INTERNAL..TOP_SECRET (4)
        # + all 5 levels × 4 other departments (it, hr, security, executive = 20) = 26
        assert denied == 26
    finally:
        db.close()
