"""sentence-transformers wrapper. Model is loaded lazily on first use so importing
the module (e.g. in tests) never triggers a download/load."""
from functools import lru_cache
from typing import Iterable

from app.config import settings


@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.EMBEDDING_MODEL)


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    """Batch-encode texts into float vectors."""
    return _model().encode(list(texts), normalize_embeddings=True).tolist()


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
