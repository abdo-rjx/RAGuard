"""LLM-response scan before it returns to the client (plan Section 9 step 9 / Section 10).

A hit logs OUTPUT_BLOCKED and the flagged content is redacted with a safe fallback.
"""
import re

from app.security.patterns import LEAK_PATTERNS

_compiled = [re.compile(p, re.IGNORECASE) for p in LEAK_PATTERNS]

REDACTION = "[redacted: sensitive content was blocked by RAGGuard output guard]"


def scan_output(text: str) -> list[str]:
    """Return the list of leak patterns that matched (empty = clean)."""
    return [p.pattern for p in _compiled if p.search(text)]


def sanitize_output(text: str) -> tuple[str, list[str]]:
    """Redact any leak-pattern matches. Returns (sanitized_text, matched_patterns)."""
    hits: list[str] = []
    sanitized = text
    for p in _compiled:
        if p.search(sanitized):
            hits.append(p.pattern)
            sanitized = p.sub(REDACTION, sanitized)
    return sanitized, hits
