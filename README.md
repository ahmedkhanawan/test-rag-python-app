# Test RAG Python App

A minimal, portfolio-oriented **Company Knowledge Assistant**: a RAG application where users ask natural-language questions about (fictional) company documents and receive answers grounded in those documents, with source citations. If the documents do not contain the answer, the assistant says so instead of inventing one.

> **Status:** Milestones 0–10 are complete (backend, ingestion, retrieval, chat, admin panel, evaluation). Milestone 11 (production quality: error handling, logging, security, Docker, CI) is implemented and pending final verification. Milestone 12 (portfolio polish: screenshots, final write-up) is next. The canonical specification is [`MASTER_PLAN.md`](MASTER_PLAN.md).

## Features

- **Chat** (public): ask a question, get a grounded answer with structured source citations (document, page, section, relevance, chunk text). Conversations are listed in the browser; the server stores messages but not the list or the sources.
- **Document ingestion**: PDF upload, text extraction (PyMuPDF), page-bounded chunking, `text-embedding-3-small` embeddings, storage in Qdrant.
- **Admin panel** (single admin, JWT): dashboard, document list with status and chunk counts, upload, delete, re-index, retrieval playground (chunks and scores, no LLM call).
- **Evaluation**: a 30-question dataset with retrieval metrics (Recall@5, Hit@5, MRR) and deterministic answer checks, viewable at `/admin/evaluation`. See [`docs/evaluation.md`](docs/evaluation.md).
- **Production basics**: consistent error bodies with request IDs, structured redacted logs, login throttling, a per-IP rate limit on public chat, upload limits, fail-fast configuration, Docker Compose, GitHub Actions CI.

## Technology

| Area | Choice |
| --- | --- |
| Backend | Python 3.14, FastAPI, Pydantic, SQLAlchemy, SQLite, pytest, uv |
| RAG | PyMuPDF, OpenAI `text-embedding-3-small` and `gpt-5.4-mini`, Qdrant (separate container) |
| Auth | single admin from environment variables, Argon2id, HS256 JWT |
| Frontend | React 19, Vite, Bootstrap, Bootstrap Icons, React Router, Axios, Vitest |
| Delivery | Docker Compose (Qdrant + backend + nginx), GitHub Actions; developed with Colima |

## Run locally (development)

Prerequisites: [uv](https://docs.astral.sh/uv/), Node.js 24, Docker (Colima works; Docker Desktop is not required).

```bash
cp .env.example backend/.env        # then set OPENAI_API_KEY and the admin variables (see below)
./scripts/start-qdrant.sh           # Qdrant on :6333, data in ./qdrant_storage
cd backend && uv sync && uv run python -m scripts.init_db && uv run uvicorn app.main:app --port 8000
cd frontend && npm ci && npm run dev    # http://localhost:5173, /api is proxied to :8000
```

Admin login needs `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` (from `cd backend && uv run python -m scripts.hash_password`, keep it in single quotes) and `JWT_SECRET` (`openssl rand -hex 32`). Without them chat still works and admin login returns 503. `backend/.env` is git-ignored; never commit real secrets.

Then upload a PDF at `/admin/documents` and ask about it at `/chat`.

## Run with Docker Compose

```bash
docker compose up --build -d        # http://localhost:8080
```

Stop the dev Qdrant container first (`docker stop company-knowledge-qdrant`); both use `./qdrant_storage`. Prerequisites, data migration, logs and security notes: [`docs/deployment.md`](docs/deployment.md).

## Test

```bash
cd backend && uv run pytest -q                              # no OpenAI or Qdrant needed
cd frontend && npm test && npm run lint && npm run build
```

CI runs the same checks plus a Docker build on every push to `main` and every pull request.

## Evaluate

```bash
cd backend
uv run python -m scripts.run_evaluation --mode retrieval    # embeddings only (cheap)
uv run python -m scripts.run_evaluation --mode full         # also generates answers
```

These call OpenAI and need the documents referenced by `evaluation/questions.json` to be indexed; the runner validates that first. Saved runs live in `evaluation/results/`. Scores depend on that small fictional corpus and are not a general quality claim.

## Documentation

- [`MASTER_PLAN.md`](MASTER_PLAN.md) — canonical project plan
- [`CLAUDE.md`](CLAUDE.md) — instructions for Claude Code sessions
- [`docs/architecture.md`](docs/architecture.md) — architecture
- [`docs/rag-pipeline.md`](docs/rag-pipeline.md) — RAG pipeline
- [`docs/evaluation.md`](docs/evaluation.md) — evaluation method and limitations
- [`docs/deployment.md`](docs/deployment.md) — Docker (Colima), configuration, logging, security, CI
- [`docs/qdrant.md`](docs/qdrant.md) — local Qdrant

## Roadmap

Development proceeds milestone by milestone (0–12); see `MASTER_PLAN.md` Section 36. Deferred or out of scope for V1: streaming answers, formats beyond PDF, multi-user accounts, server-side conversation history, hybrid search and reranking.
