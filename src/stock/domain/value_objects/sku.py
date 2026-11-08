"""Identificação do produto."""

import re
from dataclasses import dataclass

from stock.domain.exceptions import InvalidSkuError

SKU_MAX_LENGTH = 64
_SKU_PATTERN = re.compile(rf"^[A-Za-z0-9][A-Za-z0-9_.\-]{{0,{SKU_MAX_LENGTH - 1}}}$")


@dataclass(frozen=True, slots=True)
class Sku:
    """Código do produto (Stock Keeping Unit).

    Formato restrito (letras, dígitos, ``-``, ``_`` e ``.``) para ser seguro em URLs,
    logs e chaves de banco. Case-sensitive: ``abc`` e ``ABC`` são produtos diferentes.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _SKU_PATTERN.fullmatch(self.value):
            raise InvalidSkuError(
                f"SKU inválido: use de 1 a {SKU_MAX_LENGTH} caracteres entre letras, "
                "dígitos, '-', '_' e '.', começando por letra ou dígito."
            )

    def __str__(self) -> str:
        return self.value
