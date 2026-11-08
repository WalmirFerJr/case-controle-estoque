from dataclasses import dataclass

from stock.application.dtos import HoldView
from stock.application.ports import HoldFilters, UnitOfWork
from stock.domain.entities import HoldStatus, HoldType
from stock.domain.value_objects import Sku


@dataclass(frozen=True, slots=True)
class ListHoldsQuery:
    sku: str | None = None
    reference: str | None = None
    hold_type: str | None = None
    status: str | None = None
    limit: int = 50
    offset: int = 0


class ListHolds:
    """Lista holds por produto, solicitação, tipo e/ou status (consulta por pedido)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, query: ListHoldsQuery) -> list[HoldView]:
        filters = HoldFilters(
            sku=Sku(query.sku) if query.sku else None,
            reference=query.reference,
            hold_type=HoldType(query.hold_type) if query.hold_type else None,
            status=HoldStatus(query.status) if query.status else None,
            limit=query.limit,
            offset=query.offset,
        )
        with self._uow as uow:
            return [HoldView.from_entity(hold) for hold in uow.holds.list(filters)]
