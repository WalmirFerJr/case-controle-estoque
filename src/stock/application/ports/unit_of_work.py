from types import TracebackType
from typing import Protocol, Self

from stock.application.ports.repositories import (
    HoldRepository,
    MovementRepository,
    ProductRepository,
)


class UnitOfWork(Protocol):
    """Fronteira transacional: tudo dentro do ``with`` é atômico.

    Sair do bloco sem ``commit()`` (inclusive por exceção) desfaz tudo. É isso que
    garante que uma operação inválida nunca deixa o estoque inconsistente.
    """

    products: ProductRepository
    holds: HoldRepository
    movements: MovementRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
