"""Regras de negócio do produto (seções 3 e 4 do enunciado)."""

from datetime import UTC, datetime

import pytest

from stock.domain.entities import MAX_PRODUCT_STOCK, HoldStatus, HoldType, Product
from stock.domain.exceptions import (
    HoldNotActiveError,
    InsufficientAvailableStockError,
    InvalidHoldDataError,
    InvalidHoldOperationError,
    StockInvariantViolationError,
    StockLimitExceededError,
)
from stock.domain.value_objects import Quantity, Sku

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


def make_product(total: int = 0) -> Product:
    product = Product.new(Sku("SKU-1"))
    if total:
        product.register_entry(Quantity(total))
    return product


def snapshot(product: Product) -> tuple[int, int, int, int]:
    return product.total, product.available, product.reserved, product.blocked


class TestEntry:
    def test_new_product_starts_empty(self) -> None:
        assert snapshot(make_product()) == (0, 0, 0, 0)

    def test_entry_increases_total_and_available(self) -> None:
        product = make_product(10)
        product.register_entry(Quantity(5))
        assert snapshot(product) == (15, 15, 0, 0)

    def test_entry_cannot_exceed_product_limit(self) -> None:
        product = Product(sku=Sku("SKU-1"), total=MAX_PRODUCT_STOCK)
        with pytest.raises(StockLimitExceededError):
            product.register_entry(Quantity(1))
        assert product.total == MAX_PRODUCT_STOCK


class TestExit:
    def test_exit_decreases_total_and_available(self) -> None:
        product = make_product(10)
        product.register_exit(Quantity(4))
        assert snapshot(product) == (6, 6, 0, 0)

    def test_exit_of_exactly_the_available_quantity_is_allowed(self) -> None:
        product = make_product(10)
        product.register_exit(Quantity(10))
        assert snapshot(product) == (0, 0, 0, 0)

    def test_exit_above_available_is_rejected_and_state_is_unchanged(self) -> None:
        product = make_product(10)
        with pytest.raises(InsufficientAvailableStockError) as exc:
            product.register_exit(Quantity(11))
        assert (exc.value.requested, exc.value.available) == (11, 10)
        assert snapshot(product) == (10, 10, 0, 0)

    def test_exit_cannot_take_reserved_or_blocked_units(self) -> None:
        product = make_product(10)
        product.reserve(Quantity(4), reference="PED-1", now=NOW)
        product.block(Quantity(3), reference="QA-1", reason="avaria", now=NOW)
        with pytest.raises(InsufficientAvailableStockError):
            product.register_exit(Quantity(4))
        assert snapshot(product) == (10, 3, 4, 3)


class TestReserve:
    def test_reserve_moves_units_from_available_to_reserved(self) -> None:
        product = make_product(10)
        hold = product.reserve(Quantity(3), reference="PED-1", now=NOW)
        assert snapshot(product) == (10, 7, 3, 0)
        assert hold.type is HoldType.RESERVATION
        assert hold.status is HoldStatus.ACTIVE
        assert hold.reference == "PED-1"
        assert hold.created_at == NOW

    def test_reserve_above_available_is_rejected(self) -> None:
        product = make_product(5)
        with pytest.raises(InsufficientAvailableStockError):
            product.reserve(Quantity(6), reference="PED-1", now=NOW)
        assert snapshot(product) == (5, 5, 0, 0)

    def test_multiple_reservations_for_different_requests_coexist(self) -> None:
        product = make_product(10)
        first = product.reserve(Quantity(2), reference="PED-1", now=NOW)
        second = product.reserve(Quantity(3), reference="PED-2", now=NOW)
        third = product.reserve(Quantity(1), reference="PED-1", now=NOW)
        assert len({first.id, second.id, third.id}) == 3
        assert snapshot(product) == (10, 4, 6, 0)

    @pytest.mark.parametrize("reference", ["", "   ", "X" * 129])
    def test_reserve_requires_a_valid_reference(self, reference: str) -> None:
        product = make_product(10)
        with pytest.raises(InvalidHoldDataError):
            product.reserve(Quantity(1), reference=reference, now=NOW)
        assert snapshot(product) == (10, 10, 0, 0)


