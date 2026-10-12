from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Company Knowledge Assistant"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./app.db"
    # Implementation defaults (characters), not final project decisions.
    chunk_size: int = 1000
    chunk_overlap: int = 150

    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-5.4-mini"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "company_documents"

    # Implementation defaults, not final project decisions. The threshold is
    # disabled by default because suitable cosine values are not yet measured.
    retrieval_top_k: int = 5
    retrieval_score_threshold: float | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
