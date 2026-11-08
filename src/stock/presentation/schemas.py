"""Contrato HTTP (Pydantic). Validação de formato na borda; regras de negócio no domínio."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from stock.domain.entities.hold import REASON_MAX_LENGTH, REFERENCE_MAX_LENGTH
from stock.domain.value_objects import MAX_OPERATION_QUANTITY

QuantityField = Annotated[
    StrictInt,
    Field(gt=0, le=MAX_OPERATION_QUANTITY, description="Unidades (inteiro positivo)", examples=[5]),
]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")  # campo desconhecido = erro, não silêncio


class QuantityRequest(_Request):
    quantity: QuantityField


class ReservationRequest(_Request):
    quantity: QuantityField
    reference: str = Field(
        min_length=1,
        max_length=REFERENCE_MAX_LENGTH,
        description="Identificação da solicitação/pedido de origem",
        examples=["PED-2026-0001"],
    )


class BlockRequest(_Request):
    quantity: QuantityField
    reference: str = Field(
        min_length=1,
        max_length=REFERENCE_MAX_LENGTH,
        description="Identificação da solicitação que originou o bloqueio",
        examples=["QA-2026-0042"],
    )
    reason: str | None = Field(
        default=None, max_length=REASON_MAX_LENGTH, examples=["Avaria no transporte"]
    )


class _Response(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProductStockResponse(_Response):
    sku: str
    total: int
    available: int
    reserved: int
    blocked: int


class HoldResponse(_Response):
    id: UUID
    sku: str
    type: str
    quantity: int
    reference: str
    reason: str | None
    status: str
    created_at: datetime
    closed_at: datetime | None


class ProductDetailsResponse(ProductStockResponse):
    active_holds: list[HoldResponse]


class MovementResponse(_Response):
    id: UUID
    sku: str
    type: str
    quantity: int
    hold_id: UUID | None
    occurred_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: str
