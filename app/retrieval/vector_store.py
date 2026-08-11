"""ChromaDB persistent client wrapper (plan Section 3, 8)."""
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.config import settings


@dataclass
class RetrievedChunk:
    """A single chunk returned by Chroma, already carrying its access metadata."""
    id: str
    document_id: int
    department: str
    classification: str
    source_filename: str
    text: str
    distance: float = field(default=0.0)


class VectorStore:
    def __init__(self, persist_dir: str, collection_name: str = "documents"):
        import chromadb

        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(collection_name)

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str],
    ) -> None:
        self._collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    def query(self, embedding: list[float], where: dict | None = None, n_results: int = 5) -> list[RetrievedChunk]:
        """Query with an optional `where` filter. Returns chunk objects with metadata."""
        result = self._collection.query(
            query_embeddings=[embedding],
            where=where,
            n_results=n_results,
            include=["metadatas", "documents", "distances"],
        )

        chunks: list[RetrievedChunk] = []
        ids = result.get("ids", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        documents = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for cid, meta, text, dist in zip(ids, metadatas, documents, distances):
            meta = meta or {}
            chunks.append(
                RetrievedChunk(
                    id=cid,
                    document_id=meta.get("document_id"),
                    department=meta.get("department", ""),
                    classification=meta.get("classification", ""),
                    source_filename=meta.get("source_filename", ""),
                    text=text or "",
                    distance=dist or 0.0,
                )
            )
        return chunks

    def delete_by_ids(self, ids: list[str]) -> None:
        if ids:
            self._collection.delete(ids=ids)


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore(settings.CHROMA_PERSIST_DIR)
