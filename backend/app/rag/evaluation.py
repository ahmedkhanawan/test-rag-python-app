"""RAG evaluation: dataset validation, retrieval metrics, deterministic answer checks.

Everything here is deterministic and free except `run_evaluation`, which calls the
configured embedding model (and, in "full" mode, the chat model) through the existing
services. No LLM judge is used; see docs/evaluation.md for what the checks can and
cannot establish.
"""

import hashlib
import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Chunk, Document
from app.rag.pipeline import answer_question
from app.rag.prompts import INSUFFICIENT_INFO_MESSAGE
from app.services.embeddings import EmbeddingError, EmbeddingService
from app.services.generation import GenerationError, GenerationService
from app.services.retrieval import RetrievedChunk, retrieve
from app.services.vector_store import VectorStore, VectorStoreError

logger = logging.getLogger(__name__)

K = 5  # Recall@K / Hit@K are always computed on the top 5 retrieved chunks
MODES = ("retrieval", "full")
_RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


# --- paths ------------------------------------------------------------------

def evaluation_dir() -> Path:
    configured = get_settings().evaluation_dir
    return Path(configured) if configured else Path(__file__).resolve().parents[3] / "evaluation"


def results_dir() -> Path:
    return evaluation_dir() / "results"


# --- text helpers -----------------------------------------------------------

def normalize(text: str) -> str:
    """Lowercase, unify quotes/dashes, drop thousands separators, collapse whitespace."""
    t = text.lower().replace("’", "'").replace("—", "-").replace("–", "-")
    t = re.sub(r"(?<=\d),(?=\d)", "", t)
    return re.sub(r"\s+", " ", t).strip()


_REFUSAL_PATTERNS = [
    normalize(INSUFFICIENT_INFO_MESSAGE),
    "couldn't find",
    "could not find",
    "do not contain",
    "does not contain",
    "doesn't contain",
    "does not specify",
    "doesn't specify",
    "do not specify",
    "not specified",
    "does not state",
    "doesn't state",
    "not mentioned",
    "does not mention",
    "doesn't mention",
    "no information",
    "not covered",
    "not provide",
    "not include information",
]


def is_refusal(answer: str) -> bool:
    n = normalize(answer)
    return any(p in n for p in _REFUSAL_PATTERNS)


def cited_sources(answer: str) -> list[int]:
    """Source numbers cited in bracket groups such as [Source 1] or [Sources 1, 2]."""
    numbers: list[int] = []
    for group in re.findall(r"\[([^\]]*)\]", answer):
        if group.strip().lower().startswith("source"):
            numbers.extend(int(n) for n in re.findall(r"\d+", group))
    return sorted(set(numbers))


_NUMBER = re.compile(r"\d+(?:[.:]\d+)*")


def numbers_in(text: str) -> set[str]:
    return set(_NUMBER.findall(re.sub(r"\[[^\]]*\]", " ", normalize(text))))


# --- dataset ----------------------------------------------------------------

def load_dataset(path: Path | None = None) -> dict[str, Any]:
    path = path or evaluation_dir() / "questions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def dataset_hash(path: Path | None = None) -> str:
    path = path or evaluation_dir() / "questions.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_dataset(dataset: dict[str, Any], session: Session) -> list[str]:
    """Check the labels against the indexed data; returns a list of problems (empty = OK).

    Every document must be READY with chunks, every fact phrase must occur in a chunk of
    its document, and every term declared absent for an unsupported question must occur
    in no chunk. This keeps expected labels tied to what is actually indexed.
    """
    problems: list[str] = []
    texts: dict[str, list[str]] = {}
    for name in dataset["documents"]:
        docs = list(session.scalars(select(Document).where(Document.name == name)))
        if len(docs) != 1:
            problems.append(f"document {name!r}: expected exactly 1, found {len(docs)}")
            continue
        if docs[0].status.value != "READY":
            problems.append(f"document {name!r} is {docs[0].status.value}, not READY")
        chunks = list(session.scalars(select(Chunk).where(Chunk.document_id == docs[0].id)))
        if not chunks:
            problems.append(f"document {name!r} has no chunks")
        texts[name] = [normalize(c.text) for c in chunks]

    all_text = [t for chunk_texts in texts.values() for t in chunk_texts]
    seen_ids: set[str] = set()
    for q in dataset["questions"]:
        if q["id"] in seen_ids:
            problems.append(f"{q['id']}: duplicate id")
        seen_ids.add(q["id"])
        if q["answerable"] and not q["facts"]:
            problems.append(f"{q['id']}: answerable question without facts")
        if not q["answerable"] and (q["facts"] or not q.get("absent_terms")):
            problems.append(f"{q['id']}: unsupported question needs absent_terms and no facts")
        for fact in q["facts"]:
            for opt in fact["any_of"]:
                chunk_texts = texts.get(opt["document"], [])
                if not any(normalize(opt["contains"]) in t for t in chunk_texts):
                    problems.append(
                        f"{q['id']}/{fact['id']}: phrase not found in {opt['document']!r}: "
                        f"{opt['contains']!r}"
                    )
        for term in q.get("absent_terms", []):
            if any(normalize(term) in t for t in all_text):
                problems.append(f"{q['id']}: term {term!r} appears in the indexed documents")
    return problems


