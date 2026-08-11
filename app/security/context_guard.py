"""Retrieved-chunk scan (plan Section 9 step 6 / Section 10).

A hit logs INJECTION_SUSPECTED_CONTEXT and the chunk is dropped — retrieved content is
untrusted, and anything that looks like an instruction should not reach the prompt.
"""
import re

from app.security.patterns import INJECTION_PATTERNS

_compiled = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def scan_context(chunk_text: str) -> list[str]:
    """Return the list of patterns that matched in this chunk (empty = clean)."""
    return [p.pattern for p in _compiled if p.search(chunk_text)]
