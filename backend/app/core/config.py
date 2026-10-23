from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_JWT_SECRET_LENGTH = 32


class ConfigurationError(RuntimeError):
    """The environment configuration is unusable. Messages never contain secret values."""


def reveal(secret: SecretStr | None) -> str | None:
    """Plain value of an optional secret; empty counts as unset."""
    return (secret.get_secret_value() or None) if secret is not None else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Company Knowledge Assistant"
    # "production" turns missing/weak configuration into a startup failure.
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"
    database_url: str = "sqlite:///./app.db"
    # Implementation defaults (characters), not final project decisions.
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=150, ge=0)

    # Secrets are SecretStr so they never show up in repr(), logs or tracebacks.
    openai_api_key: SecretStr | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-5.4-mini"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "company_documents"

    # Implementation defaults, not final project decisions. The threshold is
    # disabled by default because suitable cosine values are not yet measured.
    retrieval_top_k: int = Field(default=5, gt=0, le=50)
    retrieval_score_threshold: float | None = None

    max_upload_mb: int = Field(default=20, gt=0, le=200)  # implementation default
    evaluation_dir: str | None = None  # default: <repo>/evaluation

    # Admin auth: a single admin account configured in the environment.
    # Generate the hash with `uv run python -m scripts.hash_password`.
    admin_username: str | None = None
    admin_password_hash: SecretStr | None = None
    jwt_secret: SecretStr | None = None  # at least 32 characters
    jwt_expire_minutes: int = Field(default=60, gt=0, le=24 * 60)

    # Failed admin logins allowed per client IP within the window before HTTP 429.
    login_max_failures: int = Field(default=5, gt=0)
    login_window_seconds: int = Field(default=300, gt=0)

    # Per-IP limit on POST /api/chat (each request can cost OpenAI credit). 0 disables.
    chat_rate_limit_requests: int = Field(default=20, ge=0)
    chat_rate_limit_window_seconds: int = Field(default=60, gt=0)

    # Comma-separated browser origins allowed to call the API cross-origin. Empty (the
    # default) adds no CORS headers: the Vite dev proxy and the nginx container proxy
    # both make the browser see a single origin.
    cors_origins: Annotated[list[str], NoDecode] = []

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip().rstrip("/") for o in v.split(",") if o.strip()]
        return v

    @field_validator("cors_origins")
    @classmethod
    def _check_origins(cls, v: list[str]) -> list[str]:
        for origin in v:
            parsed = urlparse(origin)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path:
                raise ValueError(
                    "CORS_ORIGINS entries must look like https://host[:port] (no '*', no path)"
                )
        return v

    @model_validator(mode="after")
    def _check_chunking(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self

    def problems(self) -> list[str]:
        """Configuration gaps that matter at runtime. Names only; never values."""
        found = []
        if not reveal(self.openai_api_key):
            found.append("OPENAI_API_KEY is not set (chat, search and indexing will fail)")
        if not self.admin_username:
            found.append("ADMIN_USERNAME is not set (admin login is disabled)")
        hash_ = reveal(self.admin_password_hash)
        if not hash_:
            found.append("ADMIN_PASSWORD_HASH is not set (admin login is disabled)")
        elif not hash_.startswith("$argon2"):
            found.append(
                "ADMIN_PASSWORD_HASH is not an Argon2 hash "
                "(generate one with `uv run python -m scripts.hash_password`)"
            )
        secret = reveal(self.jwt_secret)
        if not secret:
            found.append("JWT_SECRET is not set (admin login is disabled)")
        elif len(secret) < MIN_JWT_SECRET_LENGTH:
            found.append(f"JWT_SECRET is shorter than {MIN_JWT_SECRET_LENGTH} characters")
        return found


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        # Report which variables are wrong and why, never the rejected values.
        details = "; ".join(
            f"{'.'.join(str(part) for part in e['loc']).upper() or 'settings'}: {e['msg']}"
            for e in exc.errors()
        )
        raise ConfigurationError(f"Invalid configuration: {details}") from None


def check_startup_configuration(settings: Settings) -> list[str]:
    """Return the problems found; raise ConfigurationError in production if there are any."""
    problems = settings.problems()
    if problems and settings.environment == "production":
        raise ConfigurationError(
            "Invalid production configuration:\n  - " + "\n  - ".join(problems)
        )
    return problems
