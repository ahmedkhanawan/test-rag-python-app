import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models import Chunk, Conversation, Document, DocumentStatus, Message

# Every route here requires a valid admin JWT.
router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


class DocumentOut(BaseModel):
    id: uuid.UUID
    name: str
    filename: str
    status: DocumentStatus
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class StatsOut(BaseModel):
    documents: int
    documents_by_status: dict[str, int]
    chunks: int
    conversations: int
    messages: int


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentOut]:
    rows = db.execute(
        select(Document, func.count(Chunk.id))
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    ).all()
    return [
        DocumentOut(
            id=d.id, name=d.name, filename=d.filename, status=d.status,
            chunk_count=n, created_at=d.created_at, updated_at=d.updated_at,
        )
        for d, n in rows
    ]


@router.get("/admin/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)) -> StatsOut:
    by_status = {s.value: 0 for s in DocumentStatus}
    for st, n in db.execute(select(Document.status, func.count()).group_by(Document.status)):
        by_status[st.value] = n

    def count(model) -> int:
        return db.scalar(select(func.count()).select_from(model)) or 0

    return StatsOut(
        documents=sum(by_status.values()),
        documents_by_status=by_status,
        chunks=count(Chunk),
        conversations=count(Conversation),
        messages=count(Message),
    )
