"""Tradução de erros para respostas HTTP no formato Problem Details (RFC 9457/7807).

Regra: o cliente sempre recebe um JSON previsível com ``code`` estável para
tratar programaticamente, e nunca recebe stack trace ou detalhe interno.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from stock.domain.exceptions import (
    DomainError,
    HoldNotActiveError,
    HoldNotFoundError,
    InsufficientAvailableStockError,
    InvalidHoldDataError,
    InvalidHoldOperationError,
    InvalidQuantityError,
    InvalidSkuError,
    ProductNotFoundError,
    StockLimitExceededError,
)
from stock.presentation.observability import CORRELATION_HEADER, get_correlation_id

logger = logging.getLogger("stock.errors")

PROBLEM_CONTENT_TYPE = "application/problem+json"
ERROR_TYPE_BASE = "urn:stock-control:error:"  # URN: identifica o tipo sem prometer uma URL

# 404: recurso não existe | 409: conflita com o estado atual | 422: entrada inválida
STATUS_BY_DOMAIN_ERROR: dict[type[DomainError], int] = {
    ProductNotFoundError: status.HTTP_404_NOT_FOUND,
    HoldNotFoundError: status.HTTP_404_NOT_FOUND,
    InsufficientAvailableStockError: status.HTTP_409_CONFLICT,
    HoldNotActiveError: status.HTTP_409_CONFLICT,
    InvalidHoldOperationError: status.HTTP_409_CONFLICT,
    StockLimitExceededError: status.HTTP_409_CONFLICT,
    InvalidQuantityError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidSkuError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidHoldDataError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}

TITLES = {
    400: "Requisição inválida",
    404: "Recurso não encontrado",
    405: "Método não permitido",
    409: "Conflito com o estado atual do estoque",
    422: "Dados inválidos",
    500: "Erro interno",
    503: "Serviço temporariamente indisponível",
}


def problem_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    detail: str,
    **extra: Any,
) -> JSONResponse:
    correlation_id = get_correlation_id(request)
    body = {
        "type": ERROR_TYPE_BASE + code.lower().replace("_", "-"),
        "title": TITLES.get(status_code, "Erro"),
        "status": status_code,
        "code": code,
        "detail": detail,
        "instance": request.url.path,
        "correlation_id": correlation_id,
        **extra,
    }
    return JSONResponse(
        body,
        status_code=status_code,
        media_type=PROBLEM_CONTENT_TYPE,
        headers={CORRELATION_HEADER: correlation_id},
    )


def _domain_error_extras(exc: DomainError) -> dict[str, Any]:
    if isinstance(exc, InsufficientAvailableStockError):
        return {"sku": exc.sku, "requested": exc.requested, "available": exc.available}
    return {}


async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    status_code = STATUS_BY_DOMAIN_ERROR.get(type(exc), status.HTTP_422_UNPROCESSABLE_CONTENT)
    logger.info("business rule rejected request", extra={"extra_fields": {"code": exc.code}})
    return problem_response(
        request,
        status_code=status_code,
        code=exc.code,
        detail=exc.message,
        **_domain_error_extras(exc),
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        {"field": ".".join(str(part) for part in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return problem_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="VALIDATION_ERROR",
        detail="Um ou mais campos da requisição são inválidos.",
        errors=errors,
    )


async def handle_http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return problem_response(
        request,
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        detail=str(exc.detail),
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unexpected error", exc_info=exc)
    return problem_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
        detail="Erro inesperado. Informe o correlation_id ao suporte.",
    )


async def handle_service_unavailable(request: Request, exc: Exception) -> JSONResponse:
    logger.error("dependency unavailable", exc_info=exc)
    return problem_response(
        request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="SERVICE_UNAVAILABLE",
        detail="Banco de dados indisponível ou ocupado. Tente novamente em instantes.",
    )


def register_error_handlers(
    app: FastAPI, *, unavailable_errors: tuple[type[Exception], ...] = ()
) -> None:
    """Registra os handlers. ``unavailable_errors`` vem do composition root, para a
    camada HTTP não precisar conhecer exceções do driver de banco."""
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    for error_type in unavailable_errors:
        app.add_exception_handler(error_type, handle_service_unavailable)
    app.add_exception_handler(Exception, handle_unexpected_error)
