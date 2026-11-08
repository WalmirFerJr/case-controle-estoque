from stock.application.dtos import HoldView, ProductStockDetailsView, ProductStockView
from stock.application.ports import HoldFilters, UnitOfWork
from stock.domain.entities import HoldStatus
from stock.domain.exceptions import ProductNotFoundError
from stock.domain.value_objects import Sku

MAX_ACTIVE_HOLDS_IN_DETAILS = 100


class GetProductStock:
    """Consulta a situação atual do produto e seus holds ativos."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, sku_value: str) -> ProductStockDetailsView:
        sku = Sku(sku_value)
        with self._uow as uow:
            product = uow.products.get(sku)
            if product is None:
                raise ProductNotFoundError(sku.value)
            holds = uow.holds.list(
                HoldFilters(sku=sku, status=HoldStatus.ACTIVE, limit=MAX_ACTIVE_HOLDS_IN_DETAILS)
            )
            return ProductStockDetailsView(
                stock=ProductStockView.from_entity(product),
                active_holds=[HoldView.from_entity(hold) for hold in holds],
            )
