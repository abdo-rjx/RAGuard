"""Incoming user-message scan (plan Section 9 step 2 / Section 10).

A match logs INJECTION_SUSPECTED_QUERY but does NOT block the query — the security
guarantee is that the retriever never fetches unauthorized content, not the user's words.

Patterns are DB-backed (feature A4): read from guard_patterns via pattern_store.
"""
from app.security.pattern_store import get_compiled


def scan_query(message: str) -> list[str]:
    """Return the list of patterns that matched (empty = clean)."""
    return [p.pattern for p in get_compiled("injection") if p.search(message)]
