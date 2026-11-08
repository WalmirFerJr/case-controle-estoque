"""Registro imutável (ledger) de cada movimentação de estoque."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from stock.domain.value_objects import Quantity, Sku


class MovementType(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    RESERVE = "RESERVE"
    BLOCK = "BLOCK"
    RELEASE_RESERVATION = "RELEASE_RESERVATION"
    RELEASE_BLOCK = "RELEASE_BLOCK"
    CONSUME_RESERVATION = "CONSUME_RESERVATION"


@dataclass(frozen=True, slots=True)
class StockMovement:
    """Fato ocorrido no estoque. Append-only: nunca é alterado nem apagado.

    Serve para auditoria ("quem mexeu, quanto e quando") e para reconciliação:
    o saldo de um produto pode ser reconstruído somando seus movimentos
    (ver ``stock.domain.services.ledger``).
    """

    id: UUID
    sku: Sku
    type: MovementType
    quantity: Quantity
    hold_id: UUID | None
    occurred_at: datetime

    @classmethod
    def record(
        cls,
        *,
        sku: Sku,
        movement_type: MovementType,
        quantity: Quantity,
        now: datetime,
        hold_id: UUID | None = None,
    ) -> "StockMovement":
        return cls(
            id=uuid4(),
            sku=sku,
            type=movement_type,
            quantity=quantity,
            hold_id=hold_id,
            occurred_at=now,
        )
