from datetime import UTC, datetime

from stock.domain.entities import MovementType, StockMovement
from stock.domain.services.ledger import replay
from stock.domain.value_objects import Quantity, Sku

NOW = datetime(2026, 11, 8, tzinfo=UTC)


def movement(kind: MovementType, qty: int) -> StockMovement:
    return StockMovement.record(sku=Sku("A"), movement_type=kind, quantity=Quantity(qty), now=NOW)


def test_replay_of_empty_history_is_zero() -> None:
    assert replay([]).available == 0


def test_replay_applies_every_movement_type() -> None:
    balance = replay(
        [
            movement(MovementType.ENTRY, 20),
            movement(MovementType.EXIT, 2),
            movement(MovementType.RESERVE, 5),
            movement(MovementType.RELEASE_RESERVATION, 1),
            movement(MovementType.CONSUME_RESERVATION, 2),
            movement(MovementType.BLOCK, 4),
            movement(MovementType.RELEASE_BLOCK, 1),
        ]
    )
    assert (balance.total, balance.reserved, balance.blocked) == (16, 2, 3)
    assert balance.available == 11
