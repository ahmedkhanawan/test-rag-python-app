from collections.abc import Callable
from functools import lru_cache

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
