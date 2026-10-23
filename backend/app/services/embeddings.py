import logging
from collections.abc import Sequence

import openai
from openai import OpenAI

from app.core.config import get_settings, reveal

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """The embedding provider failed or is not configured."""


class EmbeddingService:
    """The only place that talks to OpenAI embeddings."""

    def __init__(
        self,
        client: OpenAI | None = None,
        model: str | None = None,
        batch_size: int = 100,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.openai_embedding_model
        self.batch_size = batch_size
        self._client = client
        self._api_key = reveal(settings.openai_api_key)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not self._api_key:
                raise EmbeddingError("OPENAI_API_KEY is not configured")
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts in order, sending them to the API in batches."""
        if any(not t or not t.strip() for t in texts):
            raise ValueError("Cannot embed empty text")
        if not texts:
            return []
        client = self._get_client()
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = list(texts[i : i + self.batch_size])
            try:
                response = client.embeddings.create(model=self.model, input=batch)
            except openai.OpenAIError as exc:
                # Provider messages can echo credentials; keep only the exception type.
                logger.error("OpenAI embedding request failed: %s", type(exc).__name__)
                raise EmbeddingError(
                    f"OpenAI embedding request failed ({type(exc).__name__})"
                ) from exc
            data = sorted(response.data, key=lambda d: d.index)
            if len(data) != len(batch):
                raise EmbeddingError("OpenAI returned an unexpected number of embeddings")
            vectors.extend(list(d.embedding) for d in data)
        return vectors

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]
