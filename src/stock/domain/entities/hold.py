"""Reserva ou bloqueio de unidades de um produto."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from stock.domain.exceptions import (
    HoldNotActiveError,
    InvalidHoldDataError,
    InvalidHoldOperationError,
)
from stock.domain.value_objects import Quantity, Sku

REFERENCE_MAX_LENGTH = 128
REASON_MAX_LENGTH = 255


class HoldType(StrEnum):
    RESERVATION = "RESERVATION"
    BLOCK = "BLOCK"


class HoldStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    CONSUMED = "CONSUMED"


@dataclass(slots=True)
class Hold:
    """Retenção de unidades: uma reserva (para um pedido) ou um bloqueio.

    Reserva e bloqueio têm o mesmo ciclo de vida (criar, consultar, liberar), por isso
    são uma única entidade diferenciada por ``type``, e não duas tabelas/classes quase
    iguais. ``reference`` identifica a solicitação/pedido de origem e permite vários
    holds simultâneos por produto e por solicitação.

    Estados: ACTIVE -> RELEASED (liberado) | CONSUMED (reserva baixada do estoque).
    Estados finais são imutáveis.
    """

    id: UUID
    sku: Sku
    type: HoldType
    quantity: Quantity
    reference: str
    reason: str | None
    status: HoldStatus
    created_at: datetime
    closed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        sku: Sku,
        hold_type: HoldType,
        quantity: Quantity,
        reference: str,
        reason: str | None,
        now: datetime,
    ) -> "Hold":
        return cls(
            id=uuid4(),
            sku=sku,
            type=hold_type,
            quantity=quantity,
            reference=_validate_reference(reference),
            reason=_validate_reason(reason),
            status=HoldStatus.ACTIVE,
            created_at=now,
        )

    @property
    def is_active(self) -> bool:
        return self.status is HoldStatus.ACTIVE

    def release(self, now: datetime) -> None:
        self._close(HoldStatus.RELEASED, now)

    def consume(self, now: datetime) -> None:
        """Baixa uma reserva: as unidades saem fisicamente do estoque.

        Bloqueios não são consumíveis: unidade bloqueada precisa ser liberada
        (ou, numa evolução, ter um fluxo próprio de descarte/perda).
        """
        if self.type is not HoldType.RESERVATION:
            raise InvalidHoldOperationError("Apenas reservas podem ser consumidas.")
        self._close(HoldStatus.CONSUMED, now)

    def _close(self, final_status: HoldStatus, now: datetime) -> None:
        if not self.is_active:
            raise HoldNotActiveError(self.id, self.status.value)
        self.status = final_status
        self.closed_at = now


def _validate_reference(reference: str) -> str:
    normalized = reference.strip()
    if not normalized:
        raise InvalidHoldDataError("A referência da solicitação é obrigatória.")
    if len(normalized) > REFERENCE_MAX_LENGTH:
        raise InvalidHoldDataError(
            f"A referência deve ter no máximo {REFERENCE_MAX_LENGTH} caracteres."
        )
    return normalized


def _validate_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    normalized = reason.strip()
    if len(normalized) > REASON_MAX_LENGTH:
        raise InvalidHoldDataError(f"O motivo deve ter no máximo {REASON_MAX_LENGTH} caracteres.")
    return normalized or None
