"""RAGGuard — permission-aware RAG backend. FastAPI app entrypoint.

Starts up in stages as phases land:
  Phase 0: /health
  Phase 1: auth router
  Phase 2: policy engine (loaded at startup)
  Phase 3+: documents / chat / audit routers
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import SessionLocal, init_db
from app.policy.policy_engine import get_policy_engine
from app.rate_limit import limiter
from app.routers import (
    audit_router,
    auth_router,
    chat_router,
    conversations_router,
    documents_router,
    policy_router,
    security_router,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    get_policy_engine()  # load + validate policy once at startup
    _seed_guard_patterns()  # feature A4: DB-backed patterns, defaults on first boot
    yield


def _seed_guard_patterns() -> None:
    """Insert the default guard patterns if the table is empty (feature A4)."""
    from app.security.pattern_store import seed_default_patterns

    db = SessionLocal()
    try:
        seed_default_patterns(db)
    finally:
        db.close()


app = FastAPI(
    title="RAGGuard",
    description="Permission-aware RAG backend — unauthorized information never enters the LLM context.",
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiting to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

# Security headers on every response. If Clerk is added later, extend the CSP
# connect-src with the Clerk proxy/API origins used by the frontend.
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "  # inline style attributes in the UI
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    return response

app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(conversations_router.router)
app.include_router(documents_router.router)
app.include_router(audit_router.router)
app.include_router(policy_router.router)
app.include_router(security_router.router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index():
    from fastapi.responses import FileResponse

    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Monitoring/health endpoints for frontend compatibility
@app.get("/api/health/ping")
def health_ping() -> dict:
    return {"status": "ok", "timestamp": __import__("time").time()}


@app.get("/api/health/degradation")
def health_degradation(summary: bool = False) -> dict:
    """Health degradation check - returns ok for now"""
    return {
        "healthy": True,
        "degraded_services": [],
        "summary": "All systems operational" if summary else None
    }


@app.get("/api/provider-metrics")
def provider_metrics() -> dict:
    """Provider metrics - placeholder for LLM provider monitoring"""
    return {
        "providers": {
            "ollama": {
                "status": "healthy",
                "model": settings.OLLAMA_MODEL,
                "host": settings.OLLAMA_HOST,
                "latency_ms": 0,
                "error_rate": 0.0
            }
        }
    }


@app.get("/api/token-health")
def token_health() -> dict:
    """Token health check - placeholder for token monitoring"""
    return {
        "healthy": True,
        "token_usage": {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0
        },
        "rate_limits": {
            "remaining": 1000,
            "reset_at": None
        }
    }
