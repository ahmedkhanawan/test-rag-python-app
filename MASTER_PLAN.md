# MASTER_PLAN.md
# Test RAG Python App — Canonical Project Plan

> **Status:** Milestones 0–10 completed and pushed; Milestone 11 implementation and isolated Compose verification completed, final commit/push pending; Milestone 12 next  
> **Purpose:** Canonical source of truth for the Test RAG Python App project  
> **Last updated:** 2026-10-16  
> **Project name:** Test RAG Python App  
> **Demo application concept:** Company Knowledge Assistant

---

## 1. Purpose of This Document

This file is the canonical source of truth for the Test RAG Python App project.

It captures the implementation plan and decisions explicitly agreed upon in the project discussion so far, including:

- project goals
- intended portfolio/demo scope
- architecture
- technology choices
- RAG approach
- frontend/backend direction
- document handling
- deployment strategy
- AI-assisted development workflow
- token/usage optimization
- confirmed decisions
- proposals that have not yet been approved
- open questions
- current implementation status

### Change-control rule

This document must **not be automatically modified during future discussions**.

If a future discussion introduces a proposed change to:

- project goals
- architecture
- technology choices
- RAG approach
- approved scope
- implementation strategy
- other significant project decisions

the proposed change must first be explained to the user and receive **explicit approval**.

Only after explicit approval should `MASTER_PLAN.md` be updated.

During future implementation work, the latest approved version of this file should be treated as the primary project reference. The ongoing conversation may provide additional temporary context, but it must not silently override an approved decision in this document.

---

# 2. Project Goal

Build a **professional-looking, minimal viable RAG application** in Python that can be published as a public GitHub portfolio project.

The application should demonstrate practical competency in:

- Python
- FastAPI
- RAG
- LLM integration
- embeddings
- vector databases
- document ingestion
- prompt engineering
- ReactJS
- Bootstrap
- API design
- testing
- Docker
- Git/GitHub
- modern AI-assisted software development

The project should be:

1. small enough to finish,
2. sophisticated enough to demonstrate modern AI engineering skills,
3. understandable enough that the developer can explain the architecture in an interview,
4. visually polished enough to function as a portfolio demo,
5. useful to both technical and non-technical reviewers.

---

# 3. Demo Concept — Confirmed Decision

## Company Knowledge Assistant

The selected demo concept is **Option B — Company Knowledge Assistant**.

The application will simulate an internal company knowledge system in which users can ask questions about company documentation.

This was selected because interviewers and HR personnel may not be technical. A company-policy-oriented RAG application makes the RAG concept easy to understand and test.

A reviewer should be able to:

1. open the application,
2. see company documents,
3. ask a natural-language question,
4. receive an answer grounded in those documents,
5. see the sources used to produce the answer.

---

# 4. Example Company Documents

The planned fictional company documentation may include documents such as:

- Employee Handbook
- HR Policy
- Leave & Attendance Policy
- Remote Work Policy
- IT & Security Policy
- Engineering Handbook
- Benefits & Compensation Policy
- Code of Conduct
- Expense Policy

These are examples discussed during planning. The exact final document set has not yet been finalized.

The documents are expected to be fictional/demo material rather than real confidential company documents.

---

# 5. Primary User Experience

The main user-facing feature is an AI assistant.

Example interaction:

> **User:** How many annual leave days do employees receive?

The assistant should answer using the indexed company documents and provide source information.

Example conceptual response:

> According to the company's Leave Policy, employees receive the specified annual leave allowance subject to the policy conditions.

Then:

```text
Sources
────────────────────────
Leave Policy.pdf
Page 3

Employee Handbook.pdf
Page 18
```

The exact wording and source presentation will be implemented later.

---

# 6. Core RAG Behavior

The intended RAG pipeline is:

```text
Document
    ↓
Parse
    ↓
Clean
    ↓
Chunk
    ↓
Attach Metadata
    ↓
Generate Embeddings
    ↓
Store in Qdrant
    ↓
User Question
    ↓
Generate Query Embedding
    ↓
Semantic Retrieval
    ↓
Retrieve Top-K Chunks
    ↓
Optional Similarity Threshold
    ↓
Assemble Context
    ↓
Prompt LLM
    ↓
Generate Grounded Answer
    ↓
Return Answer + Citations
```

The application should not simply behave as a generic LLM chatbot.

The answer should be grounded in the retrieved company documentation.

---

# 7. Hallucination / Grounding Rule

A central RAG behavior is:

> If the available documents do not contain enough information to answer a question, the assistant should say that it cannot find sufficient information in the available company documents rather than inventing an answer.

Example:

```text
I couldn't find information about this topic
in the available company documents.
```

This is an important part of demonstrating genuine RAG behavior.

---

# 8. Source Citations — Confirmed Requirement

Answers should expose the documents/chunks used to construct the response.

Each chunk should carry sufficient metadata to identify its origin.

Planned metadata includes:

```python
{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "document_name": "Employee Handbook.pdf",
    "page_number": 18,
    "chunk_index": 42,
    "section": "Remote Work Policy"
}
```

The relational database schema is approved as follows:

- `documents.id`: UUID primary key
- `chunks.id`: UUID primary key; `document_id` is a UUID foreign key to `documents.id`
- `conversations.id`: UUID primary key
- `messages.id`: UUID primary key; `conversation_id` is a UUID foreign key to `conversations.id`
- `query_logs.id`: UUID primary key; relationships should use UUID foreign keys where applicable

