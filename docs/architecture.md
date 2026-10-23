# Architecture

High-level architecture of the Company Knowledge Assistant. Source: `MASTER_PLAN.md` Sections 9–15, 30–32. It describes the implemented system (Milestones 0–11; Milestone 11 is pending final verification); hosting and production database choices remain open.

## Overview

```text
                    ┌─────────────────────────┐
                    │       React Frontend    │
                    │  Chat │ Documents │     │
                    │       Admin Dashboard   │
                    └────────────┬────────────┘
                                 │
                              REST API
                                 │
                    ┌────────────▼────────────┐
                    │         FastAPI         │
                    │  Chat API               │
                    │  Document API           │
                    │  Admin API              │
                    └────────────┬────────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               │                 │                 │
        ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
        │ RAG Engine  │   │ SQLite / DB │   │ OpenAI API  │
        └──────┬──────┘   └─────────────┘   └─────────────┘
               │
        ┌──────▼──────┐
        │   Qdrant    │
        │ Vector DB   │
        └─────────────┘
```

## Components

- **React frontend** — React 19 + Vite, Bootstrap, React Router and Axios. Public pages: Home, Chat (conversation list kept in browser `localStorage`). Admin pages behind login: Dashboard, Documents (upload, delete, re-index), Retrieval Playground, Evaluation. Settings and a server-side conversations view are not built.
- **FastAPI backend** — REST API with automatic OpenAPI/Swagger docs. Routes under `/api`: `health`, `chat`, `auth/login` (public) and `documents`, `documents/upload`, `documents/{id}` (DELETE), `documents/{id}/reindex`, `retrieval/search`, `admin/stats`, `admin/evaluation/runs[/{id}]` (admin JWT). Cross-cutting: request-ID/access-log middleware, consistent error bodies, config validation, login throttling.
- **RAG engine** — ingestion, chunking, embedding, retrieval, prompt assembly, generation. See [rag-pipeline.md](rag-pipeline.md).
- **Relational database** — SQLite (SQLAlchemy, UUID keys) for documents, chunks, conversations and messages. A `query_logs` table exists but nothing writes to it yet.
- **Qdrant** — stores embedded document chunks and serves semantic search.
- **OpenAI API** — `text-embedding-3-small` embeddings and `gpt-5.4-mini` generation. Configured via environment, never hard-coded; keys are not committed.
- **Deployment** — `docker-compose.yml` runs three services: `qdrant`, `backend` and `frontend` (nginx serving the build and proxying `/api`, so the browser uses a single origin). See [deployment.md](deployment.md).

## Backend layout

```text
backend/
├── app/
│   ├── main.py
│   ├── api/        # health, chat, auth, admin, documents, retrieval, evaluation, deps
│   ├── core/       # config, database, security, logging, middleware, errors, ratelimit
│   ├── models/     # Document, Chunk, Conversation, Message, QueryLog
│   ├── services/   # ingestion, chunking, embeddings, indexing, vector_store, retrieval, generation
│   └── rag/        # pipeline, prompts, evaluation
├── scripts/        # init_db, hash_password, check_qdrant, run_evaluation
├── tests/
└── pyproject.toml
```

## Decisions

**Confirmed:** Python + FastAPI, React + Bootstrap, Qdrant (separate container), OpenAI APIs, SQLite, PyMuPDF (PDF only), uv, single-admin JWT auth, Docker Compose with an nginx same-origin proxy, Colima for local Docker.

**Still open:** formats beyond PDF, chunking and retrieval parameters (defaults 1000/150/Top-K 5, no threshold), streaming, production database, hosting and TLS, visual design, branding.

## Out of scope for V1

Multi-agent, MCP server, GraphRAG, knowledge graphs, hybrid BM25, reranking, Kubernetes, microservices, Redis, Celery, Kafka, complicated OAuth, multi-tenancy, billing, real-time collaboration, mobile app.
