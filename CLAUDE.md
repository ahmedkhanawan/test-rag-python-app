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
- **Qdrant** as vector database, running as a **separate Docker container** in development (`scripts/start-qdrant.sh`, image `qdrant/qdrant:v1.19.2`); the Python app is not containerized yet
- **Colima** is the working Docker runtime on the developer's Mac (context `colima`); Docker Desktop is not used and `lima-docker` is inactive
- **OpenAI APIs**: embeddings `text-embedding-3-small`, generation GPT-5.4 mini (`gpt-5.4-mini`). Both are approved; do not change them
- React, Bootstrap, Bootstrap Icons, React Router, Axios (no Redux initially) for the later frontend
- Source citations, ingestion, and semantic retrieval are core; the assistant must refuse to invent answers when documents lack support
- Citations are application-owned (from retrieved chunks), never produced by the LLM
- Claude Code is the primary implementation tool; Cursor and MCP are not part of V1

## Still open (ask before assuming)

Formats beyond PDF; chunk size/overlap, Top-K, similarity threshold (current values are implementation defaults only, kept configurable); auth/JWT details; streaming mechanism; production relational DB; application Docker Compose topology; hosting provider; evaluation methodology; React component/page architecture; visual design; admin dashboard metrics; sample document content; branding. See MASTER_PLAN.md Sections 45-46.

## Current status

Milestones 0-5 are completed and committed (docs, backend foundation, database, PDF ingestion, embeddings + Qdrant, RAG engine). The current milestone is **Milestone 6 - Chat API** (`POST /api/chat`, conversation persistence, sources). Do not implement later milestones unless explicitly requested.

## Prompt/report conventions

Expect prompts structured as OBJECTIVE / SCOPE / REQUIREMENTS / DO NOT / TESTING / COMPLETION REPORT. Honor the DO NOT list strictly. Finish with a concise completion report, including any ambiguity encountered.

## Testing

Run tests locally (`uv run pytest -q` from `backend/`; no real OpenAI or Qdrant needed) and report only relevant failures. Documentation-only milestones are verified by file existence, Markdown formatting, and consistency with `MASTER_PLAN.md`.