UUIDs are used to provide globally unique identifiers and keep the SQL ↔ Qdrant relationship clean. A Qdrant point representing a chunk should use the chunk UUID as its point identifier (or an equivalent direct UUID mapping).

The UI should eventually display information such as:

```text
Sources

Employee Handbook.pdf
Page 18
Remote Work Policy
```

The final citation UX is an implementation detail still to be determined.

---

# 9. Technology Stack — Confirmed Choices

## Backend

- **Python**
- **FastAPI**
- **Pydantic**
- **SQLAlchemy**
- **SQLite initially**
- **pytest**
- `.env`-based configuration

## Vector database

- **Qdrant**

Qdrant replaces the previously considered ChromaDB choice.

## LLM

- **OpenAI APIs**

The application should use OpenAI's APIs for LLM access rather than Claude APIs.

Reason for this decision:

- the user expects their ChatGPT subscription to remain available,
- the user's Claude subscription may expire,
- the portfolio demo should therefore not depend on the continued availability of the user's Claude subscription.

The approved OpenAI model is **GPT-5.4 mini**.

## Embeddings

- Embeddings are required.
- The approved embedding provider/model is **OpenAI `text-embedding-3-small`**.

## Document parsing

- **PyMuPDF** is the planned PDF parsing technology.

V1 supports PDF only. Do not add TXT, Markdown, DOCX, or other formats unless there is a concrete requirement and explicit approval.

## Frontend

- **ReactJS**
- **Bootstrap**
- **Bootstrap Icons**
- **React Router**
- **Axios**

ReactJS is a confirmed requirement specifically so the project can demonstrate ReactJS experience.

Bootstrap remains part of the frontend stack.

Redux is not planned initially.

## Containerization

- **Docker**
- Docker Compose is expected for the final application, but Docker is deliberately not part of the initial implementation phase.
- During development, Qdrant runs in a separate Docker container.
- On the user's Intel MacBook Pro/macOS Ventura development machine, the working Docker runtime is **Colima** rather than Docker Desktop or Lima.

## Version control

- **Git**
- **GitHub**

The final repository is intended to be public and portfolio-ready.

---

# 10. Package Management — Confirmed Decision

The project will use **uv** for Python package and environment management.

The user explicitly approved uv as the project package manager before implementation.

Do not silently change this decision in future implementation work. Any replacement package-management approach requires explicit approval.

---

# 11. Planned Architecture

The conceptual architecture is:

```text
                    ┌─────────────────────────┐
                    │       React Frontend    │
                    │                         │
                    │  Chat │ Documents │     │
                    │       Admin Dashboard   │
                    └────────────┬────────────┘
                                 │
                              REST API
                                 │
                    ┌────────────▼────────────┐
                    │       FastAPI           │
                    │                         │
                    │  Chat API               │
                    │  Document API           │
                    │  Admin API              │
                    └────────────┬────────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               │                 │                 │
        ┌──────▼──────┐   ┌──────▼──────┐   ┌─────▼──────┐
        │ RAG Engine  │   │ SQLite / DB  │   │ OpenAI API │
        │             │   │              │   │             │
        └──────┬──────┘   └──────────────┘   └─────────────┘
               │
        ┌──────▼──────┐
        │   Qdrant    │
        │ Vector DB   │
        └─────────────┘
```

This diagram describes logical application components. The approved local production-style deployment topology is three services: Qdrant, FastAPI backend, and frontend served by Nginx. Nginx serves the React build and proxies same-origin `/api` requests to FastAPI. This does not make the application a microservices architecture.

---

# 12. Backend Project Structure — Proposed

The following structure was proposed:

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── chat.py
│   │   ├── documents.py
│   │   ├── retrieval.py
│   │   └── admin.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   └── logging.py
│   │
│   ├── models/
│   │
│   ├── services/
│   │   ├── ingestion.py
│   │   ├── chunking.py
│   │   ├── embeddings.py
│   │   ├── retrieval.py
│   │   └── generation.py
│   │
│   └── rag/
│       ├── pipeline.py
│       ├── prompts.py
│       └── evaluation.py
│
├── tests/
├── scripts/
└── pyproject.toml
```

This is a **proposed structure**, not an immutable decision. It should be refined only with explicit approval if the architecture changes materially.

---

# 13. Frontend Project Structure — Proposed

A conceptual React structure was discussed:

```text
frontend/
├── src/
│   ├── components/
│   ├── pages/
│   ├── layouts/
│   ├── services/
│   ├── hooks/
│   ├── context/
│   ├── utils/
│   └── App.jsx
│
├── public/
└── package.json
```

The React architecture is implemented. Treat the current `frontend/src` structure and `CLAUDE.md` as the implementation reference; refactoring is allowed when it improves clarity but should not add unnecessary state-management or framework complexity.

---

# 14. Planned Frontend Pages

## Initial UI

The planned initial pages are:

1. Login
2. Dashboard
3. AI Assistant / Chat
4. Documents

## Later UI

Potential additional pages:

5. Retrieval Playground
6. Evaluation
7. Settings
8. Conversations

The exact page sequence may be refined during implementation, but the goal is to avoid unnecessary frontend complexity.

---

# 15. UI / UX Direction

The application should look like a small professional SaaS/internal company application rather than a basic tutorial chatbot.

Conceptual layout:

```text
┌─────────────────────────────────────────────────────────┐
│ Company Knowledge Assistant              Admin ▼        │
├───────────────┬─────────────────────────────────────────┤
│ Dashboard     │                                         │
│ Ask Assistant │          Chat Area                      │
│ Documents     │                                         │
│ Retrieval     │                                         │
│ Evaluations   │                                         │
│ Settings      │                                         │
└───────────────┴─────────────────────────────────────────┘
```

The final visual design has not yet been specified.

---

# 16. Document Management

The administrator should eventually be able to:

- upload documents,
- inspect document status,
- delete documents,
- re-index/reprocess documents.

Conceptual ingestion lifecycle:

```text
Upload
  ↓
