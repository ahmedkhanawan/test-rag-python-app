import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import get_settings
from app.models import Chunk

logger = logging.getLogger(__name__)


class VectorStoreError(RuntimeError):
    """Qdrant is unavailable or returned an error."""


class CollectionNotFoundError(VectorStoreError):
    """The Qdrant collection does not exist (nothing indexed yet?)."""


@dataclass(frozen=True)
class SearchHit:
    score: float
    chunk_id: str
    payload: dict[str, Any]


def point_id(chunk: Chunk) -> str:
    """The Chunk UUID is used directly as the Qdrant point id."""
    return str(chunk.id)


def build_payload(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "document_name": chunk.document.name,
        "chunk_index": chunk.chunk_index,
        "page_number": chunk.page_number,
        "section": chunk.section,
        "text": chunk.text,
    }


class VectorStore:
    """Thin wrapper around Qdrant. SQL stays the source of truth."""

    def __init__(self, client: QdrantClient | None = None, collection: str | None = None) -> None:
        settings = get_settings()
        self.collection = collection or settings.qdrant_collection
        self._client = client or QdrantClient(url=settings.qdrant_url)

    def is_healthy(self) -> bool:
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False

    def ensure_collection(self, vector_size: int) -> None:
        """Create the collection (cosine distance) if missing; verify size otherwise."""
        try:
            if not self._client.collection_exists(self.collection):
                self._client.create_collection(
                    self.collection,
                    vectors_config=models.VectorParams(
                        size=vector_size, distance=models.Distance.COSINE
                    ),
                )
                logger.info("Created Qdrant collection %s (size=%d)", self.collection, vector_size)
                return
            params = self._client.get_collection(self.collection).config.params.vectors
        except Exception as exc:
            raise VectorStoreError(f"Qdrant error: {exc}") from exc
        if params.size != vector_size:
            raise VectorStoreError(
                f"Collection {self.collection} has vector size {params.size}, expected {vector_size}"
            )

    def upsert_chunks(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if not chunks:
            return
        points = [
            models.PointStruct(id=point_id(c), vector=list(v), payload=build_payload(c))
            for c, v in zip(chunks, vectors)
        ]
        try:
            self._client.upsert(self.collection, points=points)
        except Exception as exc:
            raise VectorStoreError(f"Qdrant upsert failed: {exc}") from exc

    def delete_document(self, document_id: str | uuid.UUID) -> None:
        """Remove every point of a document. Idempotent; a missing collection is a no-op."""
        selector = models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=str(document_id))
                    )
                ]
            )
        )
        try:
            if not self._client.collection_exists(self.collection):
                return
            self._client.delete(self.collection, points_selector=selector)
        except Exception as exc:
            raise VectorStoreError(f"Qdrant delete failed: {exc}") from exc

    def search(
        self, vector: Sequence[float], top_k: int, score_threshold: float | None = None
    ) -> list[SearchHit]:
        try:
            response = self._client.query_points(
                self.collection,
                query=list(vector),
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
            )
        except (UnexpectedResponse, ValueError) as exc:
            if "not found" in str(exc).lower() or "doesn't exist" in str(exc).lower():
                raise CollectionNotFoundError(
                    f"Collection {self.collection} does not exist"
                ) from exc
            raise VectorStoreError(f"Qdrant search failed: {exc}") from exc
        except Exception as exc:
            raise VectorStoreError(f"Qdrant search failed: {exc}") from exc
        return [
            SearchHit(score=p.score, chunk_id=str(p.id), payload=dict(p.payload or {}))
            for p in response.points
        ]
