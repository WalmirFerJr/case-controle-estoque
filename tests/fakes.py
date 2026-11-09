"""Implementações em memória dos ports, para testar casos de uso sem banco.

Simulam a semântica transacional relevante: o que não for ``commit``-ado é
descartado, e entidades lidas são cópias (alterar sem ``save`` não persiste).
"""

from collections.abc import Sequence
from copy import deepcopy
from types import TracebackType
from typing import Self
from uuid import UUID

from stock.application.ports import HoldFilters
from stock.domain.entities import Hold, Product, StockMovement
from stock.domain.value_objects import Sku


class InMemoryStore:
    def __init__(self) -> None:
        self.products: dict[Sku, Product] = {}
        self.holds: dict[UUID, Hold] = {}
        self.movements: list[StockMovement] = []


class InMemoryProductRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def get(self, sku: Sku) -> Product | None:
        return deepcopy(self._store.products.get(sku))

    def get_for_update(self, sku: Sku) -> Product | None:
        return self.get(sku)

    def add_if_absent(self, product: Product) -> None:
        self._store.products.setdefault(product.sku, deepcopy(product))

    def save(self, product: Product) -> None:
        self._store.products[product.sku] = deepcopy(product)

    def list(self, *, limit: int, offset: int) -> Sequence[Product]:
        ordered = sorted(self._store.products.values(), key=lambda p: p.sku.value)
        return deepcopy(ordered[offset : offset + limit])


class InMemoryHoldRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def get(self, hold_id: UUID) -> Hold | None:
        return deepcopy(self._store.holds.get(hold_id))

    def get_for_update(self, hold_id: UUID) -> Hold | None:
        return self.get(hold_id)

    def add(self, hold: Hold) -> None:
        self._store.holds[hold.id] = deepcopy(hold)

    def save(self, hold: Hold) -> None:
        self._store.holds[hold.id] = deepcopy(hold)

    def list(self, filters: HoldFilters) -> Sequence[Hold]:
        matches = [
            hold
            for hold in sorted(self._store.holds.values(), key=lambda h: h.created_at)
            if (filters.sku is None or hold.sku == filters.sku)
            and (filters.reference is None or hold.reference == filters.reference)
            and (filters.hold_type is None or hold.type is filters.hold_type)
            and (filters.status is None or hold.status is filters.status)
        ]
        return deepcopy(matches[filters.offset : filters.offset + filters.limit])


class InMemoryMovementRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def add(self, movement: StockMovement) -> None:
        self._store.movements.append(movement)

    def list_by_sku(self, sku: Sku, *, limit: int, offset: int) -> Sequence[StockMovement]:
        matches = [m for m in self._store.movements if m.sku == sku]
        return matches[offset : offset + limit]


class InMemoryUnitOfWork:
    def __init__(self) -> None:
        self.committed = InMemoryStore()
        self.commits = 0

    def __enter__(self) -> Self:
        self._working = deepcopy(self.committed)
        self.products = InMemoryProductRepository(self._working)
        self.holds = InMemoryHoldRepository(self._working)
        self.movements = InMemoryMovementRepository(self._working)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.rollback()

    def commit(self) -> None:
        self.committed = deepcopy(self._working)
        self.commits += 1

    def rollback(self) -> None:
        self._working = deepcopy(self.committed)