Extract text
  ↓
Clean
  ↓
Chunk
  ↓
Generate embeddings
  ↓
Store vectors
  ↓
READY
```

A document should have a visible status such as:

```text
READY
```

V1 document ingestion is synchronous in the backend request flow; no separate worker/queue is used. This is intentional for the small portfolio scope. Background jobs and task queues remain out of scope unless a future approved change justifies them.

---

# 17. Initial Document Format Scope — V1 Decision

V1 supports **PDF only**, parsed with PyMuPDF. TXT, Markdown, and DOCX were considered but are not V1 requirements. Additional formats are out of scope unless a concrete requirement is raised and explicitly approved.

---

# 18. Chunking

Chunking is a core part of the ingestion pipeline.

Candidate configuration discussed:

```text
Chunk size: 800
Chunk overlap: 100
```

These values were examples/configuration ideas, **not confirmed final parameters**.

The implementation should make chunking configurable rather than permanently hard-code an unapproved value.

---

# 19. Retrieval

The initial retrieval design is intentionally simple:

```text
User question
    ↓
Query embedding
    ↓
Qdrant similarity search
    ↓
Top K chunks
    ↓
Optional similarity threshold
    ↓
Context assembly
```

Candidate configuration discussed:

```text
Top K = 5
Similarity threshold = 0.70
```

These are **proposed starting values**, not final approved values.

Advanced retrieval techniques such as the following are deliberately excluded from V1:

- hybrid BM25 search
- sophisticated reranking
- GraphRAG
- knowledge graphs
- multi-agent retrieval

They may be considered later if explicitly approved.

---

# 20. RAG Configuration

A settings/admin interface was proposed with parameters such as:

```text
LLM provider
LLM model
Temperature
Max tokens

Embedding model

Top K
Chunk size
Chunk overlap
Similarity threshold
```

The final list of configurable settings has not yet been approved.

---

# 21. Chat API

A core FastAPI endpoint is expected to be similar to:

```text
POST /api/chat
```

The chat system should eventually support:

- user question
- RAG retrieval
- grounded response
- citations/sources
- conversation persistence
- conversation history

Additional API routes proposed include:

```text
POST   /api/documents/upload
GET    /api/documents
DELETE /api/documents/{id}

POST   /api/retrieval/search

GET    /api/conversations
GET    /api/conversations/{id}

GET    /api/admin/stats
GET    /api/admin/logs
```

These routes are proposed and may be adjusted during implementation.

FastAPI's automatic OpenAPI/Swagger documentation should be retained as part of the backend.

---

# 22. Conversation History

A conversation model was proposed conceptually:

```text
Conversation
    ├── User message
    ├── Assistant response
    ├── Sources
    └── Timestamp
```

The UI may provide:

```text
New Conversation

Previous conversations:
- Leave policy
- Remote work
- Security requirements
- Employee benefits
```

The exact database schema and conversation UX remain implementation details.

---

# 23. Streaming Responses

Streaming responses were identified as a desirable professional feature.

The intended UX is for the assistant's response to appear progressively rather than waiting for the entire response.

True token-by-token or progressive response streaming is **not implemented in V1**. The chat UI currently submits a request and displays the completed response. Streaming may be added during portfolio polish only if it is worthwhile; it is not required to close Milestone 11.

---

# 24. Retrieval Playground

A retrieval-testing interface was proposed.

Conceptually:

```text
Question:
[ What is the remote work policy? ]

Top K:
[ 5 ]

Similarity threshold:
[ 0.70 ]

[ Search ]

Results

#1  Score: 0.91
Employee Handbook.pdf
Page 18

#2  Score: 0.87
Remote Work Policy.pdf
Page 3
```

This is intended to demonstrate the distinction between:

- retrieval,
- context selection,
- final answer generation.

The retrieval playground is implemented in the admin area. Its current UI and API behavior are the V1 baseline; refinements can be made during portfolio polish without changing the core architecture.

---

# 25. Admin Dashboard

A dashboard was proposed with high-level system statistics such as:

```text
Documents
Chunks
Queries
Average latency
```

A possible expanded status view:

```text
API                 Online
Database            Online
Vector Store        Online
LLM                 Connected
Embedding Service   Connected
```

The current dashboard provides document/chunk/conversation/message counts and document-status breakdowns. Keep this as the V1 baseline; additional metrics or deeper service-health checks are optional polish, not a blocker.

---

# 26. Evaluation

Evaluation is an important planned feature because the goal is to demonstrate actual RAG engineering rather than merely build a chatbot.

A possible dataset:

```text
evaluation/
    questions.json
