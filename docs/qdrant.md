# Local Qdrant

Qdrant always runs as a separate container. This page covers the standalone development container; `docker-compose.yml` runs the same image as a service next to the containerized app (see [deployment.md](deployment.md)). Both use `./qdrant_storage`, so run only one at a time.

```bash
./scripts/start-qdrant.sh                 # start (data persists in ./qdrant_storage)
cd backend && uv run python -m scripts.check_qdrant   # connectivity check
docker stop company-knowledge-qdrant      # stop
```

Defaults: `QDRANT_URL=http://localhost:6333`, `QDRANT_COLLECTION=company_documents`.

The collection is created automatically on first indexing, with cosine distance and a vector size taken from the actual embedding response (1536 for `text-embedding-3-small`). SQL remains the source of truth; Qdrant holds vectors plus a citation payload. The Qdrant point id is the chunk UUID.
