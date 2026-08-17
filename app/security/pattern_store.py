"""DB-backed guard patterns with in-memory caching (feature A4).

Guards no longer import a static regex list. Instead they ask this store for
compiled patterns of a given type. The store:

  * loads ACTIVE patterns of that type from the `guard_patterns` table,
  * falls back to the built-in defaults when the table is empty or the DB is
    unavailable (keeps the pure guard functions testable without a DB),
  * caches compiled patterns in memory; any pattern mutation (CRUD endpoint)
    calls `refresh_pattern_cache()` so changes take effect immediately.
"""
import re
from typing import Optional

from app.database import SessionLocal
from app.models.feature_models import GuardPattern
from app.security.patterns import INJECTION_PATTERNS, LEAK_PATTERNS

DEFAULT_PATTERNS = {"injection": INJECTION_PATTERNS, "leak": LEAK_PATTERNS}

# type → list[re.Pattern] | None (None = not yet loaded)
_compiled_cache: dict[str, Optional[list[re.Pattern]]] = {"injection": None, "leak": None}


def _load_compiled(pattern_type: str) -> list[re.Pattern]:
    """Load active patterns of one type from the DB; fall back to defaults."""
    try:
        db = SessionLocal()
        try:
            rows = (
                db.query(GuardPattern)
                .filter(GuardPattern.type == pattern_type, GuardPattern.active.is_(True))
                .all()
            )
            raw = [r.pattern for r in rows]
        finally:
            db.close()
    except Exception:
        raw = []

    if not raw:
        raw = DEFAULT_PATTERNS[pattern_type]
    return [re.compile(p, re.IGNORECASE) for p in raw]


def get_compiled(pattern_type: str) -> list[re.Pattern]:
    """Compiled active patterns for a type, cached after first load."""
    if _compiled_cache[pattern_type] is None:
        _compiled_cache[pattern_type] = _load_compiled(pattern_type)
    return _compiled_cache[pattern_type]


def refresh_pattern_cache() -> None:
    """Drop the cache so the next scan re-reads the DB (call after any CRUD change)."""
    _compiled_cache["injection"] = None
    _compiled_cache["leak"] = None


def seed_default_patterns(db) -> int:
    """Insert the default patterns if the table is empty. Returns count inserted.
    Called at app startup (and safe to call from tests)."""
    count = db.query(GuardPattern).count()
    if count:
        return 0
    for pattern_type, defaults in DEFAULT_PATTERNS.items():
        for p in defaults:
            db.add(GuardPattern(pattern=p, type=pattern_type, active=True))
    db.commit()
    refresh_pattern_cache()
    return len(INJECTION_PATTERNS) + len(LEAK_PATTERNS)