```

Example:

```json
{
  "question": "How many annual leave days do employees receive?",
  "expected_sources": [
    "Leave Policy.pdf"
  ]
}
```

Potential evaluation metrics discussed:

- retrieval accuracy
- answer relevance
- faithfulness
- average latency

A conceptual dashboard could show:

```text
Questions                 25
Retrieval accuracy        88%
Answer relevance          92%
Faithfulness              94%
Average latency           1.7 sec
```

These numbers are illustrative only and must never be presented as actual results until measured.

The initial evaluation methodology is implemented as described in Milestones 10 and 47. Further metrics or dataset expansion are optional; do not describe the initial 30-question corpus as proof of general RAG quality.

---

# 27. Logging and Observability

Backend logging is planned.

A conceptual query log:

```text
Timestamp
Question
Retrieved chunks
Latency
Model
```

A possible admin log view was proposed.

Exact logging implementation and retention policy remain open.

---

# 28. Authentication

A simple authentication layer was proposed.

Potential approach:

- `/login`
- JWT
- protected API routes
- protected React routes

The intention is **not** to build enterprise-grade identity management.

Approved and implemented V1 authentication: one administrator configured through environment variables (`ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `JWT_SECRET`, and `JWT_EXPIRE_MINUTES`); Argon2id password hashing; JWT bearer authentication; protected admin APIs and React routes; token storage in `sessionStorage` with an in-memory fallback. Public chat and health endpoints remain public. This is intentionally not enterprise identity management or multi-user authorization. Login throttling and public chat rate limiting are implemented in memory per backend process. Chat defaults to 20 requests per client IP per 60 seconds; `CHAT_RATE_LIMIT_REQUESTS=0` disables the chat limit. Over-limit responses return 429 with `Retry-After` and a request ID; blocked requests do not reach OpenAI or count against the active window. Both login and chat limits are single-process safeguards, not shared/distributed controls.

---

# 29. Database Strategy

SQLite is the planned initial relational database.

PostgreSQL was mentioned as a possible later production choice.

The initial project should avoid unnecessary infrastructure complexity.

SQLite is the approved relational database for V1, including the local Compose demo. A different database may be considered only if a real deployment requirement justifies it.

---

# 30. Qdrant Strategy

Qdrant is the confirmed vector database.

The application should store embedded document chunks in Qdrant and retrieve semantically relevant chunks for user queries.

The approved development deployment is **Qdrant in a separate Docker container**, independent from the Python application containerization. This keeps the vector database isolated and allows the application to connect to Qdrant over its service endpoint.

The verified local development setup uses **Colima** as the Docker runtime on the user's Intel MacBook Pro running macOS Ventura. The active Docker context is `colima`; Docker Desktop is not used, and the previously configured `lima-docker` context is not the working runtime. The current development Qdrant image is pinned to `qdrant/qdrant:v1.19.2`.

Qdrant Cloud or another production deployment model may be considered later if needed, but it requires explicit approval if it materially changes architecture or cost.

---

# 31. OpenAI API Strategy

OpenAI APIs are the confirmed LLM integration choice.

The application should be designed so that the model/provider configuration is not unnecessarily hard-coded throughout the codebase.

The approved model is **GPT-5.4 mini** and the approved embedding model is **text-embedding-3-small**.

API keys must be loaded through environment configuration and must not be committed to GitHub.

A `.env.example` file is planned.

---

# 32. Docker Strategy

Docker is planned for application containerization later, but it should **not** be the first application implementation step. The approved exception is that Qdrant may run in its own separate Docker container during development.

### Verified local Docker development environment

The user's working Docker environment is: **Docker CLI 29.2.1 + Colima + Docker context `colima`** on an Intel MacBook Pro running macOS Ventura via OCLP. Colima uses macOS Virtualization.Framework with x86_64 architecture and virtiofs. Docker Desktop is not used. Lima is not the active runtime.

Typical startup/check sequence:

```text
colima start
docker context use colima
docker info
```

The Qdrant development container runs separately from the application containerization effort. Its current verified image is `qdrant/qdrant:v1.19.2`, exposed on port 6333 with persistent development storage under `./qdrant_storage/`. Qdrant 1.19.2 has been successfully started and accessed by the Python application through this setup.

Preferred sequence:

```text
Local development
       ↓
Working backend
       ↓
Working RAG
       ↓
Working React UI
       ↓
Testing
       ↓
Dockerization
       ↓
Deployment configuration
```

This is intentional to avoid debugging application problems and container problems simultaneously.

Approved application Compose topology: three services—Qdrant, FastAPI backend, and Nginx serving the built React frontend. Nginx proxies `/api` to the backend, so the browser uses same-origin API requests and CORS is disabled by default. The local development Qdrant container and Compose Qdrant service share the same default storage path; stop the development container before starting Compose. See `docs/deployment.md` for operational steps. The isolated scratch-copy `docker compose up` verification has been completed and reported successful; it is distinct from the earlier image-build/temporary-network tests. The verification used a separate database volume and Qdrant storage, and the original database/Qdrant storage hashes were unchanged afterward.

---

# 33. Deployment Strategy

The project should ultimately be suitable for public GitHub presentation and potentially a deployed demo.

Deployment has not yet been specified to a particular hosting provider.

The project should be prepared for:

- environment variables,
- Docker,
- production configuration,
- API/frontend separation as appropriate,
- secure handling of API keys.

No cloud hosting provider has been selected. The committed deployment target for V1 is a local Docker Compose setup suitable for demonstration and evaluation. A public hosted deployment is optional and should be chosen only during portfolio polish if it adds value within the time/budget constraints.

---

# 34. GitHub Repository Structure — Proposed

The proposed final repository structure is:

```text
company-knowledge-assistant/
│
├── backend/
│   ├── app/
│   ├── tests/
│   ├── scripts/
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
├── documents/
│   └── sample/
│
├── evaluation/
│   ├── questions.json
│   └── results/
│
├── docs/
│   ├── architecture.md
│   ├── rag-pipeline.md
│   └── evaluation.md
│
├── screenshots/
│
├── .env.example
├── docker-compose.yml
├── README.md
└── LICENSE
```

