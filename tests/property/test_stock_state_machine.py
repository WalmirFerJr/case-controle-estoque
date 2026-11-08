"""Property-based: qualquer sequência de operações preserva as invariantes do estoque.

O hypothesis gera centenas de sequências aleatórias (entradas, saídas, reservas,
bloqueios, liberações, consumos, inclusive operações inválidas) e compara o
``Product`` com um modelo de referência propositalmente ingênuo. Isso encontra
combinações de borda que ninguém pensaria em escrever à mão.
"""

from datetime import UTC, datetime

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    consumes,
    invariant,
    multiple,
    rule,
)

from stock.domain.entities import Hold, HoldStatus, HoldType, Product, StockMovement
from stock.domain.entities.stock_movement import MovementType
from stock.domain.exceptions import (
    HoldNotActiveError,
    InsufficientAvailableStockError,
    InvalidHoldOperationError,
)
from stock.domain.services.ledger import replay
from stock.domain.value_objects import Quantity, Sku

NOW = datetime(2026, 11, 8, tzinfo=UTC)
quantities = st.integers(min_value=1, max_value=50)


class StockMachine(RuleBasedStateMachine):
    holds = Bundle("holds")

    def __init__(self) -> None:
        super().__init__()
        self.product = Product.new(Sku("PROP"))
        self.model_total = 0
        self.model_holds: dict[object, tuple[HoldType, int]] = {}  # apenas holds ativos
        self.ledger: list[StockMovement] = []

    # -------------------------------------------------------------- helpers
    def _model_available(self) -> int:
        held = sum(qty for _, qty in self.model_holds.values())
        return self.model_total - held

    def _record(self, kind: MovementType, qty: int, hold: Hold | None = None) -> None:
        self.ledger.append(
            StockMovement.record(
                sku=self.product.sku,
                movement_type=kind,
                quantity=Quantity(qty),
                now=NOW,
                hold_id=hold.id if hold else None,
            )
        )

    # -------------------------------------------------------------- regras
    @rule(qty=quantities)
    def entry(self, qty: int) -> None:
        self.product.register_entry(Quantity(qty))
        self.model_total += qty
        self._record(MovementType.ENTRY, qty)

    @rule(qty=quantities)
    def exit(self, qty: int) -> None:
        if qty <= self._model_available():
            self.product.register_exit(Quantity(qty))
            self.model_total -= qty
            self._record(MovementType.EXIT, qty)
        else:
            self._expect_rejection(lambda: self.product.register_exit(Quantity(qty)))

    @rule(target=holds, qty=quantities, kind=st.sampled_from(HoldType))
    def create_hold(self, qty: int, kind: HoldType) -> object:
        def act() -> Hold:
            if kind is HoldType.RESERVATION:
                return self.product.reserve(Quantity(qty), reference="REF", now=NOW)
            return self.product.block(Quantity(qty), reference="REF", reason=None, now=NOW)

        if qty > self._model_available():
            self._expect_rejection(act)
            return multiple()
        hold = act()
        self.model_holds[hold.id] = (kind, qty)
        self._record(
            MovementType.RESERVE if kind is HoldType.RESERVATION else MovementType.BLOCK, qty, hold
        )
        return hold

    @rule(hold=consumes(holds))
    def release(self, hold: Hold) -> None:
        self.product.release(hold, now=NOW)
        kind, qty = self.model_holds.pop(hold.id)
        self._record(
            MovementType.RELEASE_RESERVATION
            if kind is HoldType.RESERVATION
            else MovementType.RELEASE_BLOCK,
            qty,
            hold,
        )
        assert hold.status is HoldStatus.RELEASED
        # Liberar de novo nunca pode contar duas vezes.
        self._expect_rejection(lambda: self.product.release(hold, now=NOW), HoldNotActiveError)

    @rule(hold=consumes(holds))
    def consume(self, hold: Hold) -> None:
        if hold.type is HoldType.BLOCK:
            self._expect_rejection(
                lambda: self.product.consume_reservation(hold, now=NOW), InvalidHoldOperationError
            )
            self.product.release(hold, now=NOW)  # devolve para manter o modelo simples
            _, qty = self.model_holds.pop(hold.id)
            self._record(MovementType.RELEASE_BLOCK, qty, hold)
            return
        self.product.consume_reservation(hold, now=NOW)
        _, qty = self.model_holds.pop(hold.id)
        self.model_total -= qty
        self._record(MovementType.CONSUME_RESERVATION, qty, hold)

    def _expect_rejection(
        self,
        action: object,
        error: type[Exception] = InsufficientAvailableStockError,
    ) -> None:
        before = (self.product.total, self.product.reserved, self.product.blocked)
        try:
            action()  # type: ignore[operator]
        except error:
            pass
        else:
            raise AssertionError("Operação inválida deveria ter sido rejeitada")
        after = (self.product.total, self.product.reserved, self.product.blocked)
        assert before == after, "Operação rejeitada não pode alterar o estado"

    # -------------------------------------------------------------- invariantes
    @invariant()
    def balances_match_the_reference_model(self) -> None:
        reserved = sum(q for k, q in self.model_holds.values() if k is HoldType.RESERVATION)
        blocked = sum(q for k, q in self.model_holds.values() if k is HoldType.BLOCK)
        assert self.product.total == self.model_total
        assert self.product.reserved == reserved
        assert self.product.blocked == blocked
        assert self.product.available == self._model_available()

    @invariant()
    def stock_is_never_inconsistent(self) -> None:
        p = self.product
        assert min(p.total, p.reserved, p.blocked, p.available) >= 0
        assert p.reserved + p.blocked <= p.total

    @invariant()
    def ledger_replay_matches_balances(self) -> None:
        balance = replay(self.ledger)
        assert (balance.total, balance.reserved, balance.blocked) == (
            self.product.total,
            self.product.reserved,
            self.product.blocked,
        )


StockMachine.TestCase.settings = settings(max_examples=200, stateful_step_count=40, deadline=None)
TestStockStateMachine = StockMachine.TestCase
