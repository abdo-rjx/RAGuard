"""Default regex pattern lists (feature A4).

These are now SEED DEFAULTS only: on startup they are inserted into the
`guard_patterns` table (if empty), and they serve as the in-memory fallback
when the DB is unreachable or has no active patterns. At runtime the guards
read from the DB via `app/security/pattern_store.py`, not from this module —
so an admin can add/toggle/remove patterns through the API and the change
takes effect on the next cache refresh.

Starting points, expected to grow.
"""

# Scans user queries AND retrieved chunks for prompt-injection-style text.
# A match never blocks access — the security guarantee is the retriever, not the words.
INJECTION_PATTERNS = [
    r"ignore (all |previous |prior |system )?(previous |prior |all |system )?(system )?instructions",
    r"i am (actually |really )?the (ceo|cfo|cto|admin|administrator)",
    r"disable (security|restrictions|filters)",
    r"you are now",
    r"^\s*system\s*:",
    r"reveal (confidential|restricted|sensitive) information",
]

# Scans the LLM's response for secret-like content before it's returned to the client.
LEAK_PATTERNS = [
    r"sk-[A-Za-z0-9]{20,}",          # generic API-key-style prefix
    r"ghp_[A-Za-z0-9]{30,}",         # GitHub token style
    r"AKIA[0-9A-Z]{12,}",            # AWS access key style
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
    r"\b\d{13,16}\b",                # card-number-length digit runs
]