This structure is proposed and may be refined during implementation.

---

# 35. GitHub README / Portfolio Requirements

The final public repository should explain:

- what the application does,
- why it exists,
- architecture,
- RAG pipeline,
- technology stack,
- local installation,
- environment configuration,
- how to run it,
- how to upload documents,
- how retrieval works,
- how citations work,
- evaluation approach,
- screenshots,
- known limitations,
- future improvements.

An architecture diagram and screenshots are planned portfolio assets.

---

# 36. Development Milestones — Approved Overall Sequence

The agreed implementation sequence is approximately:

## Milestone 0 — Project specification

Create:

- `CLAUDE.md`
- `README.md`
- architecture documentation

No substantial application implementation yet.

## Milestone 1 — Backend foundation

Implement:

- Python project
- FastAPI
- configuration
- logging
- health endpoint
- testing foundation

## Milestone 2 — Database

Implemented the initial relational models:

- Document
- Chunk
- Conversation
- Message
- QueryLog

Initial SQLAlchemy schemas are implemented with UUID-based core identifiers, timestamps, relationships, constraints, and SQLite foreign-key behavior. Future schema evolution remains possible if later milestones require it.

## Milestone 3 — Document ingestion

Implemented:

```text
PDF
 ↓
Page-by-page text extraction
 ↓
Cleaning
 ↓
Deterministic page-bounded chunking
 ↓
Metadata
 ↓
SQLite persistence
```

Implementation uses PyMuPDF, configurable character-based chunking, 1-based page numbers, optional PDF outline/section metadata, and document status transitions including failure handling.

## Milestone 4 — Embeddings + Qdrant — COMPLETED

Implemented:

```text
Chunk
 ↓
OpenAI embedding abstraction
 ↓
Qdrant
 ↓
Semantic retrieval
```

Implemented components include:

- OpenAI `text-embedding-3-small` embedding service
- batched embedding requests with order preservation
- Qdrant vector-store abstraction
- collection creation and vector-size validation
- UUID chunk IDs used as Qdrant point IDs
- citation metadata stored in Qdrant payloads
- indexing service
- retrieval service with configurable Top-K and optional score threshold
- Qdrant connectivity check
- local Qdrant startup documentation/script
- fake/in-memory tests for application-level behavior

Verification completed:

- 48 automated tests pass
- real Qdrant 1.19.2 container verified through Colima
- real collection creation, vector upsert, search, payload retrieval, and score-threshold behavior verified against Qdrant
- no real OpenAI API call was made during this milestone verification

The exact final retrieval Top-K and similarity threshold remain implementation defaults rather than permanent project decisions.

## Milestone 5 — RAG engine — COMPLETED

Implemented:

```text
Question
 ↓
Retrieval
 ↓
Context
 ↓
Prompt
 ↓
OpenAI API
 ↓
Answer + citations
```

This is the central RAG milestone.

## Milestone 6 — Chat API — COMPLETED

Implemented:

- chat endpoint
- conversation persistence
- sources/citations

## Milestone 7 — React application — COMPLETED

Implemented:

- React
- Bootstrap
- routing
- API client
- application layout
- authentication foundation

## Milestone 8 — Chat UI — COMPLETED

Implemented:

- conversation list
- chat
- streaming
- sources
- new conversation

## Milestone 9 — Admin panel — COMPLETED

Implemented:

- dashboard
- documents
- upload
- delete
- re-index
- retrieval playground

## Milestone 10 — Evaluation — COMPLETED

Implemented:

- evaluation dataset
- retrieval metrics
- answer evaluation
- evaluation UI

## Milestone 11 — Production quality — IMPLEMENTED AND LOCALLY VERIFIED; COMMIT/PUSH PENDING

Implemented/reported:

- error handling
- logging
- security
- tests
- Docker
- environment configuration
- CI

## Milestone 12 — Portfolio polish

Finalize:

- README
- architecture diagram
- screenshots
- demo data
- setup instructions
- technical explanation
- evaluation results
- future roadmap

---

# 37. Explicitly Out of Scope for V1

The following were deliberately identified as things **not to build initially**:

- multi-agent architecture
- MCP server
- GraphRAG
- knowledge graphs
- hybrid BM25 search
- sophisticated reranking
- Kubernetes
- microservices
- Redis
- Celery
- Kafka
- complicated OAuth
- multi-tenancy
- billing
- real-time collaboration
- mobile application

These can be considered for later versions only with explicit approval.

---

# 38. MCP Strategy

The user has completed MCP Introduction/Advanced training.

MCP should **not** be forced into the core V1 architecture.

A potential V2 enhancement is an MCP server exposing tools such as:

```text
search_company_documents()
get_document()
search_policy()
```

Possible future architecture:

```text
Claude / MCP Client
        │
        ▼
Company Knowledge MCP Server
        │
        ▼
RAG Backend
```

This is a future possibility, not a V1 requirement.

---

# 39. AI-Assisted Development Strategy

The project is intended to use modern AI development tools.

## Claude Code — Primary development tool

Claude Code should be the main implementation agent.

Potential uses:

- project scaffolding
- backend implementation
- RAG implementation
- testing
- debugging
- refactoring
- Git operations
- documentation
- code review

The user has Claude Code installed and has completed Claude Code 101 and Claude Code in Action training.

## Claude Cowork — Supporting tool

Cowork is intended primarily for higher-level work such as:

