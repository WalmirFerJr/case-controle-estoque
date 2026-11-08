from uuid import UUID

from stock.application.dtos import HoldView
from stock.application.ports import Clock, UnitOfWork, utc_now
from stock.application.use_cases._shared import lock_hold_with_product
from stock.domain.entities import MovementType, StockMovement


class ConsumeReservation:
    """Baixa uma reserva (pedido expedido): as unidades reservadas saem do estoque.

    Não é exigido pelo enunciado, mas fecha o ciclo da reserva: sem ele, a única
    forma de expedir um pedido reservado seria liberar e depois dar saída, abrindo
    uma janela em que outro pedido poderia "roubar" as unidades.
    """

    def __init__(self, uow: UnitOfWork, clock: Clock = utc_now) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, hold_id: UUID) -> HoldView:
        with self._uow as uow:
            product, hold = lock_hold_with_product(uow, hold_id)
            now = self._clock()
            product.consume_reservation(hold, now=now)
            uow.products.save(product)
            uow.holds.save(hold)
            uow.movements.add(
                StockMovement.record(
                    sku=hold.sku,
                    movement_type=MovementType.CONSUME_RESERVATION,
                    quantity=hold.quantity,
                    hold_id=hold.id,
                    now=now,
                )
            )
            uow.commit()
            return HoldView.from_entity(hold)