# --- retrieval metrics ------------------------------------------------------

def _matches(fact: dict, document_name: str, text: str) -> bool:
    n = normalize(text)
    return any(
        opt["document"] == document_name and normalize(opt["contains"]) in n
        for opt in fact["any_of"]
    )


def score_retrieval(question: dict, chunks: Sequence[RetrievedChunk], k: int = K) -> dict:
    """Per-question retrieval result. Metrics are only defined for answerable questions."""
    top = list(chunks[:k])
    facts = question["facts"]
    rows = []
    for rank, c in enumerate(top, start=1):
        matched = [f["id"] for f in facts if _matches(f, c.document_name, c.text)]
        rows.append(
            {
                "rank": rank,
                "score": c.score,
                "chunk_id": c.chunk_id,
                "document_name": c.document_name,
                "page_number": c.page_number,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "relevant": bool(matched),
                "facts": matched,
            }
        )
    result: dict[str, Any] = {"retrieved": rows, "top_score": top[0].score if top else None}
    if question["answerable"]:
        found = {fid for r in rows for fid in r["facts"]}
        first = next((r["rank"] for r in rows if r["relevant"]), None)
        result.update(
            facts_found=sorted(found),
            facts_missing=sorted(f["id"] for f in facts if f["id"] not in found),
            recall=len(found) / len(facts),
            hit=first is not None,
            first_relevant_rank=first,
            reciprocal_rank=1 / first if first else 0.0,
        )
    return result


# --- answer checks ----------------------------------------------------------

def check_answer(question: dict, answer: str, retrieval: dict) -> dict:
    """Deterministic answer checks. Returns booleans plus a list of failure strings."""
    rows = retrieval["retrieved"]
    refused = is_refusal(answer)
    cited = cited_sources(answer)
    context_numbers = set().union(*(numbers_in(r["text"]) for r in rows)) if rows else set()
    allowed_numbers = context_numbers | numbers_in(question["question"])
    unsupported_numbers = sorted(numbers_in(answer) - allowed_numbers)
    result: dict[str, Any] = {
        "refused": refused,
        "cited_sources": cited,
        "unsupported_numbers": unsupported_numbers,
        "numbers_grounded": not unsupported_numbers,
        "failures": [],
    }
    failures: list[str] = result["failures"]
    if unsupported_numbers:
        failures.append(f"unfaithful: numbers not in retrieved context: {unsupported_numbers}")

    if question["answerable"]:
        n = normalize(answer)
        missing = [g for g in question["answer_checks"] if not any(normalize(a) in n for a in g)]
        valid = bool(cited) and all(1 <= c <= len(rows) for c in cited)
        supported = valid and any(rows[c - 1]["relevant"] for c in cited)
        result.update(
            correct=not refused and not missing,
            false_refusal=refused,
            citation_valid=valid,
            citation_supported=supported,
        )
        if refused:
            failures.append("false refusal: answered 'not found' for an answerable question")
        elif missing:
            failures.append(f"incorrect: missing expected content {missing}")
        if not refused:
            if not cited:
                failures.append("citation: answer cites no source")
            elif not valid:
                failures.append(f"citation: invalid source number in {cited}")
            elif not supported:
                failures.append("citation: cited sources do not contain the expected evidence")
    else:
        result["correct_refusal"] = refused
        if not refused:
            failures.append("did not refuse an unsupported question")
    return result