- research
- document preparation
- evaluation dataset preparation
- documentation review
- architecture review
- portfolio preparation

It is not intended to replace Claude Code as the primary implementation tool.

## Cursor — Optional tool

The user does not currently have a paid Cursor account and may purchase the $20 plan later.

Cursor is **not required for V1**.

The implementation should initially proceed using the existing Claude Code setup.

A Cursor subscription can be reconsidered later, particularly for React/frontend work.

---

# 40. Token / Usage Optimization Strategy — Confirmed Requirement

The implementation must be planned to consume as few AI coding-tool tokens as reasonably possible.

The agreed principles are:

### 1. Do not ask an AI coding agent to build the entire project in one prompt.

Work should be divided into focused milestones.

### 2. Use `CLAUDE.md`

The project should maintain persistent instructions covering:

- project purpose
- architecture
- technology stack
- directory structure
- coding conventions
- RAG decisions
- API conventions
- testing requirements
- things not to change

This reduces repeated explanations.

### 3. Keep prompts focused

Each implementation prompt should normally:

- have one logical objective,
- identify scope,
- identify allowed files where practical,
- specify requirements,
- specify things not to change,
- require tests,
- require a concise completion report.

### 4. Avoid unnecessary explanations

The coding agent should implement and test rather than repeatedly regenerate large explanations of the whole project.

### 5. Run tests locally

Use local commands such as:

```text
pytest
```

and provide only relevant failures to the AI coding agent when debugging.

### 6. Commit frequently

Use small Git commits so changes can be reviewed or reverted safely.

Example:

```text
git commit -m "Add document ingestion pipeline"
git commit -m "Add vector retrieval"
git commit -m "Add RAG chat endpoint"
```

### 7. Avoid unnecessary architecture exploration

The project should remain deliberately simple.

---

# 41. Future Prompting Workflow

For future implementation discussions, prompts intended for Claude Code should generally contain:

```text
OBJECTIVE

SCOPE

REQUIREMENTS

DO NOT

TESTING

COMPLETION REPORT
```

The prompt should tell Claude Code to read `CLAUDE.md` before implementation.

Prompts should normally instruct the agent not to implement future milestones unless explicitly requested.

---

# 42. Roles of the AI Tools

The intended workflow is:

```text
User
  │
  │ Focused implementation prompt
  ▼
Claude Code
  │
  ├── Inspect
  ├── Implement
  ├── Test
  └── Report
  │
  ▼
User
  │
  ├── Run application
  ├── Manual test
  └── Review Git diff
  │
  ▼
ChatGPT
  │
  ├── Architecture guidance
  ├── Prompt design
  ├── Troubleshooting
  ├── Code/architecture review
  └── Next-step planning
```

The intention is that ChatGPT acts as an architecture/engineering mentor and Claude Code acts primarily as the implementation agent.

---

# 43. Portfolio Positioning

The project is intended to demonstrate the user's transition from long-term full-stack/Laravel development toward modern AI engineering.

The portfolio story should demonstrate a progression such as:

```text
PHP / Laravel / Full-stack
        ↓
Python
        ↓
FastAPI
        ↓
Machine Learning
        ↓
LLMs
        ↓
RAG
        ↓
AI Engineering
        ↓
Agentic Development
```

ReactJS is also intentionally included so the project can demonstrate modern frontend experience alongside the Python AI stack.

The project should therefore demonstrate:

```text
Backend engineering
+
React frontend
+
RAG
+
LLMs
+
Vector search
+
AI-assisted development
=
Modern AI full-stack engineering
```

---

# 44. Confirmed Decisions

The following decisions are currently considered **approved/confirmed**:

1. The project is a professional minimal viable RAG portfolio application.
2. The demo concept is **Company Knowledge Assistant**.
3. The target audience includes non-technical interviewers/HR.
4. The frontend will use **ReactJS**.
5. The frontend will use **Bootstrap**.
6. The backend will use **Python + FastAPI**.
7. The vector database will be **Qdrant**.
8. The application will use **OpenAI APIs** for its LLM instead of Claude APIs.
9. Source citations are a core requirement.
10. Document ingestion is a core requirement.
11. Semantic retrieval is a core requirement.
12. The application should refuse to invent information when the indexed documents do not support an answer.
13. A professional admin/control panel is part of the intended application.
14. RAG evaluation is part of the intended project.
15. Docker is intended for the later production-quality stage.
16. The project will be published as a public GitHub portfolio repository.
17. Token/usage efficiency is an important development constraint.
18. Claude Code is the primary AI coding tool for implementation.
19. Claude Cowork is a supporting research/review/organization tool.
20. Cursor is optional and should not be required to start V1.
21. MCP is not required for V1.
22. The Python package/environment manager will be **uv**.
23. The OpenAI LLM model will be **GPT-5.4 mini**.
24. The embedding model will be **text-embedding-3-small**.
25. The core relational entities `documents`, `chunks`, `conversations`, and `messages` will use **UUID primary keys**; related foreign keys will use UUIDs.
26. Qdrant will run in a **separate Docker container** during development, independent from application containerization.
27. The verified local Docker runtime for development is **Colima** with Docker context `colima`; Docker Desktop and the inactive `lima-docker` context are not used.
28. The development Qdrant container is currently pinned to **`qdrant/qdrant:v1.19.2`**.

---

# 45. Decisions Resolved During Implementation

The following items from the original planning phase have been settled by explicit approval or by the implemented V1 design. They are no longer unresolved architecture questions:

