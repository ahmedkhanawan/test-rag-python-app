import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# Every error body has a string `detail` plus the `request_id` that appears in the server
# logs, so a user-reported problem can be matched to its diagnostics.


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def _response(request: Request, status_code: int, detail: str, **extra) -> JSONResponse:
    rid = _request_id(request)
    response = JSONResponse(
        {"detail": detail, **extra, "request_id": rid}, status_code=status_code
    )
    response.headers["X-Request-ID"] = rid
    return response


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    response = _response(request, exc.status_code, str(exc.detail))
    for key, value in (exc.headers or {}).items():
        response.headers[key] = value
    return response


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default body echoes the rejected input (e.g. a submitted password) and
    # raw exception objects; return only where and why a field was rejected.
    errors = [
        {"loc": [str(part) for part in e["loc"]], "msg": e["msg"], "type": e["type"]}
        for e in exc.errors()
    ]
    return _response(request, 422, "Invalid request", errors=errors)


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Unhandled database error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
    return _response(request, 500, "Database error")


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__,
        exc_info=exc,
    )
    return _response(request, 500, "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
