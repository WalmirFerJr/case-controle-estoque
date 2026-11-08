"""Reconstrução de saldos a partir do ledger de movimentos."""

from collections.abc import Iterable
from dataclasses import dataclass

from stock.domain.entities.stock_movement import MovementType, StockMovement

# Efeito de cada tipo de movimento sobre (total, reserved, blocked).
_EFFECTS: dict[MovementType, tuple[int, int, int]] = {
    MovementType.ENTRY: (1, 0, 0),
    MovementType.EXIT: (-1, 0, 0),
    MovementType.RESERVE: (0, 1, 0),
    MovementType.RELEASE_RESERVATION: (0, -1, 0),
    MovementType.CONSUME_RESERVATION: (-1, -1, 0),
    MovementType.BLOCK: (0, 0, 1),
    MovementType.RELEASE_BLOCK: (0, 0, -1),
}


@dataclass(frozen=True, slots=True)
class LedgerBalance:
    total: int = 0
    reserved: int = 0
    blocked: int = 0

    @property
    def available(self) -> int:
        return self.total - self.reserved - self.blocked


def replay(movements: Iterable[StockMovement]) -> LedgerBalance:
    """Recalcula os saldos somando os movimentos.

    Usado nos testes para provar que saldo armazenado == histórico, e é a base
    de um job de reconciliação em produção.
    """
    total = reserved = blocked = 0
    for movement in movements:
        d_total, d_reserved, d_blocked = _EFFECTS[movement.type]
        qty = movement.quantity.value
        total += d_total * qty
        reserved += d_reserved * qty
        blocked += d_blocked * qty
    return LedgerBalance(total=total, reserved=reserved, blocked=blocked)
