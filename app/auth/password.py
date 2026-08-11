"""Password hashing using bcrypt directly (not passlib) — plan Section 3 design decision.

passlib's bcrypt backend breaks on bcrypt>=4.1 (it reads a removed __about__.__version__
attribute). Calling bcrypt.hashpw/checkpw directly sidesteps the version trap entirely.
"""
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
