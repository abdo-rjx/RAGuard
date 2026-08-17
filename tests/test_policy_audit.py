"""Policy completeness audit — fails loudly if departments go missing.

Regression guard for the bug where `ceo` was missing the `general` department
in policies.yaml: a department absent from a role's entry means ZERO access,
so documents in it are silently invisible (retrieval never even searches it).

These tests treat `scripts/seed_data.py` DEPARTMENTS as the source of truth
for which departments exist in the system.
"""
from scripts.seed_data import DEPARTMENTS


def test_every_system_department_is_covered(policy_engine):
    """Every department that exists in the system must be reachable by at least
    one role — otherwise its documents can never be retrieved by anyone."""
    covered = set()
    for role in policy_engine.roles():
        covered |= set(policy_engine.allowed_departments(role))
    missing = set(DEPARTMENTS) - covered
    assert not missing, (
        f"Departments missing from policies.yaml: {sorted(missing)}. "
        "A department absent from every role means zero access — its documents "
        "are silently unreachable. Add it to app/policy/policies.yaml."
    )


def test_policy_does_not_reference_unknown_departments(policy_engine):
    """Catch typos in the YAML — a role referencing a nonexistent department is
    dead config that silently matches nothing."""
    unknown = set()
    for role in policy_engine.roles():
        unknown |= set(policy_engine.allowed_departments(role)) - set(DEPARTMENTS)
    assert not unknown, (
        f"policies.yaml references unknown departments: {sorted(unknown)}. "
        f"Known departments: {sorted(DEPARTMENTS)}."
    )


def test_ceo_covers_every_department(policy_engine):
    """The README's 'CEO sees everything (TOP_SECRET)' claim must stay true."""
    missing = set(DEPARTMENTS) - set(policy_engine.allowed_departments("ceo"))
    assert not missing, (
        f"ceo is missing departments in policies.yaml: {sorted(missing)}. "
        "The CEO is documented as seeing everything — add the missing "
        "department to the ceo entry."
    )


def test_every_role_has_at_least_one_department(policy_engine):
    """A role with no departments anywhere is either a typo or should be removed."""
    empty = [r for r in policy_engine.roles() if not policy_engine.allowed_departments(r)]
    assert not empty, f"roles with no departments in policies.yaml: {empty}"
