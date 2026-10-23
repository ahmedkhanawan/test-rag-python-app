# CLAUDE.md

Operational instructions for Claude Code sessions on **Test RAG Python App** (demo concept: Company Knowledge Assistant).

## Read first

**Before making any change, read `MASTER_PLAN.md`.** It is the canonical specification. This file only summarizes how to work; if the two ever disagree, `MASTER_PLAN.md` wins.

## Rules

- **Never modify `MASTER_PLAN.md`** unless the user has explicitly approved a specific change (see its Section 48 change-control procedure: explain the proposal, ask, wait for approval).
- **Do not silently make unresolved decisions.** If an implementation needs a decision listed under "Open decisions" below (or in MASTER_PLAN.md Sections 45/46), stop and ask the user. Do not assume a default.
- **Do not add technologies or features** outside the approved plan. Items in MASTER_PLAN.md Section 37 are out of scope for V1.
- **Work one milestone at a time** (MASTER_PLAN.md Section 36). Do not implement future milestones unless explicitly asked.
- Keep the project minimal and portfolio-oriented; prefer the simplest approach that works.
- Be token-efficient: implement and test rather than re-explaining the project; keep reports concise.
- Never commit secrets. API keys come from `.env`; only `.env.example` is committed.
- Commit only when the user asks. Use small, focused commits.

## Confirmed decisions (summary)

Authoritative list: MASTER_PLAN.md Section 44. In use now:

- Python + FastAPI, Pydantic, SQLAlchemy, SQLite (UUID primary keys), pytest, `.env` configuration
- **uv** for Python package/environment management (run backend commands from `backend/` with `uv run`)
- **PyMuPDF** for PDF extraction (PDF is the only V1 format so far)
- **Qdrant** as vector database, always a **separate container** (image `qdrant/qdrant:v1.19.2`): standalone via `scripts/start-qdrant.sh` for development, or as a service in `docker-compose.yml`. Both use `./qdrant_storage`; never run the two at once
- **Docker Compose (approved, M11)**: three services: `qdrant`, `backend` (FastAPI, non-root, SQLite in the `app-data` volume, no published port) and `frontend` (nginx serving the React build and proxying `/api` to the backend, so the browser sees one origin and CORS stays off). `docker compose up --build -d` serves `http://localhost:8080`; details in `docs/deployment.md`
- **Auth (approved, M9)**: one admin account from environment variables (`ADMIN_USERNAME`, Argon2id `ADMIN_PASSWORD_HASH`, `JWT_SECRET`), HS256 JWT with expiry (PyJWT + pwdlib), Bearer token kept in `sessionStorage`. No user table, no OAuth. Chat stays public by design; all other routes except health and login require the admin token
- **Production-quality behavior (M11)**: errors are `{"detail", "request_id"}`; structured/redacted logging (`LOG_FORMAT=text|json`); `ENVIRONMENT=production` fails startup on missing/weak secrets; login throttling and a per-IP rate limit on the public chat endpoint (in-memory, per-process); upload limits; CORS off unless `CORS_ORIGINS` is set; GitHub Actions CI (`.github/workflows/ci.yml`)
- **Colima** is the working Docker runtime on the developer's Mac (context `colima`); Docker Desktop is not used and `lima-docker` is inactive
- **OpenAI APIs**: embeddings `text-embedding-3-small`, generation GPT-5.4 mini (`gpt-5.4-mini`). Both are approved; do not change them
- Frontend: React 19 + Vite, Bootstrap, Bootstrap Icons, React Router, Axios; Vitest + Testing Library; oxlint (no Redux or other state library)
- Source citations, ingestion, and semantic retrieval are core; the assistant must refuse to invent answers when documents lack support
- Citations are application-owned (from retrieved chunks), never produced by the LLM
- Claude Code is the primary implementation tool; Cursor and MCP are not part of V1

## Still open (ask before assuming)

Formats beyond PDF; chunk size/overlap, Top-K, similarity threshold (current values 1000/150/5/none are implementation defaults only, kept configurable and not tuned); streaming mechanism; production relational DB; hosting provider and TLS; visual design; sample document content; branding. The evaluation methodology (M10) is implemented but remains open to refinement. See MASTER_PLAN.md Sections 45-46.

## Current status

Milestones 0-10 are complete, committed and pushed (docs, backend, database, PDF ingestion, embeddings + Qdrant, RAG engine, chat API, React foundation, chat UI, admin panel, evaluation). **Milestone 11 (production quality) is implemented and awaits final verification and commit.** The next milestone is **Milestone 12 - Portfolio polish**; do not start it unless explicitly requested. Known limitations are listed in `docs/deployment.md` (per-process in-memory rate limits, no TLS, single-instance SQLite/Qdrant).

## Prompt/report conventions

Expect prompts structured as OBJECTIVE / SCOPE / REQUIREMENTS / DO NOT / TESTING / COMPLETION REPORT. Honor the DO NOT list strictly. Finish with a concise completion report, including any ambiguity encountered.

## Testing

Run these locally; no real OpenAI or Qdrant is needed (tests use fakes and in-memory Qdrant). Report only relevant failures.

```bash
cd backend && uv run pytest -q                                  # backend
cd frontend && npm test && npm run lint && npm run build        # frontend
```

CI (`.github/workflows/ci.yml`) runs the same checks plus a Docker build. The RAG evaluation (`cd backend && uv run python -m scripts.run_evaluation --mode retrieval|full`) calls OpenAI and costs money: run it only when asked and never retry failed calls. Documentation-only changes are verified by file existence, Markdown formatting, and consistency with `MASTER_PLAN.md` and the code.