# --- aggregation ------------------------------------------------------------

def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _rate(flags: Sequence[bool]) -> float | None:
    return sum(flags) / len(flags) if flags else None


def aggregate(results: Sequence[dict], mode: str) -> dict:
    answerable = [r for r in results if r["answerable"] and "error" not in r]
    unsupported = [r for r in results if not r["answerable"] and "error" not in r]
    full = [r for r in results if "answer" in r]
    ans_full = [r for r in full if r["answerable"]]
    unsup_full = [r for r in full if not r["answerable"]]
    agg: dict[str, Any] = {
        "questions": len(results),
        "answerable": len(answerable),
        "unsupported": len(unsupported),
        "errors": sum(1 for r in results if "error" in r),
        "retrieval": {
            "k": K,
            "recall_at_k": _mean([r["retrieval"]["recall"] for r in answerable]),
            "hit_rate_at_k": _rate([r["retrieval"]["hit"] for r in answerable]),
            "mrr": _mean([r["retrieval"]["reciprocal_rank"] for r in answerable]),
            "mean_top_score_answerable": _mean(
                [r["retrieval"]["top_score"] for r in answerable if r["retrieval"]["top_score"] is not None]
            ),
            "mean_top_score_unsupported": _mean(
                [r["retrieval"]["top_score"] for r in unsupported if r["retrieval"]["top_score"] is not None]
            ),
        },
        "mean_latency_ms": _mean([r["latency_ms"] for r in results if "latency_ms" in r]),
        "by_category": {},
        "evaluated": sum(1 for r in results if r.get("passed") is not None),
        "passed": sum(1 for r in results if r.get("passed")),
    }
    if mode == "full":
        agg["answers"] = {
            "evaluated": len(full),
            "correct_rate": _rate([r["answer_checks"]["correct"] for r in ans_full]),
            "false_refusal_rate": _rate([r["answer_checks"]["false_refusal"] for r in ans_full]),
            "correct_refusal_rate": _rate([r["answer_checks"]["correct_refusal"] for r in unsup_full]),
            "citation_valid_rate": _rate([r["answer_checks"]["citation_valid"] for r in ans_full if not r["answer_checks"]["refused"]]),
            "citation_supported_rate": _rate([r["answer_checks"]["citation_supported"] for r in ans_full if not r["answer_checks"]["refused"]]),
            "numbers_grounded_rate": _rate([r["answer_checks"]["numbers_grounded"] for r in full]),
        }
    for cat in sorted({r["category"] for r in results}):
        rows = [r for r in results if r["category"] == cat]
        agg["by_category"][cat] = {
            "questions": len(rows),
            "evaluated": sum(1 for r in rows if r.get("passed") is not None),
            "passed": sum(1 for r in rows if r.get("passed")),
        }
    return agg


def _failure_stage(question: dict, retrieval: dict, checks: dict | None) -> str | None:
    if question["answerable"] and retrieval["recall"] < 1:
        return "retrieval"
    if checks and checks["failures"]:
        return "generation"
    return None


# --- run --------------------------------------------------------------------

