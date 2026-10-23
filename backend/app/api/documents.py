import logging
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.admin import DocumentOut
from app.api.deps import get_embedder, get_vector_store, require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.models import Chunk, Document, DocumentStatus
from app.services.embeddings import EmbeddingError, EmbeddingService
from app.services.indexing import index_document
from app.services.ingestion import IngestionError, InvalidPDFError, ingest_pdf
from app.services.vector_store import VectorStore, VectorStoreError

logger = logging.getLogger(__name__)

# Every route here requires a valid admin JWT.
router = APIRouter(tags=["documents"], dependencies=[Depends(require_admin)])

_READ_BLOCK = 1024 * 1024
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _clean_text(value: str, limit: int) -> str:
    return _CONTROL_CHARS.sub("", value).strip()[:limit]


def _safe_filename(raw: str | None) -> str:
    """Client-supplied file name reduced to a plain, bounded, printable `*.pdf` name."""
    name = _clean_text(Path((raw or "").replace("\\", "/")).name, 10_000)
    if not name.lower().endswith(".pdf"):
        return ""  # caller rejects it
    stem = name[:-4].strip(". ")
    return f"{stem[:251]}.pdf" if stem else "document.pdf"


def _out(db: Session, document_id: uuid.UUID) -> DocumentOut:
    document = db.get(Document, document_id)
    chunk_count = db.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
    )
    return DocumentOut(
        id=document.id, name=document.name, filename=document.filename,
        status=document.status, chunk_count=chunk_count or 0,
        created_at=document.created_at, updated_at=document.updated_at,
    )


def _get_or_404(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


def _database_error(exc: SQLAlchemyError) -> HTTPException:
    logger.error("Document database error: %s", type(exc).__name__)
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Database error")


def _log_failure(stage: str, exc: Exception) -> None:
    # Log only the exception type: provider messages may contain sensitive details.
    logger.error("Document operation failed at %s stage: %s", stage, type(exc).__name__)


def _mark(db: Session, document_id: uuid.UUID, doc_status: DocumentStatus) -> None:
    try:
        db.rollback()
        document = db.get(Document, document_id)
        if document is not None:
            document.status = doc_status
            db.commit()
    except SQLAlchemyError as exc:  # best effort; the original error is what we report
        db.rollback()
        logger.error("Could not set document status: %s", type(exc).__name__)


def _index(
    db: Session, document_id: uuid.UUID, embedder: EmbeddingService, store: VectorStore
) -> None:
    """Embed + upsert; on failure mark the document FAILED and raise an HTTP error.

    The chunks stay in SQLite, so the admin can retry with re-index or delete it.
    """
    try:
        indexed = index_document(db, document_id, embedder, store)
    except EmbeddingError as exc:
        _log_failure("embedding", exc)
        _mark(db, document_id, DocumentStatus.FAILED)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Embedding service failed") from None
    except VectorStoreError as exc:
        _log_failure("vector store", exc)
        _mark(db, document_id, DocumentStatus.FAILED)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Vector store is unavailable"
        ) from None
    except SQLAlchemyError as exc:
        _mark(db, document_id, DocumentStatus.FAILED)
        raise _database_error(exc) from None
    if indexed == 0:
        _mark(db, document_id, DocumentStatus.FAILED)
        raise HTTPException(status.HTTP_409_CONFLICT, "Document has no chunks to index")
    _mark(db, document_id, DocumentStatus.READY)


def _save_upload(upload: UploadFile, directory: Path) -> Path:
    """Stream the upload to disk, enforcing the configured size limit."""
    filename = _safe_filename(upload.filename)
    if not filename:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Only .pdf files are supported")
    limit = get_settings().max_upload_mb * 1024 * 1024
    target = directory / filename
    size = 0
    with target.open("wb") as out:
        while block := upload.file.read(_READ_BLOCK):
            size += len(block)
            if size > limit:
                raise HTTPException(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    f"File exceeds the {get_settings().max_upload_mb} MB limit",
                )
            out.write(block)
    if size == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The uploaded file is empty")
    return target


@router.post("/documents/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    name: str | None = Form(default=None, max_length=255),
    db: Session = Depends(get_db),
    embedder: EmbeddingService = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
) -> DocumentOut:
    tmp_dir = Path(tempfile.mkdtemp(prefix="cka-upload-"))
    try:
        path = _save_upload(file, tmp_dir)
        try:
            document = ingest_pdf(db, path, name=_clean_text(name or "", 255) or None)
        except InvalidPDFError:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "The file is not a valid PDF"
            ) from None
        except IngestionError:
            # ingest_pdf already marked the document FAILED and stored no chunks.
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Could not extract any text from the PDF",
            ) from None
        except SQLAlchemyError as exc:
            db.rollback()
            raise _database_error(exc) from None
        document_id = document.id
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)  # the PDF itself is not retained

    _index(db, document_id, embedder, store)
    return _out(db, document_id)


@router.post("/documents/{document_id}/reindex", response_model=DocumentOut)
def reindex_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    embedder: EmbeddingService = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
) -> DocumentOut:
    """Re-embed the document's stored chunks and overwrite its Qdrant points."""
    try:
        document = _get_or_404(db, document_id)
        if document.status == DocumentStatus.PROCESSING:
            raise HTTPException(status.HTTP_409_CONFLICT, "Document is already being processed")
        document.status = DocumentStatus.PROCESSING
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise _database_error(exc) from None
    _index(db, document_id, embedder, store)
    return _out(db, document_id)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    store: VectorStore = Depends(get_vector_store),
) -> Response:
    """Delete Qdrant points first, then the SQL rows.

    If Qdrant fails nothing changes. If SQL fails after Qdrant succeeded the document
    stays listed (without vectors) and the delete can simply be retried.
    """
    try:
        document = _get_or_404(db, document_id)
    except SQLAlchemyError as exc:
        raise _database_error(exc) from None
    try:
        store.delete_document(document_id)
    except VectorStoreError as exc:
        _log_failure("vector store", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Vector store is unavailable"
        ) from None
    try:
        db.delete(document)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise _database_error(exc) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
