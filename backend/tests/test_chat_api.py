import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_answerer
from app.core.database import get_db
from app.main import app
from app.models import Chunk, Conversation, Document, Message, MessageRole
from app.rag.pipeline import RAGResult, answer_question
from app.services.embeddings import EmbeddingError, EmbeddingService
from app.services.generation import GenerationError, GenerationService
from app.services.indexing import index_document
from app.services.retrieval import RetrievedChunk
from app.services.vector_store import CollectionNotFoundError, VectorStore, VectorStoreError
from tests.fakes import FakeOpenAI
from tests.test_rag import make_generator


def rc(i: int) -> RetrievedChunk:
    return RetrievedChunk(
        score=0.8 - i / 10, chunk_id=str(uuid.uuid4()), document_id=str(uuid.uuid4()),
        document_name=f"Doc {i}", chunk_index=i, page_number=i + 1,
        section="Sec" if i == 0 else None, text=f"chunk text {i}",
    )


class FakeAnswerer:
    def __init__(self, result: RAGResult | Exception | None = None) -> None:
        self.calls: list[str] = []
        self.result = result or RAGResult("Answer [Source 1]", [rc(0), rc(1)], True)

    def __call__(self, question: str) -> RAGResult:
        self.calls.append(question)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def answerer() -> FakeAnswerer:
    return FakeAnswerer()


@pytest.fixture
def client(engine, answerer) -> Iterator[TestClient]:
    factory = sessionmaker(bind=engine)

    def override_db() -> Iterator[Session]:
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_answerer] = lambda: answerer
    yield TestClient(app)
    app.dependency_overrides.clear()


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_new_conversation(client, session, answerer):
    r = client.post("/api/chat", json={"question": "  How much leave?  "})
    assert r.status_code == 200
    body = r.json()
    cid = uuid.UUID(body["conversation_id"])
    assert body["assistant_message"]["content"] == "Answer [Source 1]"
    assert body["user_message"]["content"] == "How much leave?"
    assert body["grounded"] is True and len(body["sources"]) == 2
    assert answerer.calls == ["How much leave?"]

    msgs = session.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.created_at)).all()
    assert [(m.role, m.content) for m in msgs] == [
        (MessageRole.USER, "How much leave?"),
        (MessageRole.ASSISTANT, "Answer [Source 1]"),
    ]
    assert str(msgs[0].id) == body["user_message"]["id"]
    assert str(msgs[1].id) == body["assistant_message"]["id"]


def test_existing_conversation_reused(client, session):
    cid = client.post("/api/chat", json={"question": "first"}).json()["conversation_id"]
    r = client.post("/api/chat", json={"question": "second", "conversation_id": cid})
    assert r.status_code == 200 and r.json()["conversation_id"] == cid
    assert count(session, Conversation) == 1
    contents = session.scalars(select(Message.content).order_by(Message.created_at)).all()
    assert contents == ["first", "Answer [Source 1]", "second", "Answer [Source 1]"]


def test_messages_stay_with_their_conversation(client, session):
    a = client.post("/api/chat", json={"question": "qa1"}).json()["conversation_id"]
    b = client.post("/api/chat", json={"question": "qb1"}).json()["conversation_id"]
    client.post("/api/chat", json={"question": "qa2", "conversation_id": a})
    assert a != b
    for cid, expected in [(a, 4), (b, 2)]:
        n = count_for(session, cid)
        assert n == expected
    questions_b = session.scalars(
        select(Message.content).where(Message.conversation_id == uuid.UUID(b), Message.role == MessageRole.USER)
    ).all()
    assert questions_b == ["qb1"]


def count_for(session: Session, cid: str) -> int:
    return session.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == uuid.UUID(cid)))


def test_unknown_conversation_404_and_rag_not_called(client, session, answerer):
    r = client.post("/api/chat", json={"question": "hi", "conversation_id": str(uuid.uuid4())})
    assert r.status_code == 404
    assert answerer.calls == [] and count(session, Message) == 0


@pytest.mark.parametrize("payload", [{"question": ""}, {"question": "   "}, {}, {"question": "x", "conversation_id": "nope"}])
def test_invalid_request_422_and_rag_not_called(client, session, answerer, payload):
    assert client.post("/api/chat", json=payload).status_code == 422
    assert answerer.calls == [] and count(session, Conversation) == 0


