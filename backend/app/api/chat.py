import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import Answerer, get_answerer
from app.core.config import get_settings
from app.core.database import get_db
from app.core.ratelimit import FailureLimiter
from app.models import Conversation, Message, MessageRole
from app.models.base import utcnow
from app.rag.pipeline import RAGResult
from app.services.embeddings import EmbeddingError
from app.services.generation import GenerationError
from app.services.vector_store import VectorStoreError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Per-process, in-memory (resets on restart), keyed by client IP. Each chat request can
# cost OpenAI credit, and the endpoint is public by design.
chat_limiter = FailureLimiter()


def enforce_chat_rate_limit(request: Request) -> None:
    settings = get_settings()
    limit = settings.chat_rate_limit_requests
    if limit == 0:
        return
    client_ip = request.client.host if request.client else "unknown"
    wait = chat_limiter.hit(client_ip, limit, settings.chat_rate_limit_window_seconds)
    if wait:
        logger.warning("Chat rate limit hit for client %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(wait)},
        )


MAX_QUESTION_CHARS = 4000


class ChatRequest(BaseModel):
    question: str = Field(max_length=MAX_QUESTION_CHARS)
    conversation_id: uuid.UUID | None = None

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        return v


class MessageOut(BaseModel):
    id: uuid.UUID
    content: str
    created_at: datetime


class SourceOut(BaseModel):
    """Application-owned citation; `source_number` matches [Source N] in the answer."""

    source_number: int
    document_id: uuid.UUID
    document_name: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    section: str | None
    score: float
    text: str


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    user_message: MessageOut
    assistant_message: MessageOut
    sources: list[SourceOut]
    grounded: bool


def _sources(result: RAGResult) -> list[SourceOut]:
    return [
        SourceOut(
            source_number=i,
            document_id=c.document_id,
            document_name=c.document_name,
            chunk_id=c.chunk_id,
            chunk_index=c.chunk_index,
            page_number=c.page_number,
            section=c.section,
            score=c.score,
            text=c.text,
        )
        for i, c in enumerate(result.sources, start=1)
    ]


@router.post(
    "/chat", response_model=ChatResponse, dependencies=[Depends(enforce_chat_rate_limit)]
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    answer: Answerer = Depends(get_answerer),
) -> ChatResponse:
    asked_at = utcnow()

    try:
        conversation = None
        if request.conversation_id is not None:
            conversation = db.get(Conversation, request.conversation_id)
            if conversation is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    except SQLAlchemyError as exc:
        _database_error(exc)

    # The RAG call runs before any write, so a failure leaves no partial state
    # and no write transaction is held open during the slow LLM call.
    try:
        result = answer(request.question)
    except EmbeddingError as exc:
        _log_failure("embedding", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Embedding service failed") from None
    except VectorStoreError as exc:
        _log_failure("vector store", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Document search is unavailable"
        ) from None
    except GenerationError as exc:
        _log_failure("generation", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Answer generation failed") from None

    try:
        if conversation is None:
            conversation = Conversation()
            db.add(conversation)
        user_message = Message(
            conversation=conversation,
            role=MessageRole.USER,
            content=request.question,
            created_at=asked_at,
        )
        assistant_message = Message(
            conversation=conversation, role=MessageRole.ASSISTANT, content=result.answer
        )
        conversation.updated_at = utcnow()
        db.add_all([user_message, assistant_message])
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        _database_error(exc)

    return ChatResponse(
        conversation_id=conversation.id,
        user_message=MessageOut.model_validate(user_message, from_attributes=True),
        assistant_message=MessageOut.model_validate(assistant_message, from_attributes=True),
        sources=_sources(result),
        grounded=result.grounded,
    )


def _log_failure(stage: str, exc: Exception) -> None:
    # Log only the exception type: provider messages may contain sensitive details.
    logger.error("Chat failed at %s stage: %s", stage, type(exc).__name__)


def _database_error(exc: SQLAlchemyError) -> None:
    logger.error("Chat database error: %s", type(exc).__name__)
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Database error") from None
