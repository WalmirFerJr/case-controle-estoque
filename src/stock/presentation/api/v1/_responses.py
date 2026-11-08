"""Documentação OpenAPI dos erros mais comuns (aparecem no Swagger)."""

from typing import Any

PROBLEM: dict[str, Any] = {"content": {"application/problem+json": {}}}

NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"description": "Não encontrado", **PROBLEM}}
CONFLICT: dict[int | str, dict[str, Any]] = {
    409: {"description": "Conflito com o estado do estoque", **PROBLEM}
}
INVALID: dict[int | str, dict[str, Any]] = {422: {"description": "Dados inválidos", **PROBLEM}}
