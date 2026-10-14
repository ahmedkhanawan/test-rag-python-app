import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import get_embedder, get_vector_store, require_admin
from app.services.embeddings import EmbeddingError, EmbeddingService
from app.services.retrieval import retrieve
from app.services.vector_store import CollectionNotFoundError, VectorStore, VectorStoreError

logger = logging.getLogger(__name__)

# Every route here requires a valid admin JWT.
router = APIRouter(prefix="/retrieval", tags=["retrieval"], dependencies=[Depends(require_admin)])


class SearchRequest(BaseModel):
    question: str
    top_k: int | None = Field(default=None, ge=1, le=20)  # None -> configured default

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        return v


class ChunkResult(BaseModel):
    rank: int
    score: float
    document_id: uuid.UUID
    document_name: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    section: str | None
    text: str


class SearchResponse(BaseModel):
    question: str
    results: list[ChunkResult]


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    embedder: EmbeddingService = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
) -> SearchResponse:
    """Retrieval only (embedding + vector search): no LLM call, no persistence."""
    try:
        chunks = retrieve(request.question, embedder, store, top_k=request.top_k)
    except CollectionNotFoundError:
        chunks = []  # nothing indexed yet
    except EmbeddingError as exc:
        logger.error("Retrieval search failed at embedding stage: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Embedding service failed") from None
    except VectorStoreError as exc:
        logger.error("Retrieval search failed at vector store stage: %s", type(exc).__name__)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Document search is unavailable"
        ) from None
    return SearchResponse(
        question=request.question,
        results=[
            ChunkResult(
                rank=i, score=c.score, document_id=c.document_id,
                document_name=c.document_name, chunk_id=c.chunk_id,
                chunk_index=c.chunk_index, page_number=c.page_number,
                section=c.section, text=c.text,
            )
            for i, c in enumerate(chunks, start=1)
        ],
    )
