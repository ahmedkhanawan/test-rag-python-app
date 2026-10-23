# Deployment, configuration and operations

Local development is unchanged: Qdrant via `scripts/start-qdrant.sh`, backend with `uv run uvicorn app.main:app`, frontend with `npm run dev` (see [qdrant.md](qdrant.md)). This page covers the containerized stack and the production-quality behavior added in Milestone 11. Topology (Qdrant + backend + nginx/React, same-origin `/api` proxy) is the one chosen for the project; `MASTER_PLAN.md` leaves it open.

## Docker on a Mac with Colima

Docker Desktop is not needed. Check the runtime first:

```bash
colima status && docker context use colima
```

1. Create the config: `cp .env.example backend/.env`, then fill in `OPENAI_API_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` (`cd backend && uv run python -m scripts.hash_password`, keep the hash in single quotes) and `JWT_SECRET` (`openssl rand -hex 32`). `backend/.env` is git-ignored; never commit it.
2. Stop the dev Qdrant container if it is running (`docker stop company-knowledge-qdrant`). The compose Qdrant uses the same `./qdrant_storage` and two servers must not share it.
3. `docker compose up --build -d`, then open <http://localhost:8080> (bound to 127.0.0.1 only).
4. Logs: `docker compose logs -f backend` (JSON lines). Stop: `docker compose down` (data is kept).

| Service | Image | Notes |
| --- | --- | --- |
| `qdrant` | `qdrant/qdrant:v1.19.2` | separate container, storage `./qdrant_storage`, not published to the host |
| `backend` | `./backend/Dockerfile` | non-root, SQLite in the `app-data` volume (`/data`), no published port |
| `frontend` | `./frontend/Dockerfile` | nginx serves the build and proxies `/api` to the backend (same origin, no CORS) |

The backend runs with `ENVIRONMENT=production`: it **will not start** if `OPENAI_API_KEY`, `ADMIN_USERNAME`, an Argon2 `ADMIN_PASSWORD_HASH` or a 32+ character `JWT_SECRET` is missing (`docker compose logs backend` lists the variable names, never values).

**Reusing existing local data.** The container database starts empty. To keep documents already indexed in `./qdrant_storage`, copy your SQLite file in before the first start:

```bash
docker compose run --rm --no-deps -v "$PWD/backend:/seed:ro" backend sh -c 'cp /seed/app.db /data/app.db'
```

**Evaluation** results in `./evaluation` are shown read-only at `/admin/evaluation`. The compose Qdrant is not published to the host, so run evaluations from the host against the development setup (`scripts/start-qdrant.sh` plus the local `backend/app.db`): `cd backend && uv run python -m scripts.run_evaluation`. New result files then appear in the page after a refresh (`./evaluation` is mounted live).

## Configuration

All settings are environment variables (see `.env.example`). Invalid values stop the app at startup with the variable name and reason, never the value. Secrets (`OPENAI_API_KEY`, `JWT_SECRET`, `ADMIN_PASSWORD_HASH`) are masked in `repr()`, logs and tracebacks. Outside production, missing secrets only produce startup warnings.

## Errors and logging

- Every error response is `{"detail": "<safe message>", "request_id": "..."}`; validation errors add `errors` (field and reason, never the submitted value). Unexpected failures return a generic 500; the details are in the server log under the same `request_id` (also sent as the `X-Request-ID` header; a valid incoming one is reused).
- Logs go to stderr as text (`LOG_FORMAT=text`) or one JSON object per line (`json`). One access line per request records method, path, status and duration, never query strings, bodies or tokens. Passwords, API keys, bearer tokens, JWTs and password hashes are masked even if they reach a log call.

## Security notes

- Single admin account, Argon2id hash, HS256 JWT with expiry. Every `/api` route except `/api/health`, `/api/chat` and `/api/auth/login` requires the admin token (enforced by a test that walks all routes).
- Failed logins are throttled per client IP (5 per 5 minutes by default, then 429 with `Retry-After`).
- `POST /api/chat` is public, so it is rate limited per client IP to protect OpenAI spend (20 requests per 60 seconds by default, then 429 with `Retry-After`; `CHAT_RATE_LIMIT_REQUESTS=0` disables it). Rejected requests never reach the RAG pipeline.
- Both limiters are in memory and **per process**: they reset when the backend restarts and are not shared between workers. Behind nginx the client IP comes from the `X-Forwarded-For` header nginx sets (overwritten, not appended). Without Redis or similar this is a cost guard, not a defence against a determined distributed client.
- Uploads: `.pdf` only, `%PDF-` header checked, name sanitized, size limited (`MAX_UPLOAD_MB`; oversized requests are refused from `Content-Length` before the body is read, and nginx caps bodies at 25 MB), stored in a temporary directory that is removed after ingestion.
- Question length is capped at 4000 characters; `top_k` is bounded.
- CORS is off unless `CORS_ORIGINS` lists explicit origins (no `*`, no cookies).
- nginx adds a strict Content-Security-Policy, `X-Frame-Options: DENY`, `nosniff` and `Referrer-Policy: no-referrer`; API responses are `Cache-Control: no-store`.

## CI

`.github/workflows/ci.yml` runs on pushes to `main` and on pull requests: backend (`uv sync --frozen`, `pytest`), frontend (`npm ci`, lint, test, build) and Docker (validates `docker-compose.yml`, builds both images). No secrets are used; tests rely on fakes.

## Known limitations

- `/api/chat` is public by design. It is rate limited per IP, but the limiter is in memory and per process (resets on restart, not shared across workers), so it only bounds casual abuse of OpenAI spend. Login throttling has the same limits.
- One admin account; tokens last `JWT_EXPIRE_MINUTES` (60) and cannot be revoked.
- The stack serves plain HTTP on `127.0.0.1:8080`; public use needs a TLS-terminating proxy in front.
- SQLite and local Qdrant storage mean a single instance. A document left in `PROCESSING` by a crash is not swept automatically (re-index refuses it; delete works).
- Base images and GitHub Actions use floating tags, not digests.

