from stock.application.dtos import ProductStockView, StockQuantityCommand
from stock.application.ports import Clock, UnitOfWork, utc_now
from stock.application.use_cases._shared import lock_product
from stock.domain.entities import MovementType, StockMovement
from stock.domain.value_objects import Quantity, Sku


class RegisterExit:
    """Saída avulsa: só é feita se houver quantidade disponível suficiente."""

    def __init__(self, uow: UnitOfWork, clock: Clock = utc_now) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, command: StockQuantityCommand) -> ProductStockView:
        sku, quantity = Sku(command.sku), Quantity(command.quantity)
        with self._uow as uow:
            product = lock_product(uow, sku)
            product.register_exit(quantity)
            uow.products.save(product)
            uow.movements.add(
                StockMovement.record(
                    sku=sku, movement_type=MovementType.EXIT, quantity=quantity, now=self._clock()
                )
            )
            uow.commit()
            return ProductStockView.from_entity(product)
