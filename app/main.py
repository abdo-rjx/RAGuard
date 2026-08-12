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
from app.database import init_db
from app.policy.policy_engine import get_policy_engine
from app.rate_limit import limiter
from app.routers import audit_router, auth_router, chat_router, documents_router

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    get_policy_engine()  # load + validate policy once at startup
    yield


app = FastAPI(
    title="RAGGuard",
    description="Permission-aware RAG backend — unauthorized information never enters the LLM context.",
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiting to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(documents_router.router)
app.include_router(audit_router.router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index():
    from fastapi.responses import FileResponse

    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
