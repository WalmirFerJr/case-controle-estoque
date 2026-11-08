from uuid import UUID

from stock.application.dtos import HoldView
from stock.application.ports import Clock, UnitOfWork, utc_now
from stock.application.use_cases._shared import lock_hold_with_product
from stock.domain.entities import HoldType, MovementType, StockMovement


class ReleaseHold:
    """Libera uma reserva ou bloqueio ativo, devolvendo as unidades ao disponível."""

    def __init__(self, uow: UnitOfWork, clock: Clock = utc_now) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, hold_id: UUID) -> HoldView:
        with self._uow as uow:
            product, hold = lock_hold_with_product(uow, hold_id)
            now = self._clock()
            product.release(hold, now=now)
            movement_type = (
                MovementType.RELEASE_RESERVATION
                if hold.type is HoldType.RESERVATION
                else MovementType.RELEASE_BLOCK
            )
            uow.products.save(product)
            uow.holds.save(hold)
            uow.movements.add(
                StockMovement.record(
                    sku=hold.sku,
                    movement_type=movement_type,
                    quantity=hold.quantity,
                    hold_id=hold.id,
                    now=now,
                )
            )
            uow.commit()
            return HoldView.from_entity(hold)
