import uuid

import pymupdf
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_embedder, get_vector_store
from app.core.database import get_db
from app.main import app
from app.models import Chunk, Document, DocumentStatus
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStore, VectorStoreError
from tests.fakes import FakeOpenAI
from tests.test_auth_admin import auth, configured  # noqa: F401  (fixture re-export)

COLLECTION = "admin_test"


def pdf_bytes(*pages: str) -> bytes:
    pdf = pymupdf.open()
    for text in pages:
        page = pdf.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 780), text, fontsize=11)
    data = pdf.tobytes()
    pdf.close()
    return data


LEAVE = pdf_bytes("Employees receive 25 days of annual leave.")
REMOTE = pdf_bytes("Remote employees may work from home three days per week.")


class Env:
    def __init__(self, engine) -> None:
        self.factory = sessionmaker(bind=engine, expire_on_commit=False)
        self.client = TestClient(app)
        self.store = VectorStore(QdrantClient(":memory:"), collection=COLLECTION)
        self.embedder = EmbeddingService(client=FakeOpenAI())
        self.headers: dict = {}

    def points(self) -> int:
        if not self.store._client.collection_exists(COLLECTION):
            return 0
        return self.store._client.count(COLLECTION).count

    def upload(self, data: bytes = LEAVE, filename: str = "Leave.pdf", **form):
        return self.client.post(
            "/api/documents/upload",
            files={"file": (filename, data, "application/pdf")},
            data=form,
            headers=self.headers,
        )

    def count(self, model) -> int:
        with self.factory() as s:
            return s.scalar(select(func.count()).select_from(model))


@pytest.fixture
def env(configured, engine):  # noqa: F811
    e = Env(engine)

    def override_db():
        with e.factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedder] = lambda: e.embedder
    app.dependency_overrides[get_vector_store] = lambda: e.store
    e.headers = auth(e.client)
    yield e
    app.dependency_overrides.clear()


# --- auth ---------------------------------------------------------------

def test_all_new_admin_routes_require_a_token(env):
    some_id = uuid.uuid4()
    calls = [
        ("post", "/api/documents/upload", {"files": {"file": ("a.pdf", LEAVE)}}),
        ("post", f"/api/documents/{some_id}/reindex", {}),
        ("delete", f"/api/documents/{some_id}", {}),
        ("post", "/api/retrieval/search", {"json": {"question": "x"}}),
    ]
    for method, path, kwargs in calls:
        assert getattr(env.client, method)(path, **kwargs).status_code == 401, path
    assert env.count(Document) == 0


# --- upload -------------------------------------------------------------

def test_upload_ingests_and_indexes(env):
    r = env.upload(name="Leave Policy")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "READY" and body["chunk_count"] == 1
    assert body["name"] == "Leave Policy" and body["filename"] == "Leave.pdf"
    assert env.points() == 1
    assert len(env.embedder._client.embeddings.calls) == 1


def test_upload_name_defaults_to_filename_stem(env):
    assert env.upload(filename="../../Handbook.pdf").json()["name"] == "Handbook"


def test_upload_rejects_wrong_extension_bad_header_and_empty(env):
    assert env.upload(b"hello", "notes.txt").status_code == 422
    assert env.upload(b"not really a pdf", "fake.pdf").status_code == 422
    assert env.upload(b"", "empty.pdf").status_code == 422
    assert env.count(Document) == 0 and env.points() == 0


