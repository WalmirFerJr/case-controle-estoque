"""Parâmetros de rota e de consulta compartilhados, documentados uma vez para o Swagger."""

from typing import Annotated
from uuid import UUID

from fastapi import Path, Query

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

SkuPath = Annotated[
    str,
    Path(
        description=(
            "Identificador do produto (SKU): de 1 a 64 caracteres entre letras, dígitos, "
            "`.`, `_` e `-`, começando por letra ou dígito. Diferencia maiúsculas de minúsculas."
        ),
        openapi_examples={"notebook": {"summary": "Exemplo de SKU", "value": "NOTE-15"}},
    ),
]

HoldIdPath = Annotated[
    UUID,
    Path(description="`id` devolvido ao criar a reserva ou o bloqueio (campo `id` da resposta)."),
]

Limit = Annotated[
    int, Query(ge=1, le=MAX_PAGE_SIZE, description="Máximo de itens retornados (paginação).")
]

Offset = Annotated[int, Query(ge=0, description="Quantos itens pular antes de retornar.")]
