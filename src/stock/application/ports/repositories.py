"""Contratos de persistência: a infraestrutura implementa, a aplicação só conhece os Protocols."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from stock.domain.entities import Hold, HoldStatus, HoldType, Product, StockMovement
from stock.domain.value_objects import Sku


class ProductRepository(Protocol):
    def get(self, sku: Sku) -> Product | None:
        """Leitura sem lock (consultas)."""
        ...

    def get_for_update(self, sku: Sku) -> Product | None:
        """Leitura com lock exclusivo da linha até o fim da transação.

        Toda operação que altera saldo deve usar este método: é o que serializa
        operações concorrentes no mesmo produto e impede vender a mesma unidade duas vezes.
        """
        ...

    def add_if_absent(self, product: Product) -> None:
        """Cria o produto se ainda não existir, sem falhar em corrida de criação."""
        ...

    def save(self, product: Product) -> None: ...


@dataclass(frozen=True, slots=True)
class HoldFilters:
    sku: Sku | None = None
    reference: str | None = None
    hold_type: HoldType | None = None
    status: HoldStatus | None = None
    limit: int = 100
    offset: int = 0


class HoldRepository(Protocol):
    def get(self, hold_id: UUID) -> Hold | None: ...

    def get_for_update(self, hold_id: UUID) -> Hold | None: ...

    def add(self, hold: Hold) -> None: ...

    def save(self, hold: Hold) -> None: ...

    def list(self, filters: HoldFilters) -> Sequence[Hold]: ...


class MovementRepository(Protocol):
    def add(self, movement: StockMovement) -> None: ...

    def list_by_sku(self, sku: Sku, *, limit: int, offset: int) -> Sequence[StockMovement]: ...
