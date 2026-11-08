from stock.application.dtos import ProductStockView, StockQuantityCommand
from stock.application.ports import Clock, UnitOfWork, utc_now
from stock.application.use_cases._shared import lock_product
from stock.domain.entities import MovementType, Product, StockMovement
from stock.domain.value_objects import Quantity, Sku


class RegisterEntry:
    """Entrada de unidades no estoque.

    Premissa: não existe cadastro de catálogo separado, então a primeira entrada de
    um SKU cria o produto (ver ADR-0004).
    """

    def __init__(self, uow: UnitOfWork, clock: Clock = utc_now) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, command: StockQuantityCommand) -> ProductStockView:
        sku, quantity = Sku(command.sku), Quantity(command.quantity)
        with self._uow as uow:
            uow.products.add_if_absent(Product.new(sku))
            product = lock_product(uow, sku)
            product.register_entry(quantity)
            uow.products.save(product)
            uow.movements.add(
                StockMovement.record(
                    sku=sku, movement_type=MovementType.ENTRY, quantity=quantity, now=self._clock()
                )
            )
            uow.commit()
            return ProductStockView.from_entity(product)