class TestBlock:
    def test_block_moves_units_from_available_to_blocked(self) -> None:
        product = make_product(10)
        hold = product.block(Quantity(4), reference="QA-9", reason=" avaria ", now=NOW)
        assert snapshot(product) == (10, 6, 0, 4)
        assert hold.type is HoldType.BLOCK
        assert hold.reason == "avaria"

    def test_block_above_available_is_rejected(self) -> None:
        product = make_product(10)
        product.reserve(Quantity(8), reference="PED-1", now=NOW)
        with pytest.raises(InsufficientAvailableStockError):
            product.block(Quantity(3), reference="QA-1", reason=None, now=NOW)
        assert snapshot(product) == (10, 2, 8, 0)

    def test_blank_reason_is_normalized_to_none(self) -> None:
        hold = make_product(1).block(Quantity(1), reference="QA-1", reason="  ", now=NOW)
        assert hold.reason is None


class TestRelease:
    def test_releasing_a_reservation_returns_units_to_available(self) -> None:
        product = make_product(10)
        hold = product.reserve(Quantity(3), reference="PED-1", now=NOW)
        product.release(hold, now=NOW)
        assert snapshot(product) == (10, 10, 0, 0)
        assert hold.status is HoldStatus.RELEASED
        assert hold.closed_at == NOW

    def test_releasing_a_block_returns_units_to_available(self) -> None:
        product = make_product(10)
        hold = product.block(Quantity(3), reference="QA-1", reason=None, now=NOW)
        product.release(hold, now=NOW)
        assert snapshot(product) == (10, 10, 0, 0)

    def test_releasing_one_hold_keeps_the_others(self) -> None:
        product = make_product(10)
        first = product.reserve(Quantity(2), reference="PED-1", now=NOW)
        product.reserve(Quantity(3), reference="PED-2", now=NOW)
        product.block(Quantity(1), reference="QA-1", reason=None, now=NOW)
        product.release(first, now=NOW)
        assert snapshot(product) == (10, 6, 3, 1)

    def test_releasing_twice_is_rejected_and_does_not_double_count(self) -> None:
        product = make_product(10)
        hold = product.reserve(Quantity(3), reference="PED-1", now=NOW)
        product.release(hold, now=NOW)
        with pytest.raises(HoldNotActiveError):
            product.release(hold, now=NOW)
        assert snapshot(product) == (10, 10, 0, 0)

    def test_hold_from_another_product_is_rejected(self) -> None:
        other = Product.new(Sku("OTHER"))
        other.register_entry(Quantity(5))
        foreign_hold = other.reserve(Quantity(1), reference="PED-1", now=NOW)
        with pytest.raises(StockInvariantViolationError):
            make_product(10).release(foreign_hold, now=NOW)


class TestConsumeReservation:
    def test_consuming_a_reservation_removes_units_from_stock(self) -> None:
        product = make_product(10)
        hold = product.reserve(Quantity(3), reference="PED-1", now=NOW)
        product.consume_reservation(hold, now=NOW)
        assert snapshot(product) == (7, 7, 0, 0)
        assert hold.status is HoldStatus.CONSUMED

    def test_blocks_cannot_be_consumed(self) -> None:
        product = make_product(10)
        hold = product.block(Quantity(3), reference="QA-1", reason=None, now=NOW)
        with pytest.raises(InvalidHoldOperationError):
            product.consume_reservation(hold, now=NOW)
        assert snapshot(product) == (10, 7, 0, 3)

    def test_consumed_reservation_cannot_be_released(self) -> None:
        product = make_product(10)
        hold = product.reserve(Quantity(3), reference="PED-1", now=NOW)
        product.consume_reservation(hold, now=NOW)
        with pytest.raises(HoldNotActiveError):
            product.release(hold, now=NOW)
        assert snapshot(product) == (7, 7, 0, 0)
