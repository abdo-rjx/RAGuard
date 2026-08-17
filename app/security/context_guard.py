"""Retrieved-chunk scan (plan Section 9 step 6 / Section 10).

A hit logs INJECTION_SUSPECTED_CONTEXT and the chunk is dropped — retrieved content is
untrusted, and anything that looks like an instruction should not reach the prompt.

Patterns are DB-backed (feature A4): read from guard_patterns via pattern_store.
"""
from app.security.pattern_store import get_compiled


def scan_context(chunk_text: str) -> list[str]:
    """Return the list of patterns that matched in this chunk (empty = clean)."""
    return [p.pattern for p in get_compiled("injection") if p.search(chunk_text)]
