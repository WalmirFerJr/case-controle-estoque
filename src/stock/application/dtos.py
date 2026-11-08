"""Objetos de entrada (commands) e saída (views) dos casos de uso.

Isolam o domínio dos adaptadores: a API recebe/devolve estes tipos simples,
nunca entidades.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from stock.domain.entities import Hold, Product, StockMovement

# ------------------------------------------------------------------ commands


@dataclass(frozen=True, slots=True)
class StockQuantityCommand:
    """Entrada ou saída avulsa."""

    sku: str
    quantity: int


@dataclass(frozen=True, slots=True)
class ReserveStockCommand:
    sku: str
    quantity: int
    reference: str


@dataclass(frozen=True, slots=True)
class BlockStockCommand:
    sku: str
    quantity: int
    reference: str
    reason: str | None = None


# ------------------------------------------------------------------ views


@dataclass(frozen=True, slots=True)
class ProductStockView:
    sku: str
    total: int
    available: int
    reserved: int
    blocked: int

    @classmethod
    def from_entity(cls, product: Product) -> "ProductStockView":
        return cls(
            sku=product.sku.value,
            total=product.total,
            available=product.available,
            reserved=product.reserved,
            blocked=product.blocked,
        )


@dataclass(frozen=True, slots=True)
class HoldView:
    id: UUID
    sku: str
    type: str
    quantity: int
    reference: str
    reason: str | None
    status: str
    created_at: datetime
    closed_at: datetime | None

    @classmethod
    def from_entity(cls, hold: Hold) -> "HoldView":
        return cls(
            id=hold.id,
            sku=hold.sku.value,
            type=hold.type.value,
            quantity=hold.quantity.value,
            reference=hold.reference,
            reason=hold.reason,
            status=hold.status.value,
            created_at=hold.created_at,
            closed_at=hold.closed_at,
        )


@dataclass(frozen=True, slots=True)
class ProductStockDetailsView:
    stock: ProductStockView
    active_holds: list[HoldView]


@dataclass(frozen=True, slots=True)
class MovementView:
    id: UUID
    sku: str
    type: str
    quantity: int
    hold_id: UUID | None
    occurred_at: datetime

    @classmethod
    def from_entity(cls, movement: StockMovement) -> "MovementView":
        return cls(
            id=movement.id,
            sku=movement.sku.value,
            type=movement.type.value,
            quantity=movement.quantity.value,
            hold_id=movement.hold_id,
            occurred_at=movement.occurred_at,
        )
