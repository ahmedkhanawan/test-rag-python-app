from collections.abc import Callable
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.rag.pipeline import RAGResult, answer_question
from app.services.embeddings import EmbeddingService
from app.services.generation import GenerationService
from app.services.vector_store import VectorStore

Answerer = Callable[[str], RAGResult]


@lru_cache
def _services() -> tuple[EmbeddingService, VectorStore, GenerationService]:
    return EmbeddingService(), VectorStore(), GenerationService()


def get_answerer() -> Answerer:
    """FastAPI dependency: runs the RAG pipeline with the real services.

    Tests override this with a fake so no OpenAI/Qdrant is needed.
    """

    def answer(question: str) -> RAGResult:
        embedder, store, generator = _services()
        return answer_question(question, embedder, store, generator)

    return answer


def get_embedder() -> EmbeddingService:
    """FastAPI dependency (overridden with fakes in tests)."""
    return _services()[0]


def get_vector_store() -> VectorStore:
    """FastAPI dependency (overridden with fakes in tests)."""
    return _services()[1]


_bearer = HTTPBearer(auto_error=False)


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency protecting admin routes; returns the admin username."""
    subject = decode_access_token(credentials.credentials) if credentials else None
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return subject
