import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.logging import request_id_var

logger = logging.getLogger("app.access")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
UPLOAD_PATH = "/api/documents/upload"
_MULTIPART_OVERHEAD = 1024 * 1024  # form fields and boundaries around the file


class RequestContextMiddleware:
    """Request id, access log, basic response headers and an early upload size gate.

    Pure ASGI so the request id also reaches log lines emitted by handlers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        path, method = scope["path"], scope["method"]
        status = 500
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                if path.startswith("/api/") and path != "/api/health":
                    headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            rejected = self._reject_oversized_upload(scope, method, path)
            if rejected is not None:
                await rejected(scope, receive, send_wrapper)
            else:
                await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            client = scope.get("client")
            # Path only: query strings and bodies are never logged.
            log = logger.debug if path == "/api/health" else logger.info
            log(
                "%s %s -> %d (%d ms)", method, path, status, elapsed_ms,
                extra={"fields": {"method": method, "path": path, "status": status,
                                  "duration_ms": elapsed_ms, "client": client[0] if client else None}},
            )
            request_id_var.reset(token)

    @staticmethod
    def _reject_oversized_upload(scope: Scope, method: str, path: str) -> JSONResponse | None:
        """Starlette spools the whole multipart body to disk before our handler runs, so
        refuse obviously oversized uploads from the Content-Length header first."""
        if method != "POST" or path != UPLOAD_PATH:
            return None
        limit_mb = get_settings().max_upload_mb
        declared = Headers(scope=scope).get("content-length")
        request_id = scope["state"]["request_id"]
        if declared is None or not declared.isdigit():
            return JSONResponse(
                {"detail": "Content-Length header is required", "request_id": request_id},
                status_code=411,
            )
        if int(declared) > limit_mb * 1024 * 1024 + _MULTIPART_OVERHEAD:
            return JSONResponse(
                {"detail": f"File exceeds the {limit_mb} MB limit", "request_id": request_id},
                status_code=413,
            )
        return None