def test_upload_rejects_oversized_file(env, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    try:
        r = env.upload(b"%PDF-" + b"0" * (1024 * 1024 + 1), "big.pdf")
    finally:
        get_settings.cache_clear()
    assert r.status_code == 413
    assert env.count(Document) == 0


def test_upload_pdf_without_text_is_422_and_leaves_failed_document(env):
    r = env.upload(pdf_bytes(""), "scan.pdf")
    assert r.status_code == 422
    with env.factory() as s:
        doc = s.scalars(select(Document)).one()
        assert doc.status == DocumentStatus.FAILED
    assert env.count(Chunk) == 0 and env.points() == 0


def test_upload_embedding_failure_marks_failed_keeps_chunks_and_recovers_via_reindex(env):
    env.embedder = EmbeddingService(client=FakeOpenAI(fail=True))
    r = env.upload()
    assert r.status_code == 502
    assert "boom" not in r.text
    with env.factory() as s:
        doc = s.scalars(select(Document)).one()
        assert doc.status == DocumentStatus.FAILED
        doc_id = doc.id
    assert env.count(Chunk) == 1 and env.points() == 0

    env.embedder = EmbeddingService(client=FakeOpenAI())
    r = env.client.post(f"/api/documents/{doc_id}/reindex", headers=env.headers)
    assert r.status_code == 200 and r.json()["status"] == "READY"
    assert env.points() == 1


def test_upload_vector_store_failure_is_503_and_marks_failed(env, monkeypatch):
    def boom(*a, **k):
        raise VectorStoreError("qdrant down")

    monkeypatch.setattr(env.store, "upsert_chunks", boom)
    r = env.upload()
    assert r.status_code == 503 and "qdrant" not in r.text
    with env.factory() as s:
        assert s.scalars(select(Document)).one().status == DocumentStatus.FAILED


# --- reindex ------------------------------------------------------------

def test_reindex_is_idempotent(env):
    doc_id = env.upload().json()["id"]
    for _ in range(2):
        r = env.client.post(f"/api/documents/{doc_id}/reindex", headers=env.headers)
        assert r.status_code == 200 and r.json()["status"] == "READY"
    assert env.points() == 1  # points are keyed by chunk id, so overwritten


def test_reindex_unknown_document_404(env):
    r = env.client.post(f"/api/documents/{uuid.uuid4()}/reindex", headers=env.headers)
    assert r.status_code == 404


def test_reindex_while_processing_is_409(env):
    doc_id = env.upload().json()["id"]
    with env.factory() as s:
        s.get(Document, uuid.UUID(doc_id)).status = DocumentStatus.PROCESSING
        s.commit()
    assert env.client.post(f"/api/documents/{doc_id}/reindex", headers=env.headers).status_code == 409


def test_reindex_document_without_chunks_is_409_and_failed(env):
    with env.factory() as s:
        d = Document(name="Empty", filename="e.pdf", status=DocumentStatus.READY)
        s.add(d)
        s.commit()
        doc_id = d.id
    r = env.client.post(f"/api/documents/{doc_id}/reindex", headers=env.headers)
    assert r.status_code == 409
    with env.factory() as s:
        assert s.get(Document, doc_id).status == DocumentStatus.FAILED


# --- delete -------------------------------------------------------------

def test_delete_removes_rows_chunks_and_only_its_points(env):
    keep = env.upload(REMOTE, "Remote.pdf").json()["id"]
    gone = env.upload().json()["id"]
    assert env.points() == 2

    r = env.client.delete(f"/api/documents/{gone}", headers=env.headers)
    assert r.status_code == 204
    assert env.points() == 1
    with env.factory() as s:
        assert [str(d.id) for d in s.scalars(select(Document))] == [keep]
        assert s.scalar(select(func.count()).select_from(Chunk)) == 1
    hits = env.store.search(env.embedder.embed_text("annual leave days"), top_k=5)
    assert {h.payload["document_id"] for h in hits} == {keep}


def test_delete_unknown_document_404(env):
    assert env.client.delete(f"/api/documents/{uuid.uuid4()}", headers=env.headers).status_code == 404


def test_delete_when_qdrant_fails_changes_nothing(env, monkeypatch):
    doc_id = env.upload().json()["id"]

    def boom(*a, **k):
        raise VectorStoreError("qdrant down")

    monkeypatch.setattr(env.store, "delete_document", boom)
    r = env.client.delete(f"/api/documents/{doc_id}", headers=env.headers)
    assert r.status_code == 503
    assert env.count(Document) == 1 and env.count(Chunk) == 1 and env.points() == 1


def test_delete_works_when_collection_never_existed(env):
    with env.factory() as s:
        d = Document(name="Orphan", filename="o.pdf", status=DocumentStatus.FAILED)
        s.add(d)
        s.commit()
        doc_id = d.id
    assert env.client.delete(f"/api/documents/{doc_id}", headers=env.headers).status_code == 204
    assert env.count(Document) == 0


# --- retrieval playground -----------------------------------------------

def test_retrieval_search_returns_ranked_chunks_with_scores(env):
    env.upload(LEAVE, "Leave.pdf")
    env.upload(REMOTE, "Remote.pdf")
    r = env.client.post(
        "/api/retrieval/search",
        json={"question": "annual leave days", "top_k": 2},
        headers=env.headers,
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert [x["rank"] for x in results] == [1, 2]
    assert results[0]["document_name"] == "Leave"
    assert results[0]["score"] >= results[1]["score"]
    assert {"chunk_id", "page_number", "section", "text", "chunk_index"} <= results[0].keys()


def test_retrieval_search_empty_index_returns_no_results(env):
    r = env.client.post("/api/retrieval/search", json={"question": "anything"}, headers=env.headers)
    assert r.status_code == 200 and r.json()["results"] == []


@pytest.mark.parametrize("body", [{"question": "   "}, {"question": "x", "top_k": 0}, {"question": "x", "top_k": 99}])
def test_retrieval_search_validation(env, body):
    assert env.client.post("/api/retrieval/search", json=body, headers=env.headers).status_code == 422


def test_retrieval_search_embedding_failure_is_502(env):
    env.embedder = EmbeddingService(client=FakeOpenAI(fail=True))
    r = env.client.post("/api/retrieval/search", json={"question": "x"}, headers=env.headers)
    assert r.status_code == 502 and "boom" not in r.text
