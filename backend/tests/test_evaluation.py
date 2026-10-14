import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.main import app
from app.models import Chunk, Document, DocumentStatus
from app.rag.evaluation import (
    RunContext,
    UsageRecordingClient,
    aggregate,
    check_answer,
    cited_sources,
    is_refusal,
    list_runs,
    load_dataset,
    load_run,
    normalize,
    numbers_in,
    run_evaluation,
    save_run,
    score_retrieval,
    validate_dataset,
)
from app.rag.prompts import INSUFFICIENT_INFO_MESSAGE
from app.services.embeddings import EmbeddingService
from app.services.generation import GenerationService
from app.services.indexing import index_document
from app.services.retrieval import RetrievedChunk
from app.services.vector_store import VectorStore
from tests.fakes import FakeOpenAI
from tests.test_auth_admin import auth, configured  # noqa: F401  (fixture re-export)
from tests.test_rag import make_generator

DOC = "Handbook"
LEAVE_TEXT = "Full-time employees receive 20 paid annual-leave days per calendar year."
OTHER_TEXT = "Visitors must be registered at reception and accompanied by an employee."


def chunk(text, doc=DOC, score=0.7, i=0):
    return RetrievedChunk(score=score, chunk_id=f"c{i}", document_id="d", document_name=doc,
                          chunk_index=i, page_number=1, section=None, text=text)


def fact(fid="leave", phrase="20 paid annual-leave days", doc=DOC):
    return {"id": fid, "any_of": [{"document": doc, "contains": phrase}]}


def question(**kw):
    q = {"id": "q1", "category": "direct", "question": "How many leave days?",
         "expected_answer": "20", "answerable": True, "facts": [fact()],
         "answer_checks": [["20", "twenty"]]}
    q.update(kw)
    return q


# --- helpers ---------------------------------------------------------------

def test_normalize_and_numbers():
    assert normalize("  It’s  $1,250 — OK ") == "it's $1250 - ok"
    assert numbers_in("Up to $250 [Source 12] at 10:00 a.m., 3 days") == {"250", "10:00", "3"}


def test_cited_sources_parses_bracket_groups():
    assert cited_sources("A [Source 1]. B [Source 3][Source 1] and [Sources 2, 4].") == [1, 2, 3, 4]
    assert cited_sources("No cites, but [see page 4].") == []


@pytest.mark.parametrize("text,expected", [
    (INSUFFICIENT_INFO_MESSAGE, True),
    ("I couldn’t find a stated number of sick days in the documents.", True),
    ("The excerpts do not contain that.", True),
    ("Employees receive 20 days [Source 1].", False),
])
def test_is_refusal(text, expected):
    assert is_refusal(text) is expected


# --- retrieval metrics -----------------------------------------------------

def test_score_retrieval_rank_recall_and_mrr_inputs():
    q = question(facts=[fact("leave"), fact("visitors", "registered at reception")])
    r = score_retrieval(q, [chunk("irrelevant", i=0), chunk(LEAVE_TEXT, i=1), chunk(OTHER_TEXT, i=2)])
    assert r["first_relevant_rank"] == 2 and r["reciprocal_rank"] == 0.5
    assert r["recall"] == 1.0 and r["hit"] is True
    assert [x["relevant"] for x in r["retrieved"]] == [False, True, True]


def test_score_retrieval_partial_and_missing():
    q = question(facts=[fact("leave"), fact("visitors", "registered at reception")])
    partial = score_retrieval(q, [chunk(LEAVE_TEXT)])
    assert partial["recall"] == 0.5 and partial["facts_missing"] == ["visitors"]
    none = score_retrieval(q, [chunk("nothing relevant")])
    assert none["hit"] is False and none["reciprocal_rank"] == 0.0 and none["first_relevant_rank"] is None


def test_score_retrieval_requires_matching_document_and_cuts_at_k():
    q = question()
    assert score_retrieval(q, [chunk(LEAVE_TEXT, doc="Other")])["hit"] is False
    chunks = [chunk("x", i=i) for i in range(5)] + [chunk(LEAVE_TEXT, i=5)]
    assert score_retrieval(q, chunks)["hit"] is False  # rank 6 is outside top 5


def test_unsupported_question_has_no_recall_metrics():
    r = score_retrieval(question(answerable=False, facts=[]), [chunk(OTHER_TEXT)])
    assert "recall" not in r and r["top_score"] == 0.7


# --- answer checks ---------------------------------------------------------

def checks(answer, q=None, chunks=None):
    q = q or question()
    retrieval = score_retrieval(q, chunks or [chunk(LEAVE_TEXT)])
    return check_answer(q, answer, retrieval)


