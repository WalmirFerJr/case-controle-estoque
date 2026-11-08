from stock.application.dtos import MovementView
from stock.application.ports import UnitOfWork
from stock.domain.exceptions import ProductNotFoundError
from stock.domain.value_objects import Sku


class ListMovements:
    """Histórico (ledger) de movimentações de um produto, para auditoria."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, sku_value: str, *, limit: int = 50, offset: int = 0) -> list[MovementView]:
        sku = Sku(sku_value)
        with self._uow as uow:
            if uow.products.get(sku) is None:
                raise ProductNotFoundError(sku.value)
            movements = uow.movements.list_by_sku(sku, limit=limit, offset=offset)
            return [MovementView.from_entity(movement) for movement in movements]
