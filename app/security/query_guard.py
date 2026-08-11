"""Incoming user-message scan (plan Section 9 step 2 / Section 10).

A match logs INJECTION_SUSPECTED_QUERY but does NOT block the query — the security
guarantee is that the retriever never fetches unauthorized content, not the user's words.
"""
import re

from app.security.patterns import INJECTION_PATTERNS

_compiled = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def scan_query(message: str) -> list[str]:
    """Return the list of patterns that matched (empty = clean)."""
    return [p.pattern for p in _compiled if p.search(message)]