def test_good_answer_passes_all_checks():
    c = checks("Employees receive 20 paid annual-leave days [Source 1].")
    assert c["correct"] and c["citation_valid"] and c["citation_supported"] and c["numbers_grounded"]
    assert c["failures"] == []


def test_incorrect_false_refusal_and_citation_failures():
    assert "incorrect" in checks("Employees receive some days [Source 1].")["failures"][0]
    refusal = checks(INSUFFICIENT_INFO_MESSAGE)
    assert refusal["false_refusal"] and "false refusal" in refusal["failures"][0]
    assert any("cites no source" in f for f in checks("It is 20 days.")["failures"])
    assert any("invalid source number" in f for f in checks("20 days [Source 4].")["failures"])
    wrong = checks("20 days [Source 2].", chunks=[chunk(LEAVE_TEXT), chunk(OTHER_TEXT, i=1)])
    assert wrong["citation_valid"] and not wrong["citation_supported"]


def test_invented_number_is_flagged_as_unfaithful():
    c = checks("Employees receive 20 days, plus 7 extra days [Source 1].")
    assert c["unsupported_numbers"] == ["7"] and not c["numbers_grounded"]
    assert any("unfaithful" in f for f in c["failures"])


def test_unsupported_question_must_be_refused():
    q = question(answerable=False, facts=[], answer_checks=[], absent_terms=["bonus"])
    ok = checks("I couldn't find information about this topic in the available company documents.", q)
    assert ok["correct_refusal"] and ok["failures"] == []
    bad = checks("The bonus is 10% [Source 1].", q)
    assert not bad["correct_refusal"] and len(bad["failures"]) == 2  # not refused + invented number


# --- dataset validation ----------------------------------------------------

def seed(session, text=LEAVE_TEXT, status=DocumentStatus.READY, name=DOC):
    d = Document(name=name, filename=f"{name}.pdf", status=status)
    d.chunks = [Chunk(chunk_index=0, text=text, page_number=1)]
    session.add(d)
    session.commit()
    return d


def dataset(*qs, docs=(DOC,)):
    return {"version": 1, "documents": list(docs), "questions": list(qs)}


def test_validate_dataset_ok(session):
    seed(session)
    unsupported = question(id="q2", answerable=False, facts=[], answer_checks=[], absent_terms=["bonus"])
    assert validate_dataset(dataset(question(), unsupported), session) == []


def test_validate_dataset_reports_problems(session):
    seed(session, status=DocumentStatus.FAILED)
    problems = validate_dataset(
        dataset(
            question(facts=[fact(phrase="not in the document")]),
            question(id="q2", answerable=False, facts=[], answer_checks=[], absent_terms=["annual-leave"]),
            question(id="q3", facts=[]),
            docs=(DOC, "Missing"),
        ),
        session,
    )
    text = "\n".join(problems)
    assert "'Missing': expected exactly 1" in text
    assert "not READY" in text
    assert "phrase not found" in text
    assert "appears in the indexed documents" in text
    assert "answerable question without facts" in text


def test_committed_dataset_is_well_formed():
    ds = load_dataset()
    qs = ds["questions"]
    assert len(qs) == 30 and len({q["id"] for q in qs}) == 30
    assert {q["category"] for q in qs} == {"direct", "paraphrase", "multi_part", "unsupported"}
    for q in qs:
        assert q["expected_answer"]
        if q["answerable"]:
            assert q["facts"] and q["answer_checks"]
        else:
            assert q["absent_terms"] and not q["facts"]


# --- run + aggregate (fakes; no OpenAI / network) --------------------------

@pytest.fixture
def indexed(session):
    embedder = EmbeddingService(client=FakeOpenAI())
    store = VectorStore(QdrantClient(":memory:"), collection="eval_test")
    doc = seed(session)
    index_document(session, doc.id, embedder, store)
    return embedder, store


def test_run_evaluation_retrieval_mode(indexed):
    embedder, store = indexed
    ds = dataset(
        question(question="annual-leave days calendar year"),
        question(id="q2", answerable=False, facts=[], answer_checks=[], absent_terms=["bonus"], question="bonus"),
    )
    run = run_evaluation(ds, RunContext(embedder, store), mode="retrieval")
    agg = run["aggregate"]
    assert agg["retrieval"]["recall_at_k"] == 1.0 and agg["retrieval"]["mrr"] == 1.0
    assert agg["evaluated"] == 1 and agg["passed"] == 1  # unsupported not judged without answers
    assert run["results"][1]["passed"] is None and "answers" not in agg
    assert run["config"]["chat_model"] is None


