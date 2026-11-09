"""Contrato HTTP (Pydantic). Validação de formato na borda; regras de negócio no domínio."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from stock.domain.entities import HoldStatus, HoldType, MovementType
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
    sku: str = Field(description="Identificador do produto", examples=["NOTE-15"])
    total: int = Field(description="Unidades fisicamente em estoque", examples=[10])
    available: int = Field(
        description="Livres para saída, reserva ou bloqueio: total - reservado - bloqueado",
        examples=[5],
    )
    reserved: int = Field(description="Soma das reservas ativas", examples=[3])
    blocked: int = Field(description="Soma dos bloqueios ativos", examples=[2])


class HoldResponse(_Response):
    id: UUID = Field(description="Use em /holds/{hold_id} para consultar, liberar ou consumir")
    sku: str
    type: HoldType = Field(description="RESERVATION (reserva) ou BLOCK (bloqueio)")
    quantity: int
    reference: str = Field(description="Solicitação/pedido de origem")
    reason: str | None = Field(description="Motivo do bloqueio (opcional)")
    status: HoldStatus = Field(description="ACTIVE até ser liberado (RELEASED) ou consumido")
    created_at: datetime
    closed_at: datetime | None = Field(description="Preenchido quando o hold deixa de ser ACTIVE")


class ProductDetailsResponse(ProductStockResponse):
    active_holds: list[HoldResponse] = Field(description="Reservas e bloqueios ainda ativos")


class MovementResponse(_Response):
    id: UUID
    sku: str
    type: MovementType
    quantity: int
    hold_id: UUID | None = Field(description="Hold que originou o movimento, se houver")
    occurred_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: str
