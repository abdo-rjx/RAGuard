"""Single shared slowapi Limiter.

All routers must import this instance so the limits registered via
``@limiter.limit(...)`` are the same object that ``app.state.limiter`` exposes
for enforcement (slowapi enforces on the decorator's own instance). Keeping two
separate ``Limiter`` objects means the ``enabled`` toggle and the registered
route limits silently diverge.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(key_func=get_remote_address, enabled=settings.ENVIRONMENT != "test")
