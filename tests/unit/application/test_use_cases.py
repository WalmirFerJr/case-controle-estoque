"""Orquestração dos casos de uso com repositórios em memória.

Foco: o que é persistido (saldos, holds, ledger) e o que NÃO é quando algo falha.
As regras em si estão cobertas nos testes de domínio.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from stock.application.dtos import BlockStockCommand, ReserveStockCommand, StockQuantityCommand
from stock.application.use_cases import (
    BlockStock,
    ConsumeReservation,
    GetHold,
    GetProductStock,
    ListHolds,
    ListHoldsQuery,
    ListMovements,
    RegisterEntry,
    RegisterExit,
    ReleaseHold,
    ReserveStock,
)
from stock.domain.entities import MovementType
from stock.domain.exceptions import (
    HoldNotActiveError,
    HoldNotFoundError,
    InsufficientAvailableStockError,
    InvalidQuantityError,
    InvalidSkuError,
    ProductNotFoundError,
)
from stock.domain.services.ledger import replay
from tests.fakes import InMemoryUnitOfWork

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return NOW


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


def seed(uow: InMemoryUnitOfWork, sku: str = "SKU-1", quantity: int = 10) -> None:
    RegisterEntry(uow, fixed_clock).execute(StockQuantityCommand(sku, quantity))


def ledger_types(uow: InMemoryUnitOfWork) -> list[MovementType]:
    return [m.type for m in uow.committed.movements]


class TestRegisterEntry:
    def test_first_entry_creates_the_product(self, uow: InMemoryUnitOfWork) -> None:
        view = RegisterEntry(uow, fixed_clock).execute(StockQuantityCommand("SKU-1", 10))
        assert (view.sku, view.total, view.available) == ("SKU-1", 10, 10)
        assert ledger_types(uow) == [MovementType.ENTRY]

    def test_subsequent_entries_accumulate(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow, quantity=10)
        view = RegisterEntry(uow, fixed_clock).execute(StockQuantityCommand("SKU-1", 5))
        assert view.total == 15

    @pytest.mark.parametrize(
        ("sku", "quantity", "error"),
        [("SKU-1", 0, InvalidQuantityError), ("bad sku", 1, InvalidSkuError)],
    )
    def test_invalid_input_persists_nothing(
        self, uow: InMemoryUnitOfWork, sku: str, quantity: int, error: type[Exception]
    ) -> None:
        with pytest.raises(error):
            RegisterEntry(uow, fixed_clock).execute(StockQuantityCommand(sku, quantity))
        assert uow.commits == 0
        assert uow.committed.products == {}


class TestRegisterExit:
    def test_exit_updates_stock_and_ledger(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow)
        view = RegisterExit(uow, fixed_clock).execute(StockQuantityCommand("SKU-1", 4))
        assert (view.total, view.available) == (6, 6)
        assert ledger_types(uow) == [MovementType.ENTRY, MovementType.EXIT]

    def test_exit_of_unknown_product_fails(self, uow: InMemoryUnitOfWork) -> None:
        with pytest.raises(ProductNotFoundError):
            RegisterExit(uow, fixed_clock).execute(StockQuantityCommand("NOPE", 1))

    def test_rejected_exit_persists_nothing(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow)
        with pytest.raises(InsufficientAvailableStockError):
            RegisterExit(uow, fixed_clock).execute(StockQuantityCommand("SKU-1", 11))
        assert uow.committed.products[next(iter(uow.committed.products))].total == 10
        assert ledger_types(uow) == [MovementType.ENTRY]


class TestHolds:
    def test_reserve_persists_hold_and_movement(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow)
        hold = ReserveStock(uow, fixed_clock).execute(ReserveStockCommand("SKU-1", 3, "PED-1"))
        assert hold.status == "ACTIVE"
        assert GetHold(uow).execute(hold.id) == hold
        assert uow.committed.movements[-1].hold_id == hold.id
        assert GetProductStock(uow).execute("SKU-1").stock.reserved == 3

    def test_block_persists_hold_and_movement(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow)
        hold = BlockStock(uow, fixed_clock).execute(
            BlockStockCommand("SKU-1", 2, "QA-1", reason="avaria")
        )
        assert (hold.type, hold.reason) == ("BLOCK", "avaria")
        assert GetProductStock(uow).execute("SKU-1").stock.blocked == 2

    def test_reserve_unknown_product_fails(self, uow: InMemoryUnitOfWork) -> None:
        with pytest.raises(ProductNotFoundError):
            ReserveStock(uow, fixed_clock).execute(ReserveStockCommand("NOPE", 1, "PED-1"))

    def test_release_returns_units_and_records_movement(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow)
        reservation = ReserveStock(uow, fixed_clock).execute(
            ReserveStockCommand("SKU-1", 3, "PED-1")
        )
        block = BlockStock(uow, fixed_clock).execute(BlockStockCommand("SKU-1", 2, "QA-1"))

        released = ReleaseHold(uow, fixed_clock).execute(reservation.id)
        ReleaseHold(uow, fixed_clock).execute(block.id)

        assert (released.status, released.closed_at) == ("RELEASED", NOW)
        assert GetProductStock(uow).execute("SKU-1").stock.available == 10
        assert ledger_types(uow)[-2:] == [
            MovementType.RELEASE_RESERVATION,
            MovementType.RELEASE_BLOCK,
        ]

    def test_release_twice_fails_without_side_effects(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow)
        hold = ReserveStock(uow, fixed_clock).execute(ReserveStockCommand("SKU-1", 3, "PED-1"))
        ReleaseHold(uow, fixed_clock).execute(hold.id)
        movements_before = len(uow.committed.movements)
        with pytest.raises(HoldNotActiveError):
            ReleaseHold(uow, fixed_clock).execute(hold.id)
        assert len(uow.committed.movements) == movements_before

    def test_release_unknown_hold_fails(self, uow: InMemoryUnitOfWork) -> None:
        with pytest.raises(HoldNotFoundError):
            ReleaseHold(uow, fixed_clock).execute(uuid4())

    def test_get_unknown_hold_fails(self, uow: InMemoryUnitOfWork) -> None:
        with pytest.raises(HoldNotFoundError):
            GetHold(uow).execute(uuid4())

    def test_consume_reservation_removes_units(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow)
        hold = ReserveStock(uow, fixed_clock).execute(ReserveStockCommand("SKU-1", 3, "PED-1"))
        consumed = ConsumeReservation(uow, fixed_clock).execute(hold.id)
        stock = GetProductStock(uow).execute("SKU-1").stock
        assert consumed.status == "CONSUMED"
        assert (stock.total, stock.reserved, stock.available) == (7, 0, 7)


class TestQueries:
    def test_product_details_lists_only_active_holds(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow)
        reserve = ReserveStock(uow, fixed_clock)
        kept = reserve.execute(ReserveStockCommand("SKU-1", 1, "PED-1"))
        released = reserve.execute(ReserveStockCommand("SKU-1", 1, "PED-2"))
        ReleaseHold(uow, fixed_clock).execute(released.id)

        details = GetProductStock(uow).execute("SKU-1")
        assert [h.id for h in details.active_holds] == [kept.id]

    def test_unknown_product_details_fails(self, uow: InMemoryUnitOfWork) -> None:
        with pytest.raises(ProductNotFoundError):
            GetProductStock(uow).execute("NOPE")

    def test_list_holds_by_reference(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow, "A")
        seed(uow, "B")
        ReserveStock(uow, fixed_clock).execute(ReserveStockCommand("A", 1, "PED-1"))
        ReserveStock(uow, fixed_clock).execute(ReserveStockCommand("B", 1, "PED-1"))
        BlockStock(uow, fixed_clock).execute(BlockStockCommand("A", 1, "QA-1"))

        by_order = ListHolds(uow).execute(ListHoldsQuery(reference="PED-1"))
        blocks_of_a = ListHolds(uow).execute(ListHoldsQuery(sku="A", hold_type="BLOCK"))

        assert sorted(h.sku for h in by_order) == ["A", "B"]
        assert [h.reference for h in blocks_of_a] == ["QA-1"]

    def test_movements_reconcile_with_stored_balance(self, uow: InMemoryUnitOfWork) -> None:
        seed(uow)
        hold = ReserveStock(uow, fixed_clock).execute(ReserveStockCommand("SKU-1", 3, "PED-1"))
        BlockStock(uow, fixed_clock).execute(BlockStockCommand("SKU-1", 2, "QA-1"))
        RegisterExit(uow, fixed_clock).execute(StockQuantityCommand("SKU-1", 1))
        ConsumeReservation(uow, fixed_clock).execute(hold.id)

        history = ListMovements(uow).execute("SKU-1")
        stock = GetProductStock(uow).execute("SKU-1").stock
        balance = replay(uow.committed.movements)

        assert len(history) == 5
        assert (balance.total, balance.reserved, balance.blocked) == (
            stock.total,
            stock.reserved,
            stock.blocked,
        )

    def test_movements_of_unknown_product_fails(self, uow: InMemoryUnitOfWork) -> None:
        with pytest.raises(ProductNotFoundError):
            ListMovements(uow).execute("NOPE")