1. **V1 document formats:** PDF only. PyMuPDF is the parser. TXT, Markdown, and DOCX are not V1 requirements.
2. **Relational database:** SQLite for V1, including the Compose demo. PostgreSQL is not required for this portfolio version.
3. **Authentication:** One environment-configured administrator, Argon2id password hash, JWT bearer tokens, and protected admin routes; no OAuth, multi-tenancy, or user-management system.
4. **Ingestion execution:** Synchronous request-driven ingestion; no Celery, Redis, Kafka, or separate worker.
5. **Compose topology:** Qdrant + FastAPI backend + Nginx/frontend. Nginx serves the React build and proxies `/api` to the backend using same-origin requests.
6. **Evaluation V1:** A 30-question evaluation dataset; retrieval metrics Recall@5, Hit@5, and MRR; deterministic checks for answer correctness, refusal behavior, citations, and numeric grounding; CLI runner, saved results, and an admin evaluation page. Initial success on the small fictional corpus is a baseline, not a general quality guarantee.
7. **Retrieval playground:** Implemented in the admin area.
8. **Application identity:** The demo concept/name remains **Company Knowledge Assistant**.
9. **Sample content:** Fictional company-policy/demo documents; never use confidential company documents.
10. **Streaming:** True progressive/token streaming is not implemented. The current request/response chat behavior is the V1 baseline; streaming is optional polish, not a blocker.

Implementation defaults such as chunk size, overlap, Top-K, and score threshold remain configurable tuning parameters, not permanent architectural decisions. Keep the current tested defaults unless evaluation evidence supports a change; do not tune them merely to make illustrative metrics look better.

# 46. Remaining Deliberate Choices and Constraints

These are genuinely optional decisions, not blockers for completing the V1 application:

- **Cloud hosting/live demo:** No provider selected. Local Docker Compose and a public GitHub repository are the baseline; a hosted demo is optional during Milestone 12.
- **Cursor subscription:** Optional; Claude Code remains the primary implementation tool.
- **Final branding/visual polish:** The concept is fixed, but final logo/colors/marketing copy can be chosen during Milestone 12 without architecture changes.
- **Final sample corpus:** The document set may be refined for a coherent demo, keeping it fictional and small.
- **Future production database:** PostgreSQL can be considered only if a real deployment requirement justifies it; it is not needed for V1.
- **Evaluation expansion:** The existing evaluation methodology is implemented. More metrics or a larger dataset are optional follow-up work, not a prerequisite for declaring the initial evaluation milestone complete.

Do not block ongoing work on these optional choices. Do not introduce new infrastructure or scope merely to resolve an optional item.

# 47. Current Implementation Status

## Overall status — 2026-10-16

**Milestones 0–10 are completed; the combined M9/M10 work was committed as `51593b0 feat: complete admin tools and RAG evaluation` and pushed to `origin/main`. Milestone 11 implementation, the isolated scratch-copy Compose verification, and final local checks are reported complete. M11 changes remain uncommitted/unpushed according to the latest report; review the diff and Git status before making a single combined M11 commit. Milestone 12 is next after that commit is reviewed and recorded.**

This section records the latest status supported by the project conversation. Do not infer that a test or deployment check passed unless its result was actually reported.

## Completed milestones

- **M0 — Project specification:** `CLAUDE.md`, README, architecture and RAG-pipeline documentation created and reviewed.
- **M1 — Backend foundation:** Python/uv, FastAPI, settings, logging, health endpoint, pytest/httpx foundation and environment examples.
- **M2 — Database:** SQLAlchemy/SQLite models for documents, chunks, conversations, messages and query logs; UUID IDs, relationships and constraints.
- **M3 — Ingestion/chunking:** PDF extraction with PyMuPDF, cleanup, deterministic page-bounded character chunking, page/section metadata, persistence and failure statuses.
- **M4 — Embeddings/Qdrant:** OpenAI `text-embedding-3-small`, vector-store abstraction, Qdrant collection validation, UUID point IDs, metadata payloads, indexing and retrieval. Real Qdrant `v1.19.2` integration was smoke-tested; this did not itself make a real OpenAI API call.
- **M5 — RAG engine:** Retrieval/context assembly, grounded prompting, OpenAI generation with approved `gpt-5.4-mini`, citations and insufficient-evidence refusal behavior. Commit recorded earlier as `c614e7b`; 60 tests were reported at that stage.
- **M6 — Chat API:** Chat endpoint, persistence and source citations. Commit `f23a1be`; 78 backend tests were reported at that stage.
- **M7 — React foundation:** React/Vite, Bootstrap, routing, API client and application shell. Commit `8314887`; frontend tests, lint and build passed at that stage.
- **M8 — Chat UI:** Conversation list, chat flow, citations and new conversations. True progressive/token streaming is not implemented. Commit `62e0701`; 17 frontend tests, lint/build and 78 backend tests were reported at that stage.
- **M9/M10 — Admin and evaluation:** Authentication/admin dashboard, document upload/delete/re-index, retrieval playground, 30-question evaluation dataset, Recall@5/Hit@5/MRR, deterministic answer checks, CLI runner, saved results and evaluation UI. Combined commit `51593b0` is pushed to `origin/main`. Reported verification: 139 backend tests and 38 frontend tests passed; frontend lint/build passed. The first evaluation run passed all 30 questions on the small fictional corpus; this is only a baseline for that corpus.

## Milestone 11 — Production quality — implemented and locally verified; commit/push pending

Reported implementation includes:

