# RAG Pipeline

The approved RAG pipeline for the Company Knowledge Assistant. Source: `MASTER_PLAN.md` Sections 6–8, 16–19, 31.

## Pipeline

```text
Document
    ↓
Parse            (PyMuPDF for PDF)
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
    ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
User Question
    ↓
Generate Query Embedding
    ↓
Semantic Retrieval (Qdrant similarity search)
    ↓
Retrieve Top-K Chunks
    ↓
Optional Similarity Threshold
    ↓
Assemble Context
    ↓
Prompt LLM (OpenAI)
    ↓
Generate Grounded Answer
    ↓
Return Answer + Citations
```

## Grounding rule (confirmed)

Answers must be grounded in retrieved company documents. If the documents lack enough information, the assistant says so instead of inventing an answer, e.g.:

```text
I couldn't find information about this topic
in the available company documents.
```

## Citations (confirmed requirement)

Citations are application-owned: they come from the retrieved chunks, never from the LLM. The prompt labels each excerpt `[Source N]` in retrieval order and the API returns the same list, so `[Source N]` in the answer maps to `sources[N-1]`. Each source carries:

```python
{
    "source_number": 1,
    "document_id": "9c1c64c0-...",     # UUID
    "document_name": "sample_company_policy",
    "chunk_id": "...",                 # UUID, also the Qdrant point id
    "chunk_index": 4,
    "page_number": 2,
    "section": None,                   # from the PDF outline when it has one
    "score": 0.61,                     # cosine similarity
    "text": "...",
}
```

The chat UI shows document, page, section, relevance and the chunk text for each source. Sources are not stored on the server (only messages are), so the browser keeps them with the conversation.

## Ingestion lifecycle

Upload → validate (`.pdf`, `%PDF-` header, size limit) → extract text per page (PyMuPDF) → clean → chunk (page-bounded, characters) → store document and chunks in SQLite → generate embeddings → upsert into Qdrant → `READY`. It runs synchronously inside the upload request (no background queue). Failures set the document to `FAILED`: extraction problems store no chunks; embedding or Qdrant problems keep the chunks so **re-index** (re-embeds the stored chunks) can recover it. Delete removes the Qdrant points first, then the database rows.

## Configuration

Chunking and retrieval are configurable through environment variables, not hard-coded (see `.env.example`):

| Setting | Default | Notes |
| --- | --- | --- |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 1000 / 150 | characters; overlap must be smaller than size |
| `RETRIEVAL_TOP_K` | 5 | |
| `RETRIEVAL_SCORE_THRESHOLD` | unset | disabled; measured scores of answerable and unsupported questions overlap (see [evaluation.md](evaluation.md)) |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | approved |
| `OPENAI_CHAT_MODEL` | `gpt-5.4-mini` | approved; no temperature is set |

Qdrant uses cosine distance; the vector size is taken from the first embedding response (1536 for `text-embedding-3-small`).

## Status of earlier open decisions

| Item | Status |
| --- | --- |
| LLM and embedding models | Decided: `gpt-5.4-mini`, `text-embedding-3-small` |
| Chunk size / overlap, Top-K | Implementation defaults above; configurable, not tuned |
| Similarity threshold | Open; disabled |
| Formats beyond PDF (TXT, Markdown, DOCX) | Open; PDF only |
| Streaming mechanism | Open; answers are returned in one response |
| Evaluation methodology | Implemented in Milestone 10 ([evaluation.md](evaluation.md)); may evolve |

## Excluded from V1

Hybrid BM25 search, sophisticated reranking, GraphRAG, knowledge graphs, multi-agent retrieval.
