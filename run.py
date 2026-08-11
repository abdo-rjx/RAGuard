"""Run RAGGuard on the HOST/PORT configured in .env.

    python run.py

Equivalent to: uvicorn app.main:app --host <HOST> --port <PORT> --reload
"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
