"""Logs estruturados (JSON) com correlation id por requisição."""

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response

CORRELATION_HEADER = "X-Correlation-ID"
_MAX_INCOMING_ID_LENGTH = 128
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

logger = logging.getLogger("stock.http")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", correlation_id_var.get()),
        }
        payload.update(getattr(record, "extra_fields", {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", correlation_id_var.get())


def register_request_context(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(CORRELATION_HEADER, "")
        correlation_id = (
            incoming if 0 < len(incoming) <= _MAX_INCOMING_ID_LENGTH else str(uuid.uuid4())
        )
        # request.state fica no scope ASGI: visível até para handlers de erro 500,
        # que rodam fora deste middleware.
        request.state.correlation_id = correlation_id
        token = correlation_id_var.set(correlation_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers[CORRELATION_HEADER] = correlation_id
        logger.info(
            "request completed",
            extra={
                "correlation_id": correlation_id,
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            },
        )
        return response
