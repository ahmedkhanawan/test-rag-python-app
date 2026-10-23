import pytest

from app.core.config import get_settings
from app.services.embeddings import EmbeddingError, EmbeddingService
from tests.fakes import FakeOpenAI, fake_vector


def test_default_model_is_text_embedding_3_small():
    assert EmbeddingService(client=FakeOpenAI()).model == "text-embedding-3-small"


def test_embed_text_uses_model_and_converts_response():
    client = FakeOpenAI()
    vec = EmbeddingService(client=client).embed_text("annual leave")
    assert vec == fake_vector("annual leave")
    assert client.embeddings.calls[0]["model"] == "text-embedding-3-small"


def test_batching_and_order_preserved():
    client = FakeOpenAI()
    texts = [f"text {i}" for i in range(5)]
    vectors = EmbeddingService(client=client, batch_size=2).embed_texts(texts)
    assert [len(c["input"]) for c in client.embeddings.calls] == [2, 2, 1]
    assert vectors == [fake_vector(t) for t in texts]


def test_empty_text_rejected():
    svc = EmbeddingService(client=FakeOpenAI())
    for bad in ["", "   "]:
        with pytest.raises(ValueError):
            svc.embed_text(bad)
    with pytest.raises(ValueError):
        svc.embed_texts(["ok", ""])


def test_api_failure_wrapped():
    # Only the exception type is kept: provider messages can echo credentials.
    with pytest.raises(EmbeddingError, match="OpenAIError") as exc_info:
        EmbeddingService(client=FakeOpenAI(fail=True)).embed_text("hi")
    assert "boom" not in str(exc_info.value)


def test_missing_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        monkeypatch.setattr(get_settings(), "openai_api_key", None)
        with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
            EmbeddingService().embed_text("hi")
    finally:
        get_settings.cache_clear()
