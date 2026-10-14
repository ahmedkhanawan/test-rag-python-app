"""Run the RAG evaluation against the indexed documents.

    uv run python -m scripts.run_evaluation --mode retrieval   # embeddings only
    uv run python -m scripts.run_evaluation --mode full        # + answer generation

Reads evaluation/questions.json, validates its labels against SQLite first (aborting on
any mismatch), and writes evaluation/results/<run id>.json. Nothing is indexed, changed
or deleted. Requests are never retried.
"""

import argparse
import sys

from openai import OpenAI

from app.core.config import get_settings
from app.core.database import get_sessionmaker
from app.rag.evaluation import (
    MODES,
    RunContext,
    UsageRecordingClient,
    load_dataset,
    run_evaluation,
    save_run,
    validate_dataset,
)
from app.services.embeddings import EmbeddingService
from app.services.generation import GenerationService
from app.services.vector_store import VectorStore


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=MODES, default="retrieval")
    parser.add_argument("--limit", type=int, help="only the first N questions")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is not configured.")
        return 2

    dataset = load_dataset()
    with get_sessionmaker()() as session:
        problems = validate_dataset(dataset, session)
    if problems:
        print("Dataset does not match the indexed data; not running:")
        for p in problems:
            print(f"  - {p}")
        return 1

    client = UsageRecordingClient(OpenAI(api_key=settings.openai_api_key))
    ctx = RunContext(
        embedder=EmbeddingService(client=client),
        store=VectorStore(),
        generator=GenerationService(client=client) if args.mode == "full" else None,
        usage=lambda: dict(client.usage),
    )
    run = run_evaluation(dataset, ctx, mode=args.mode, limit=args.limit)
    path = save_run(run)

    agg = run["aggregate"]
    r = agg["retrieval"]
    print(f"Run {run['id']} -> {path}")
    print(f"questions {agg['questions']} (answerable {agg['answerable']}, unsupported {agg['unsupported']}), "
          f"errors {agg['errors']}, passed {agg['passed']}")
    print(f"Recall@{r['k']} {pct(r['recall_at_k'])} | Hit@{r['k']} {pct(r['hit_rate_at_k'])} | MRR {r['mrr']:.3f}"
          if r["mrr"] is not None else "no answerable questions evaluated")
    if "answers" in agg:
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in agg["answers"].items()})
    print("usage:", run["usage"])
    return 1 if run["aborted"] else 0


if __name__ == "__main__":
    sys.exit(main())
