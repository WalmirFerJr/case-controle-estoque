"""Passos comuns entre casos de uso."""

from uuid import UUID

from stock.application.ports import UnitOfWork
from stock.domain.entities import Hold, Product
from stock.domain.exceptions import HoldNotFoundError, ProductNotFoundError
from stock.domain.value_objects import Sku


def lock_product(uow: UnitOfWork, sku: Sku) -> Product:
    product = uow.products.get_for_update(sku)
    if product is None:
        raise ProductNotFoundError(sku.value)
    return product


def lock_hold_with_product(uow: UnitOfWork, hold_id: UUID) -> tuple[Product, Hold]:
    """Trava produto e hold **sempre nesta ordem** (produto -> hold).

    Todas as operações travam o produto primeiro; manter a mesma ordem aqui evita
    deadlock entre uma liberação e uma reserva simultâneas. O hold é relido após o
    lock para enxergar o status mais recente (ex.: outra liberação já confirmada).
    """
    unlocked = uow.holds.get(hold_id)
    if unlocked is None:
        raise HoldNotFoundError(hold_id)
    product = lock_product(uow, unlocked.sku)
    hold = uow.holds.get_for_update(hold_id)
    if hold is None:  # pragma: no cover - holds nunca são apagados
        raise HoldNotFoundError(hold_id)
    return product, hold