def test_run_evaluation_full_mode_scores_answers(indexed):
    embedder, store = indexed
    gen, chat = make_generator(answer="Employees receive 20 paid annual-leave days [Source 1].")
    ds = dataset(question(question="annual-leave days calendar year"))
    run = run_evaluation(ds, RunContext(embedder, store, GenerationService(client=SimpleNamespace(chat=chat))), mode="full")
    assert run["results"][0]["passed"] and run["aggregate"]["answers"]["correct_rate"] == 1.0
    assert len(chat.calls) == 1


def test_run_evaluation_records_errors_without_retrying_and_aborts(indexed):
    _, store = indexed
    failing = EmbeddingService(client=FakeOpenAI(fail=True))
    ds = dataset(*[question(id=f"q{i}") for i in range(6)])
    run = run_evaluation(ds, RunContext(failing, store), mode="retrieval", max_consecutive_errors=3)
    assert run["aborted"] and len(run["results"]) == 3
    assert all(r["error"] == "EmbeddingError" and r["passed"] is False for r in run["results"])
    assert len(failing._client.embeddings.calls) == 3  # one attempt each, no retries
    assert run["aggregate"]["errors"] == 3 and run["aggregate"]["retrieval"]["mrr"] is None


def test_full_mode_needs_a_generator(indexed):
    embedder, store = indexed
    with pytest.raises(ValueError):
        run_evaluation(dataset(question()), RunContext(embedder, store), mode="full")


def test_usage_recording_client_tallies_usage():
    usage = SimpleNamespace(total_tokens=7, prompt_tokens=5, completion_tokens=2)
    inner = SimpleNamespace(
        embeddings=SimpleNamespace(create=lambda **k: SimpleNamespace(data=[], usage=usage)),
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **k: SimpleNamespace(usage=usage))),
    )
    client = UsageRecordingClient(inner)
    client.embeddings.create(model="m", input=["a"])
    client.chat.completions.create(model="m", messages=[])
    assert client.usage == {
        "embedding_requests": 1, "embedding_tokens": 7,
        "chat_requests": 1, "chat_prompt_tokens": 5, "chat_completion_tokens": 2,
    }


def test_aggregate_empty():
    assert aggregate([], "full")["retrieval"]["mrr"] is None


# --- result files + API ----------------------------------------------------

def make_run(run_id="20260101T000000Z-full", mode="full"):
    return {"id": run_id, "started_at": "2026-01-01T00:00:00+00:00", "mode": mode, "aborted": False,
            "dataset": {"version": 1, "questions": 1, "evaluated": 1},
            "aggregate": {"questions": 1}, "results": [{"id": "q1"}]}


def test_save_list_and_load_runs(tmp_path):
    save_run(make_run("20260101T000000Z-full"), tmp_path)
    newer = make_run("20260102T000000Z-retrieval", "retrieval")
    newer["started_at"] = "2026-01-02T00:00:00+00:00"
    save_run(newer, tmp_path)
    (tmp_path / "broken.json").write_text("{not json")
    assert [r["id"] for r in list_runs(tmp_path)] == ["20260102T000000Z-retrieval", "20260101T000000Z-full"]
    assert load_run("20260101T000000Z-full", tmp_path)["results"] == [{"id": "q1"}]
    assert load_run("missing", tmp_path) is None
    assert load_run("../secret", tmp_path) is None


@pytest.fixture
def api(configured, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("EVALUATION_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "results").mkdir()
    save_run(make_run(), tmp_path / "results")
    client = TestClient(app)
    yield client, auth(client)
    get_settings.cache_clear()


def test_evaluation_api_requires_auth(api):
    client, _ = api
    assert client.get("/api/admin/evaluation/runs").status_code == 401
    assert client.get("/api/admin/evaluation/runs/20260101T000000Z-full").status_code == 401


def test_evaluation_api_lists_and_returns_runs(api):
    client, headers = api
    runs = client.get("/api/admin/evaluation/runs", headers=headers).json()
    assert [r["id"] for r in runs] == ["20260101T000000Z-full"] and "results" not in runs[0]
    run = client.get("/api/admin/evaluation/runs/20260101T000000Z-full", headers=headers)
    assert run.status_code == 200 and run.json()["results"] == [{"id": "q1"}]
    assert client.get("/api/admin/evaluation/runs/nope", headers=headers).status_code == 404
    assert client.get("/api/admin/evaluation/runs/..%2Fsecret", headers=headers).status_code == 404
