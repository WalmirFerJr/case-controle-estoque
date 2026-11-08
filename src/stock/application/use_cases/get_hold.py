from uuid import UUID

from stock.application.dtos import HoldView
from stock.application.ports import UnitOfWork
from stock.domain.exceptions import HoldNotFoundError


class GetHold:
    """Consulta uma reserva ou bloqueio pela sua identificação."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, hold_id: UUID) -> HoldView:
        with self._uow as uow:
            hold = uow.holds.get(hold_id)
            if hold is None:
                raise HoldNotFoundError(hold_id)
            return HoldView.from_entity(hold)
