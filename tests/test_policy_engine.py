"""Policy engine tests — every role × department from plan Section 7's table."""
import pytest

# (role, department, max_classification) — the plan Section 7 table verbatim.
# Absent = no access at all.
ROLE_DEPT_CEILINGS = [
    ("ceo", "finance", "TOP_SECRET"),
    ("ceo", "it", "TOP_SECRET"),
    ("ceo", "hr", "TOP_SECRET"),
    ("ceo", "security", "TOP_SECRET"),
    ("ceo", "executive", "TOP_SECRET"),
    ("cfo", "finance", "CONFIDENTIAL"),
    ("cfo", "hr", "INTERNAL"),
    ("cfo", "executive", "INTERNAL"),
    ("cto", "it", "CONFIDENTIAL"),
    ("cto", "security", "INTERNAL"),
    ("cto", "executive", "INTERNAL"),
    ("hr_manager", "hr", "CONFIDENTIAL"),
    ("security_engineer", "security", "RESTRICTED"),
    ("it_engineer", "it", "INTERNAL"),
    ("accountant", "finance", "CONFIDENTIAL"),
    ("employee", "general", "PUBLIC"),
]

ALL_DEPARTMENTS = ["finance", "it", "hr", "security", "executive", "general"]
LEVELS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "TOP_SECRET"]

# plan Section 14's spot checks, exactly as written
SPEC_SPOT_CHECKS = [
    ("accountant", "finance", "CONFIDENTIAL", True),
    ("accountant", "it", "INTERNAL", False),
    ("it_engineer", "it", "INTERNAL", True),
    ("ceo", "it", "TOP_SECRET", True),
]


def test_roles_match_plan():
    assert sorted(policy_engine_roles()) == sorted(
        ["ceo", "cfo", "cto", "hr_manager", "security_engineer", "it_engineer", "accountant", "employee"]
    )


def policy_engine_roles():
    import app.policy.policy_engine as pe
    return list(pe.get_policy_engine().roles())


@pytest.fixture(scope="module")
def engine():
    from app.policy.policy_engine import get_policy_engine
    return get_policy_engine()


def test_spec_spot_checks(engine):
    for role, dept, classification, expected in SPEC_SPOT_CHECKS:
        assert engine.can_access_document(role, dept, classification) is expected, (
            f"{role}→{dept}/{classification} expected {expected}"
        )


def test_ceiling_allows_below_not_above(engine):
    # At-or-below ceiling is allowed; strictly above is denied.
    assert engine.can_access_document("cfo", "finance", "CONFIDENTIAL")
    assert engine.can_access_document("cfo", "finance", "INTERNAL")
    assert engine.can_access_document("cfo", "finance", "PUBLIC")
    assert not engine.can_access_document("cfo", "finance", "RESTRICTED")
    assert not engine.can_access_document("cfo", "finance", "TOP_SECRET")


def test_absent_department_is_denied(engine):
    assert not engine.can_access_document("accountant", "it", "PUBLIC")
    assert not engine.can_access_document("hr_manager", "finance", "PUBLIC")
    assert not engine.can_access_document("employee", "finance", "PUBLIC")
    assert not engine.can_access_document("employee", "it", "PUBLIC")


def test_full_matrix(engine):
    """Every role × department × classification from the plan's table."""
    for role, dept, ceiling in ROLE_DEPT_CEILINGS:
        for level in LEVELS:
            expected = LEVELS.index(level) <= LEVELS.index(ceiling)
            assert engine.can_access_document(role, dept, level) is expected, (
                f"{role}→{dept}/{level} expected {expected}"
            )


def test_every_other_department_denied(engine):
    """A department not in a role's entry must be inaccessible at every level."""
    allowed_by_role = {}
    for role, dept, _ in ROLE_DEPT_CEILINGS:
        allowed_by_role.setdefault(role, set()).add(dept)
    for role in engine.roles():
        for dept in ALL_DEPARTMENTS:
            if dept in allowed_by_role.get(role, set()):
                continue
            for level in LEVELS:
                assert not engine.can_access_document(role, dept, level), (
                    f"{role} should have NO access to {dept}/{level}"
                )


def test_allowed_classifications_order(engine):
    assert engine.allowed_classifications("cfo", "finance") == ["PUBLIC", "INTERNAL", "CONFIDENTIAL"]
    assert engine.allowed_classifications("accountant", "it") == []
    assert engine.allowed_classifications("ceo", "executive") == LEVELS


def test_build_chroma_filter(engine):
    # accountant → single department clause with classification IN [...]
    f = engine.build_chroma_filter("accountant")
    assert f == {
        "$and": [
            {"department": {"$eq": "finance"}},
            {"classification": {"$in": ["PUBLIC", "INTERNAL", "CONFIDENTIAL"]}},
        ]
    }

    # cfo → OR of three department clauses
    f = engine.build_chroma_filter("cfo")
    assert "$or" in f
    assert len(f["$or"]) == 3
    finance_clause = next(c for c in f["$or"] if c["$and"][0]["department"]["$eq"] == "finance")
    assert finance_clause["$and"][1]["classification"]["$in"] == ["PUBLIC", "INTERNAL", "CONFIDENTIAL"]

    # unknown role → matches nothing
    f = engine.build_chroma_filter("ghost")
    assert f == {"department": {"$eq": "__none__"}}
