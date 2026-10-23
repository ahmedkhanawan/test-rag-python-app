import json
import logging
import re
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(request_id)s]: %(message)s"

# Defense in depth: even if a secret reaches a log call (or a traceback), mask it.
_REDACTIONS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-***"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]+"), "Bearer ***"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*"), "***jwt***"),
    (re.compile(r"\$argon2[a-z0-9]*\$[^\s\"']+"), "***hash***"),
    (
        re.compile(r"(?i)\b(api[_-]?key|password|passwd|secret|token)(\"?\s*[:=]\s*\"?)[^\s\"',;&]+"),
        r"\1\2***",
    ),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


class JsonFormatter(logging.Formatter):
    """One JSON object per line, suitable for log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            entry.update(extra)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return redact(json.dumps(entry, default=str))


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter(TEXT_FORMAT))
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
    # One format everywhere: route uvicorn's loggers through ours and replace its
    # access log (which prints query strings) with the request log in the middleware.
    for name in ("uvicorn", "uvicorn.error"):
        uv = logging.getLogger(name)
        uv.handlers.clear()
        uv.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    # HTTP client libraries log every request URL at INFO; keep them quiet.
    for name in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
