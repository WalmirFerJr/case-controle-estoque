import pytest

from stock.domain.exceptions import InvalidQuantityError, InvalidSkuError
from stock.domain.value_objects import MAX_OPERATION_QUANTITY, Quantity, Sku


class TestQuantity:
    @pytest.mark.parametrize("value", [1, 7, MAX_OPERATION_QUANTITY])
    def test_accepts_positive_integers_up_to_the_limit(self, value: int) -> None:
        assert Quantity(value).value == value

    @pytest.mark.parametrize("value", [0, -1, MAX_OPERATION_QUANTITY + 1])
    def test_rejects_out_of_range_values(self, value: int) -> None:
        with pytest.raises(InvalidQuantityError):
            Quantity(value)

    @pytest.mark.parametrize("value", [1.5, "3", True, None])
    def test_rejects_non_integer_values(self, value: object) -> None:
        with pytest.raises(InvalidQuantityError):
            Quantity(value)  # type: ignore[arg-type]

    def test_is_immutable_value_object(self) -> None:
        assert Quantity(3) == Quantity(3)
        with pytest.raises(AttributeError):
            Quantity(3).value = 4  # type: ignore[misc]


class TestSku:
    @pytest.mark.parametrize("value", ["A", "SKU-123", "abc_01.v2", "X" * 64])
    def test_accepts_valid_codes(self, value: str) -> None:
        assert str(Sku(value)) == value

    @pytest.mark.parametrize("value", ["", " ", "-abc", "has space", "a/b", "X" * 65, "ção"])
    def test_rejects_invalid_codes(self, value: str) -> None:
        with pytest.raises(InvalidSkuError):
            Sku(value)
