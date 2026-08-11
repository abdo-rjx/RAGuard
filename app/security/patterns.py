"""Shared regex pattern lists (plan Section 10). Starting points, expected to grow."""

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
