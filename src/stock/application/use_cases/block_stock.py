from stock.application.dtos import BlockStockCommand, HoldView
from stock.application.ports import Clock, UnitOfWork, utc_now
from stock.application.use_cases._shared import lock_product
from stock.domain.entities import MovementType, StockMovement
from stock.domain.value_objects import Quantity, Sku


class BlockStock:
    """Bloqueia unidades disponíveis, tornando-as indisponíveis até a liberação."""

    def __init__(self, uow: UnitOfWork, clock: Clock = utc_now) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, command: BlockStockCommand) -> HoldView:
        sku, quantity = Sku(command.sku), Quantity(command.quantity)
        with self._uow as uow:
            product = lock_product(uow, sku)
            now = self._clock()
            hold = product.block(
                quantity, reference=command.reference, reason=command.reason, now=now
            )
            uow.products.save(product)
            uow.holds.add(hold)
            uow.movements.add(
                StockMovement.record(
                    sku=sku,
                    movement_type=MovementType.BLOCK,
                    quantity=quantity,
                    hold_id=hold.id,
                    now=now,
                )
            )
            uow.commit()
            return HoldView.from_entity(hold)
