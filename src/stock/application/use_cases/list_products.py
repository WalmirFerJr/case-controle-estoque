from stock.application.dtos import ProductStockView
from stock.application.ports import UnitOfWork


class ListProducts:
    """Lista a situação de todos os produtos cadastrados, em ordem de SKU.

    Uma única leitura sem lock: os saldos de cada produto vêm da mesma linha, então
    ``available = total - reserved - blocked`` vale para cada item retornado.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, limit: int = 50, offset: int = 0) -> list[ProductStockView]:
        with self._uow as uow:
            products = uow.products.list(limit=limit, offset=offset)
            return [ProductStockView.from_entity(product) for product in products]
