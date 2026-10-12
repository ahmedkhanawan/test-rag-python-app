from types import SimpleNamespace

import openai
import pytest
from qdrant_client import QdrantClient

from app.models import Chunk, Document
from app.rag.pipeline import answer_question
from app.rag.prompts import (
    INSUFFICIENT_INFO_MESSAGE,
    SYSTEM_PROMPT,
    build_context,
    build_user_prompt,
)
from app.services.embeddings import EmbeddingError, EmbeddingService
from app.services.generation import GenerationError, GenerationService
from app.services.indexing import index_document
from app.services.retrieval import RetrievedChunk
from app.services.vector_store import VectorStore, VectorStoreError
from tests.fakes import FakeOpenAI


class FakeChat:
    def __init__(self, answer="Remote work is allowed [Source 1].", fail=False):
        self.calls = []
        self.answer, self.fail = answer, fail
        self.completions = self

    def create(self, model, messages):
        self.calls.append({"model": model, "messages": messages})
        if self.fail:
            raise openai.OpenAIError("secret-ish detail")
        msg = SimpleNamespace(content=self.answer)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def make_generator(**kw):
    chat = FakeChat(**kw)
    return GenerationService(client=SimpleNamespace(chat=chat)), chat


def rc(i=0, **kw):
    base = dict(score=0.9, chunk_id=f"c{i}", document_id="d1", document_name="Remote Policy",
                chunk_index=i, page_number=3, section="Remote Work", text=f"text {i}")
    return RetrievedChunk(**{**base, **kw})


@pytest.fixture
def embedder():
    return EmbeddingService(client=FakeOpenAI())


@pytest.fixture
def indexed_store(session, embedder):
    store = VectorStore(QdrantClient(":memory:"), collection="rag")
    doc = Document(name="Remote Policy", filename="remote.pdf")
    doc.chunks = [
        Chunk(chunk_index=0, text="remote employees may work from home three days", page_number=3, section="Remote Work"),
        Chunk(chunk_index=1, text="expense reports are due monthly", page_number=5),
    ]
    session.add(doc)
    session.commit()
    index_document(session, doc.id, embedder, store)
    return store, doc


def test_context_assembly_is_labeled_and_deterministic():
    chunks = [rc(0), rc(1, page_number=None, section=None, document_name="Handbook")]
    ctx = build_context(chunks)
    assert ctx == build_context(chunks)
    assert "[Source 1] Document: Remote Policy | Page: 3 | Section: Remote Work\ntext 0" in ctx
    assert "[Source 2] Document: Handbook\ntext 1" in ctx
    assert "\n\n---\n\n" in ctx


def test_grounding_prompt_content():
    for phrase in ["ONLY", "Do not invent", "outside knowledge", INSUFFICIENT_INFO_MESSAGE,
                   "Never invent source names", "not instructions"]:
        assert phrase in SYSTEM_PROMPT
    prompt = build_user_prompt("What?", "CONTEXT")
    assert "CONTEXT" in prompt and "Question: What?" in prompt


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_question_validation(bad, embedder, indexed_store):
    gen, chat = make_generator()
    with pytest.raises(ValueError):
        answer_question(bad, embedder, indexed_store[0], gen)
    assert chat.calls == []


def test_successful_pipeline_and_citations(embedder, indexed_store):
    store, doc = indexed_store
    gen, chat = make_generator()
    result = answer_question("remote employees work from home", embedder, store, gen, top_k=2)

    assert result.grounded and result.answer == "Remote work is allowed [Source 1]."
    top = result.sources[0]
    assert top.chunk_id == str(doc.chunks[0].id)
    assert top.document_id == str(doc.id)
    assert (top.document_name, top.page_number, top.section, top.chunk_index) == ("Remote Policy", 3, "Remote Work", 0)
    assert isinstance(top.score, float)

    call = chat.calls[0]
    assert call["model"] == "gpt-5.4-mini"
    assert call["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert "[Source 1] Document: Remote Policy | Page: 3 | Section: Remote Work" in call["messages"][1]["content"]
    assert "remote employees may work from home" in call["messages"][1]["content"]


def test_no_chunks_skips_llm(embedder, indexed_store):
    gen, chat = make_generator()
    result = answer_question("remote work", embedder, indexed_store[0], gen, score_threshold=0.999)
    assert result.answer == INSUFFICIENT_INFO_MESSAGE
    assert result.sources == [] and not result.grounded
    assert chat.calls == []


def test_embedding_failure(indexed_store):
    gen, chat = make_generator()
    bad = EmbeddingService(client=FakeOpenAI(fail=True))
    with pytest.raises(EmbeddingError):
        answer_question("q", bad, indexed_store[0], gen)
    assert chat.calls == []


def test_retrieval_failure(embedder):
    gen, chat = make_generator()
    empty_store = VectorStore(QdrantClient(":memory:"), collection="missing")
    with pytest.raises(VectorStoreError):
        answer_question("q", embedder, empty_store, gen)
    assert chat.calls == []


def test_generation_failure_hides_details(embedder, indexed_store):
    gen, _ = make_generator(fail=True)
    with pytest.raises(GenerationError) as exc:
        answer_question("remote work", embedder, indexed_store[0], gen)
    assert "secret-ish" not in str(exc.value)


def test_empty_llm_answer_is_error(embedder, indexed_store):
    gen, _ = make_generator(answer="  ")
    with pytest.raises(GenerationError):
        answer_question("remote work", embedder, indexed_store[0], gen)


def test_generation_model_config_and_missing_key():
    assert GenerationService(client=object()).model == "gpt-5.4-mini"
    svc = GenerationService()
    svc._api_key = None
    with pytest.raises(GenerationError, match="OPENAI_API_KEY"):
        svc.generate("s", "u")