@pytest.mark.parametrize(
    "error,status_code",
    [
        (EmbeddingError("sk-leak embedding"), 502),
        (GenerationError("sk-leak generation"), 502),
        (VectorStoreError("sk-leak qdrant"), 503),
        (CollectionNotFoundError("sk-leak collection"), 503),
    ],
)
def test_rag_failures_persist_nothing_and_do_not_leak(client, session, answerer, error, status_code):
    answerer.result = error
    r = client.post("/api/chat", json={"question": "hi"})
    assert r.status_code == status_code
    assert "sk-leak" not in r.text
    assert count(session, Conversation) == 0 and count(session, Message) == 0


def test_rag_failure_on_existing_conversation_adds_nothing(client, session, answerer):
    cid = client.post("/api/chat", json={"question": "ok"}).json()["conversation_id"]
    answerer.result = GenerationError("x")
    assert client.post("/api/chat", json={"question": "bad", "conversation_id": cid}).status_code == 502
    assert count(session, Message) == 2


def test_database_failure_returns_500_and_rolls_back(engine, answerer, session):
    factory = sessionmaker(bind=engine)

    def broken_db() -> Iterator[Session]:
        with factory() as s:
            def boom():
                raise OperationalError("stmt", {}, Exception("db secret"))
            s.commit = boom
            yield s

    app.dependency_overrides[get_db] = broken_db
    app.dependency_overrides[get_answerer] = lambda: answerer
    try:
        r = TestClient(app).post("/api/chat", json={"question": "hi"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 500 and "secret" not in r.text
    assert count(session, Message) == 0 and count(session, Conversation) == 0


def test_sources_structure_comes_from_rag_result(client, answerer):
    r = client.post("/api/chat", json={"question": "q"}).json()
    first = r["sources"][0]
    assert first["source_number"] == 1 and r["sources"][1]["source_number"] == 2
    assert set(first) == {"source_number", "document_id", "document_name", "chunk_id", "chunk_index",
                          "page_number", "section", "score", "text"}
    rag = answerer.result.sources[0]
    assert (first["chunk_id"], first["document_id"], first["document_name"]) == (rag.chunk_id, rag.document_id, rag.document_name)
    assert (first["page_number"], first["section"], first["score"], first["text"]) == (rag.page_number, rag.section, rag.score, rag.text)
    assert r["sources"][1]["section"] is None


def test_no_sources_answer_is_persisted(client, session, answerer):
    answerer.result = RAGResult("I couldn't find information.", [], False)
    r = client.post("/api/chat", json={"question": "q"}).json()
    assert r["sources"] == [] and r["grounded"] is False
    assert count(session, Message) == 2


def test_end_to_end_with_real_pipeline_and_fakes(engine, session):
    """Real RAG pipeline + in-memory Qdrant; only OpenAI is faked."""
    embedder = EmbeddingService(client=FakeOpenAI())
    store = VectorStore(QdrantClient(":memory:"), collection="chat_e2e")
    doc = Document(name="Remote Policy", filename="r.pdf")
    doc.chunks = [Chunk(chunk_index=0, text="remote employees may work from home", page_number=3, section="Remote")]
    session.add(doc)
    session.commit()
    index_document(session, doc.id, embedder, store)
    generator, chat_stub = make_generator(answer="Up to home work [Source 1]")

    factory = sessionmaker(bind=engine)

    def override_db() -> Iterator[Session]:
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_answerer] = lambda: (lambda q: answer_question(q, embedder, store, generator))
    try:
        r = TestClient(app).post("/api/chat", json={"question": "remote work from home"})
    finally:
        app.dependency_overrides.clear()
    body = r.json()
    assert r.status_code == 200
    src = body["sources"][0]
    assert src["document_id"] == str(doc.id) and src["chunk_id"] == str(doc.chunks[0].id)
    assert (src["document_name"], src["page_number"], src["section"]) == ("Remote Policy", 3, "Remote")
    assert body["assistant_message"]["content"] == "Up to home work [Source 1]"
    assert len(chat_stub.calls) == 1


def test_health_still_works(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