class UsageRecordingClient:
    """Wraps an OpenAI client and tallies `usage` from responses (services are unchanged)."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.usage = {
            "embedding_requests": 0, "embedding_tokens": 0,
            "chat_requests": 0, "chat_prompt_tokens": 0, "chat_completion_tokens": 0,
        }
        self.embeddings = SimpleNamespace(create=self._embed)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))

    def _embed(self, **kwargs):
        response = self._client.embeddings.create(**kwargs)
        self.usage["embedding_requests"] += 1
        usage = getattr(response, "usage", None)
        self.usage["embedding_tokens"] += getattr(usage, "total_tokens", 0) or 0
        return response

    def _chat(self, **kwargs):
        response = self._client.chat.completions.create(**kwargs)
        self.usage["chat_requests"] += 1
        usage = getattr(response, "usage", None)
        self.usage["chat_prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
        self.usage["chat_completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
        return response


@dataclass
class RunContext:
    embedder: EmbeddingService
    store: VectorStore
    generator: GenerationService | None = None  # required for mode="full"
    usage: Callable[[], dict] | None = None


def run_evaluation(
    dataset: dict, ctx: RunContext, mode: str = "retrieval", limit: int | None = None,
    max_consecutive_errors: int = 3,
) -> dict:
    """Run the dataset through the real retrieval (and, in full mode, answer) pipeline.

    API failures are recorded per question and never retried; the run stops early after
    several consecutive failures so a misconfiguration cannot burn requests.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if mode == "full" and ctx.generator is None:
        raise ValueError("full mode needs a generation service")
    settings = get_settings()
    questions = dataset["questions"][:limit] if limit else dataset["questions"]
    started = datetime.now(timezone.utc)
    results: list[dict] = []
    consecutive_errors = 0
    aborted = False
    for q in questions:
        entry = {
            "id": q["id"], "category": q["category"], "question": q["question"],
            "answerable": q["answerable"], "expected_answer": q["expected_answer"],
        }
        t0 = time.perf_counter()
        try:
            if mode == "full":
                rag = answer_question(
                    q["question"], ctx.embedder, ctx.store, ctx.generator, top_k=K
                )
                chunks, answer = rag.sources, rag.answer
            else:
                chunks, answer = retrieve(q["question"], ctx.embedder, ctx.store, top_k=K), None
        except (EmbeddingError, VectorStoreError, GenerationError) as exc:
            # Only the exception type is stored: provider messages may be sensitive.
            entry.update(error=type(exc).__name__, passed=False, failure_stage="error",
                         failures=[f"error: {type(exc).__name__}"])
            results.append(entry)
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                aborted = True
                break
            continue
        consecutive_errors = 0
        entry["latency_ms"] = round((time.perf_counter() - t0) * 1000)
        retrieval = score_retrieval(q, chunks)
        entry["retrieval"] = retrieval
        checks = None
        if answer is not None:
            checks = check_answer(q, answer, retrieval)
            entry.update(answer=answer, answer_checks=checks)
        failures = list(checks["failures"]) if checks else []
        if q["answerable"] and retrieval["recall"] < 1:
            failures.insert(0, f"retrieval: facts missing from top {K}: {retrieval['facts_missing']}")
        entry["failures"] = failures
        entry["failure_stage"] = _failure_stage(q, retrieval, checks)
        # Unsupported questions are only judged once an answer exists (full mode).
        entry["passed"] = (not failures) if (q["answerable"] or answer is not None) else None
        results.append(entry)

    return {
        "id": started.strftime("%Y%m%dT%H%M%SZ") + f"-{mode}",
        "started_at": started.isoformat(),
        "mode": mode,
        "aborted": aborted,
        "dataset": {"version": dataset["version"], "questions": len(dataset["questions"]),
                    "evaluated": len(results)},
        "config": {
            "embedding_model": settings.openai_embedding_model,
            "chat_model": settings.openai_chat_model if mode == "full" else None,
            "k": K,
            "score_threshold": settings.retrieval_score_threshold,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
        },
        "usage": ctx.usage() if ctx.usage else None,
        "aggregate": aggregate(results, mode),
        "results": results,
    }


# --- result files -----------------------------------------------------------

def save_run(run: dict, directory: Path | None = None) -> Path:
    directory = directory or results_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run['id']}.json"
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def list_runs(directory: Path | None = None) -> list[dict]:
    """Run summaries, newest first. Unreadable files are skipped."""
    directory = directory or results_dir()
    runs = []
    for path in directory.glob("*.json") if directory.is_dir() else []:
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
            runs.append(
                {k: run[k] for k in ("id", "started_at", "mode", "aborted", "aggregate", "dataset")}
            )
        except (OSError, ValueError, KeyError):
            logger.warning("Skipping unreadable evaluation result %s", path.name)
    return sorted(runs, key=lambda r: r["started_at"], reverse=True)


def load_run(run_id: str, directory: Path | None = None) -> dict | None:
    if not _RUN_ID.match(run_id):
        return None
    path = (directory or results_dir()) / f"{run_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
