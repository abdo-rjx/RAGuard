"""PolicyEngine — deterministic RBAC+ABAC evaluation (plan Section 7).

Used TWICE on every retrieval:
  1. to build the Chroma `where` filter, and
  2. to re-validate every chunk Chroma returns before it reaches the prompt
     (the defense-in-depth re-check — plan Section 9 step 5).
"""
from functools import lru_cache
from pathlib import Path

import yaml


class PolicyEngine:
    def __init__(self, yaml_path: str | Path):
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._levels: list[str] = data["classification_levels"]
        self._roles: dict[str, dict[str, str]] = data.get("roles", {})
        # level index, lower = more sensitive; PUBLIC is index 0
        self._level_index = {level: i for i, level in enumerate(self._levels)}

    # -- role introspection ---------------------------------------------------

    def roles(self) -> list[str]:
        return list(self._roles.keys())

    def all_classifications(self) -> list[str]:
        return list(self._levels)

    def valid_classification(self, classification: str) -> bool:
        return classification in self._level_index

    def allowed_departments(self, role: str) -> list[str]:
        """Departments this role has any access to (order preserved from YAML)."""
        return list(self._roles.get(role, {}).keys())

    def allowed_classifications(self, role: str, department: str) -> list[str]:
        """Classification levels AT OR BELOW this role's ceiling for this department.
        Returns [] if the role has no access to the department at all."""
        ceiling = self._roles.get(role, {}).get(department)
        if ceiling is None:
            return []
        return [
            level for level in self._levels
            if self._level_index[level] <= self._level_index[ceiling]
        ]

    # -- single yes/no check ---------------------------------------------------

    def can_access_document(self, role: str, department: str, classification: str) -> bool:
        """Deterministic yes/no: does `role` have access to this department/classification?"""
        return classification in self.allowed_classifications(role, department)

    def simulate_access(self, role: str, department: str, classification: str) -> bool:
        """Feature A2 — thin wrapper over can_access_document used by the admin
        "Permission Preview" endpoint. No new logic; exposes the same deterministic
        check so an admin can answer "would user X see document Y?" without logging
        in as that user."""
        return self.can_access_document(role, department, classification)

    # -- Chroma filter ---------------------------------------------------------

    def build_chroma_filter(self, role: str) -> dict:
        """One $and(department, classification IN [...]) clause per accessible department,
        OR'd together. A role with no access anywhere matches nothing."""
        depts = self._roles.get(role, {})
        if not depts:
            return {"department": {"$eq": "__none__"}}  # matches nothing

        clauses = [
            {
                "$and": [
                    {"department": {"$eq": dept}},
                    {"classification": {"$in": self.allowed_classifications(role, dept)}},
                ]
            }
            for dept in depts
        ]
        return clauses[0] if len(clauses) == 1 else {"$or": clauses}


@lru_cache
def get_policy_engine() -> PolicyEngine:
    """Cached singleton, loaded once at startup."""
    from app.config import settings

    return PolicyEngine(settings.POLICY_YAML_PATH)
