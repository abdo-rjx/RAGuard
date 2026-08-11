"""Secure retrieval — plan Section 9. The two non-negotiable properties enforced here:
  1. role/department come only from the verified JWT (the CurrentUser passed in);
  2. every chunk Chroma returns is re-validated against the policy engine in plain
     Python before it is allowed anywhere near the prompt.
"""
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.audit.logger import write_audit_event
from app.ingestion.embedder import embed_text
from app.policy.policy_engine import PolicyEngine
from app.retrieval.vector_store import RetrievedChunk, VectorStore
from app.security.context_guard import scan_context
from app.security.query_guard import scan_query

DEFAULT_N_RESULTS = 5


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    matched_query_patterns: list[str] = field(default_factory=list)
    dropped_by_recheck: list[RetrievedChunk] = field(default_factory=list)
    dropped_by_context_guard: list[RetrievedChunk] = field(default_factory=list)
    note: str | None = None


class SecureRetriever:
    def __init__(self, policy: PolicyEngine, store: VectorStore):
        self._policy = policy
        self._store = store

    def retrieve(
        self,
        db: Session,
        *,
        user_id: int | None,
        username: str,
        role: str,
        message: str,
        n_results: int = DEFAULT_N_RESULTS,
    ) -> RetrievalResult:
        result = RetrievalResult()

        # --- step 2: scan the raw user message (informational, never blocking) ---
        result.matched_query_patterns = scan_query(message)
        if result.matched_query_patterns:
            write_audit_event(
                db,
                action="INJECTION_SUSPECTED_QUERY",
                user_id=user_id,
                username=username,
                role=role,
                query_text=message,
                decision="ALLOW",  # heuristic only — query proceeds; retriever is the guard
                reason="matched: " + ", ".join(result.matched_query_patterns),
            )

        # --- steps 3–4: policy-built Chroma filter + vector query -----------------
        where = self._policy.build_chroma_filter(role)
        if not self._policy.allowed_departments(role):
            result.note = "no_departments_authorized"
            return result

        try:
            embedding = embed_text(message)
        except Exception:
            # Embedding model unavailable (e.g. not downloaded) — degrade to empty context
            result.note = "embedding_unavailable"
            return result

        candidates = self._store.query(embedding, where=where, n_results=n_results)

        # --- step 5: defense-in-depth re-check (THE security line) -----------------
        for chunk in candidates:
            if self._policy.can_access_document(role, chunk.department, chunk.classification):
                result.chunks.append(chunk)
            else:
                result.dropped_by_recheck.append(chunk)
                write_audit_event(
                    db,
                    action="ACCESS_DENIED",
                    user_id=user_id,
                    username=username,
                    role=role,
                    query_text=message,
                    decision="DENY",
                    reason="recheck_failed",
                    details_json={
                        "chunk_id": chunk.id,
                        "department": chunk.department,
                        "classification": chunk.classification,
                    },
                )

        # --- step 6: context guard on surviving chunks -----------------------------
        survivors: list[RetrievedChunk] = []
        for chunk in result.chunks:
            hits = scan_context(chunk.text)
            if hits:
                result.dropped_by_context_guard.append(chunk)
                write_audit_event(
                    db,
                    action="INJECTION_SUSPECTED_CONTEXT",
                    user_id=user_id,
                    username=username,
                    role=role,
                    query_text=message,
                    decision="DENY",
                    reason="matched: " + ", ".join(hits),
                    details_json={"chunk_id": chunk.id, "document_id": chunk.document_id},
                )
            else:
                survivors.append(chunk)
        result.chunks = survivors

        return result


_retriever: SecureRetriever | None = None


def get_secure_retriever() -> SecureRetriever:
    """Lazy singleton. Needs the policy engine + vector store — both lazy themselves."""
    global _retriever
    if _retriever is None:
        from app.policy.policy_engine import get_policy_engine
        from app.retrieval.vector_store import get_vector_store

        _retriever = SecureRetriever(get_policy_engine(), get_vector_store())
    return _retriever
