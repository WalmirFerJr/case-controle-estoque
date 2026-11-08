"""Disputa concorrente real contra PostgreSQL.

Cada thread usa sua própria conexão/transação, exatamente como requisições
simultâneas em produção. Uma ``Barrier`` solta todas ao mesmo tempo para
maximizar a contenção. Sem o ``SELECT ... FOR UPDATE`` estes testes falham
(overselling / liberação contada duas vezes).
"""

import random
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.orm import Session, sessionmaker

from stock.application.dtos import BlockStockCommand, ReserveStockCommand, StockQuantityCommand
from stock.application.ports import HoldFilters
from stock.application.use_cases import (
    BlockStock,
    GetProductStock,
    RegisterEntry,
    RegisterExit,
    ReleaseHold,
    ReserveStock,
)
from stock.domain.entities import HoldStatus, HoldType
from stock.domain.exceptions import (
    DomainError,
    HoldNotActiveError,
    InsufficientAvailableStockError,
)
from stock.domain.services.ledger import replay
from stock.domain.value_objects import Sku
from stock.infrastructure.persistence import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.concurrency]

SessionFactory = sessionmaker[Session]


def run_concurrently[T](tasks: list[Callable[[], T]]) -> list[T | Exception]:
    """Executa todas as tarefas em paralelo, começando no mesmo instante."""
    barrier = Barrier(len(tasks))

    def run(task: Callable[[], T]) -> T | Exception:
        barrier.wait()
        try:
            return task()
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        return list(pool.map(run, tasks))


def uow(factory: SessionFactory) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(factory)


def assert_consistent(factory: SessionFactory, sku: str) -> None:
    """Saldos == soma dos holds ativos == replay do ledger, e invariantes válidas."""
    stock = GetProductStock(uow(factory)).execute(sku).stock
    with uow(factory) as unit:
        holds = unit.holds.list(HoldFilters(sku=Sku(sku), status=HoldStatus.ACTIVE, limit=10_000))
        ledger = replay(unit.movements.list_by_sku(Sku(sku), limit=100_000, offset=0))

    active_reserved = sum(h.quantity.value for h in holds if h.type is HoldType.RESERVATION)
    active_blocked = sum(h.quantity.value for h in holds if h.type is HoldType.BLOCK)

    assert stock.available >= 0
    assert stock.reserved + stock.blocked <= stock.total
    assert (stock.reserved, stock.blocked) == (active_reserved, active_blocked)
    assert (ledger.total, ledger.reserved, ledger.blocked) == (
        stock.total,
        stock.reserved,
        stock.blocked,
    )


@pytest.mark.usefixtures("clean_db")
class TestConcurrency:
    def test_no_overselling_when_many_requests_race_for_the_same_units(
        self, session_factory: SessionFactory
    ) -> None:
        RegisterEntry(uow(session_factory)).execute(StockQuantityCommand("HOT", 10))

        results = run_concurrently(
            [
                lambda i=i: ReserveStock(uow(session_factory)).execute(
                    ReserveStockCommand("HOT", 1, f"PED-{i}")
                )
                for i in range(50)
            ]
        )

        outcomes = Counter(type(result).__name__ for result in results)
        assert outcomes == {"HoldView": 10, "InsufficientAvailableStockError": 40}
        stock = GetProductStock(uow(session_factory)).execute("HOT").stock
        assert (stock.available, stock.reserved) == (0, 10)
        assert_consistent(session_factory, "HOT")

    def test_concurrent_exits_never_take_more_than_available(
        self, session_factory: SessionFactory
    ) -> None:
        RegisterEntry(uow(session_factory)).execute(StockQuantityCommand("HOT", 25))

        results = run_concurrently(
            [
                lambda: RegisterExit(uow(session_factory)).execute(StockQuantityCommand("HOT", 3))
                for _ in range(20)
            ]
        )

        successes = [r for r in results if not isinstance(r, Exception)]
        assert len(successes) == 8  # 8 * 3 = 24 <= 25 < 27
        assert all(
            isinstance(r, InsufficientAvailableStockError)
            for r in results
            if isinstance(r, Exception)
        )
        assert GetProductStock(uow(session_factory)).execute("HOT").stock.total == 1
        assert_consistent(session_factory, "HOT")

    def test_same_hold_released_concurrently_is_counted_only_once(
        self, session_factory: SessionFactory
    ) -> None:
        RegisterEntry(uow(session_factory)).execute(StockQuantityCommand("HOT", 10))
        hold = ReserveStock(uow(session_factory)).execute(ReserveStockCommand("HOT", 4, "PED"))

        results = run_concurrently(
            [lambda: ReleaseHold(uow(session_factory)).execute(hold.id) for _ in range(10)]
        )

        errors = [r for r in results if isinstance(r, Exception)]
        assert len(results) - len(errors) == 1
        assert all(isinstance(e, HoldNotActiveError) for e in errors)
        assert GetProductStock(uow(session_factory)).execute("HOT").stock.available == 10
        assert_consistent(session_factory, "HOT")

    def test_first_entries_of_a_new_sku_racing_do_not_collide(
        self, session_factory: SessionFactory
    ) -> None:
        results = run_concurrently(
            [
                lambda: RegisterEntry(uow(session_factory)).execute(StockQuantityCommand("NEW", 1))
                for _ in range(20)
            ]
        )

        assert not [r for r in results if isinstance(r, Exception)]
        assert GetProductStock(uow(session_factory)).execute("NEW").stock.total == 20
        assert_consistent(session_factory, "NEW")

    def test_random_mix_of_operations_preserves_every_invariant(
        self, session_factory: SessionFactory
    ) -> None:
        RegisterEntry(uow(session_factory)).execute(StockQuantityCommand("MIX", 60))
        seed_holds = [
            ReserveStock(uow(session_factory)).execute(ReserveStockCommand("MIX", 2, f"S-{i}")).id
            for i in range(10)
        ]
        rng = random.Random(42)  # determinístico: falha reproduzível

        def random_operation(i: int) -> Callable[[], object]:
            qty = rng.randint(1, 5)
            hold_id = rng.choice(seed_holds)
            operations: dict[str, Callable[[], object]] = {
                "entry": lambda: RegisterEntry(uow(session_factory)).execute(
                    StockQuantityCommand("MIX", qty)
                ),
                "exit": lambda: RegisterExit(uow(session_factory)).execute(
                    StockQuantityCommand("MIX", qty)
                ),
                "reserve": lambda: ReserveStock(uow(session_factory)).execute(
                    ReserveStockCommand("MIX", qty, f"PED-{i}")
                ),
                "block": lambda: BlockStock(uow(session_factory)).execute(
                    BlockStockCommand("MIX", qty, f"QA-{i}")
                ),
                "release": lambda: ReleaseHold(uow(session_factory)).execute(hold_id),
            }
            return operations[rng.choice(sorted(operations))]

        results = run_concurrently([random_operation(i) for i in range(60)])

        unexpected = [
            r for r in results if isinstance(r, Exception) and not isinstance(r, DomainError)
        ]
        assert unexpected == []
        assert_consistent(session_factory, "MIX")