- backend/frontend Dockerfiles and a three-service Compose configuration (Qdrant, backend, Nginx/frontend)
- Nginx serving the frontend and proxying same-origin `/api` requests
- GitHub Actions CI for backend, frontend and Docker-related checks
- request IDs, structured/text logging options, safe error responses and correlated server-side errors
- stricter environment validation and production fail-fast behavior
- login throttling, request/upload limits, sanitized filenames and sensitive-value masking
- protections against leaking passwords/API keys through validation responses and logs
- in-memory per-IP chat throttling: default 20 requests per 60 seconds, configurable; `CHAT_RATE_LIMIT_REQUESTS=0` disables it; 429 responses include `Retry-After` and request ID; blocked requests do not reach OpenAI
- frontend handling for chat 429 responses that preserves the user question
- deployment documentation and updated README/architecture/RAG docs

Latest reported verification:

- Backend: **186 tests passed**.
- Frontend: **39 tests passed**; lint and production build passed.
- CI workflow YAML parsed locally; `uv lock --check`, `npm ci --dry-run`, and Docker Compose configuration validation against `.env.example` passed. GitHub Actions itself has **not** run, so hosted CI remains unverified until a push/PR triggers it.
- Full isolated Compose verification completed in disposable project `cka-test` under `~/cka-compose-test`, using a separate database volume, separate Qdrant storage, dummy admin credentials and a random JWT secret. All three services became healthy.
- Through Nginx on port 8080, the React app and a deep SPA route returned 200; `/api/health` proxied correctly; protected documents without a token returned 401; incorrect credentials returned 401; login succeeded; document list and dashboard stats matched the seeded disposable database; saved evaluation runs were visible; retrieval returned relevant chunks.
- Container logs were checked for secrets; none of the API key, password, password hash or JWT was found. One low-cost OpenAI embedding call was made for the real retrieval check; no chat request was made through the Compose stack.
- The scratch stack and temporary resources were removed. The original `backend/app.db` and all 43 files under `qdrant_storage/` had identical content hashes before and after verification. The development Qdrant container was restarted and all 15 original points were confirmed present.
- GitHub Actions itself was not run. The workflow remains to be verified by an actual push/PR.

M11 implementation and isolated Compose verification are therefore **complete locally**, but M11 is not yet committed/pushed according to the latest report. Review `git status` and the complete diff before committing the combined M11, rate-limit and documentation changes.

Known V1 limitations to document honestly:

- SQLite and local Qdrant are single-instance demo infrastructure, not a horizontally scalable deployment.
- Authentication is single-admin, with no token revocation or user-management system.
- Login and chat rate limits are in-memory and per process; they reset on restart and are not shared between workers.
- No TLS is configured by the local Compose stack; a public deployment needs HTTPS/TLS termination and a deployment-specific security review.
- True progressive/token streaming is not implemented in V1.
- Stale `PROCESSING` document recovery and multi-instance operation are not established V1 capabilities.
- The backend Docker build reports a non-blocking `useradd` warning because UID 10001 is above the system-UID range; it was left unchanged after testing.
- GitHub Actions has not yet run remotely. Local workflow/lockfile/configuration checks passed, but hosted CI status is pending until a push or pull request runs it.

## Immediate next steps

1. Review `git status` and the complete diff; the latest report says M11, chat rate limiting and documentation changes are uncommitted and not pushed. Keep them in one reviewed commit unless the diff reveals a clear reason to split them.
2. Commit and push the reviewed changes when ready; do not claim hosted CI passed until GitHub Actions actually runs.
3. Begin **M12 — Portfolio polish** after the M11 commit is recorded.

## Milestone 12 — Portfolio polish checklist

- finalize accurate README and setup/deployment instructions
- add an architecture diagram and screenshots
- prepare a small, coherent fictional demo corpus
- document the RAG pipeline, citations, evaluation method/results, and known limitations
- run the documented clean-install workflow
- verify no secrets, real `.env` files, SQLite databases, Qdrant storage, or generated evaluation artifacts are accidentally committed
- confirm GitHub repository status and prepare a concise portfolio/interview explanation

# 48. Future Change-Control Procedure

If a future discussion proposes a significant change, use this procedure:

### Step 1

Explain:

- what is being proposed,
- why it may be useful,
- what existing decision it changes,
- consequences/tradeoffs.

### Step 2

Ask the user explicitly whether to approve the change.

### Step 3

Until approval:

- do not modify the canonical plan,
- do not treat the proposed change as an approved decision,
- do not implement an architecture-breaking change based solely on the proposal.

### Step 4

After explicit approval:

- update `MASTER_PLAN.md`,
- clearly move the affected item from proposal/open question to confirmed decision where appropriate,
- ensure the rest of the plan remains internally consistent.

---

# 49. Guiding Principle

The project should demonstrate **real understanding of RAG and modern AI engineering**, not merely demonstrate that an AI coding agent can generate a large amount of code.

The finished application should be:

> **Small enough to finish, sophisticated enough to impress, and simple enough to explain in an interview.**

---

# 50. Canonical Status

This document represents the canonical project plan updated on **2026-10-16** using the restored original plan and the latest implementation reports available in the project conversation. Milestones 0–10 are completed and pushed. Milestone 11 implementation and isolated full Compose verification are reported complete locally; the combined M11 changes still need review, commit and push. Hosted GitHub Actions verification remains pending until a push or pull request triggers the workflow. Milestone 12 — Portfolio polish follows the M11 commit.

Future implementation work should remain aligned with this document unless the user explicitly approves a change.

**End of MASTER_PLAN.md**
