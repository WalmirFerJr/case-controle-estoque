"""Quantidade de uma operação de estoque."""

from dataclasses import dataclass

from stock.domain.exceptions import InvalidQuantityError

MAX_OPERATION_QUANTITY = 1_000_000
"""Teto por operação: protege contra erro de digitação e overflow (premissa documentada)."""


@dataclass(frozen=True, slots=True)
class Quantity:
    """Quantidade inteira e positiva movimentada em uma operação.

    Validar na criação torna impossível representar uma operação com 0, negativo
    ou fracionado: o restante do domínio confia que a quantidade é válida.
    """

    value: int

    def __post_init__(self) -> None:
        # bool é subclasse de int em Python; True não pode virar "1 unidade".
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise InvalidQuantityError("A quantidade deve ser um número inteiro.")
        if self.value <= 0:
            raise InvalidQuantityError("A quantidade deve ser maior que zero.")
        if self.value > MAX_OPERATION_QUANTITY:
            raise InvalidQuantityError(
                f"A quantidade por operação não pode exceder {MAX_OPERATION_QUANTITY}."
            )

    def __int__(self) -> int:
        return self.value
