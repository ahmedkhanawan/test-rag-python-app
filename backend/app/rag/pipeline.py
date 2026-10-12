import logging
from dataclasses import dataclass

from app.rag.prompts import (
    INSUFFICIENT_INFO_MESSAGE,
    SYSTEM_PROMPT,
    build_context,
    build_user_prompt,
)
from app.services.embeddings import EmbeddingService
from app.services.generation import GenerationService
from app.services.retrieval import RetrievedChunk, retrieve
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RAGResult:
    answer: str
    # Citations come from retrieved chunks (application data), never from the LLM.
    sources: list[RetrievedChunk]
    grounded: bool  # False when nothing was retrieved and the LLM was not called


def answer_question(
    question: str,
    embedder: EmbeddingService,
    store: VectorStore,
    generator: GenerationService,
    top_k: int | None = None,
    score_threshold: float | None = None,
) -> RAGResult:
    """question -> embed -> retrieve -> context -> grounded prompt -> LLM.

    Embedding, vector-store and generation errors propagate as their own
    application exceptions (EmbeddingError, VectorStoreError, GenerationError).
    """
    if not question or not question.strip():
        raise ValueError("Question must not be empty")
    question = question.strip()

    chunks = retrieve(question, embedder, store, top_k=top_k, score_threshold=score_threshold)
    if not chunks:
        logger.info("No relevant chunks retrieved; skipping LLM call")
        return RAGResult(answer=INSUFFICIENT_INFO_MESSAGE, sources=[], grounded=False)

    answer = generator.generate(SYSTEM_PROMPT, build_user_prompt(question, build_context(chunks)))
    return RAGResult(answer=answer, sources=chunks, grounded=True)
