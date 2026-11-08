"""Exceções de domínio.

Cada regra de negócio violada tem uma exceção própria, com um ``code`` estável.
A camada HTTP apenas traduz essas exceções; ela não decide regra nenhuma.
"""

from uuid import UUID


class DomainError(Exception):
    """Base de todos os erros de regra de negócio."""

    code: str = "DOMAIN_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidQuantityError(DomainError):
    code = "INVALID_QUANTITY"


class InvalidSkuError(DomainError):
    code = "INVALID_SKU"


class InvalidHoldDataError(DomainError):
    code = "INVALID_HOLD_DATA"


class ProductNotFoundError(DomainError):
    code = "PRODUCT_NOT_FOUND"

    def __init__(self, sku: str) -> None:
        super().__init__(f"Produto '{sku}' não encontrado.")
        self.sku = sku


class HoldNotFoundError(DomainError):
    code = "HOLD_NOT_FOUND"

    def __init__(self, hold_id: UUID) -> None:
        super().__init__(f"Reserva/bloqueio '{hold_id}' não encontrado.")
        self.hold_id = hold_id


class InsufficientAvailableStockError(DomainError):
    """Operação pede mais unidades do que as disponíveis (total - reservado - bloqueado)."""

    code = "INSUFFICIENT_AVAILABLE_STOCK"

    def __init__(self, sku: str, requested: int, available: int) -> None:
        super().__init__(
            f"Quantidade solicitada ({requested}) maior que a disponível ({available}) "
            f"para o produto '{sku}'."
        )
        self.sku = sku
        self.requested = requested
        self.available = available


class StockLimitExceededError(DomainError):
    """Entrada levaria o total acima do limite suportado por produto."""

    code = "STOCK_LIMIT_EXCEEDED"


class HoldNotActiveError(DomainError):
    """Reserva/bloqueio já foi encerrado (liberado ou consumido)."""

    code = "HOLD_NOT_ACTIVE"

    def __init__(self, hold_id: UUID, status: str) -> None:
        super().__init__(f"Reserva/bloqueio '{hold_id}' não está ativo (status atual: {status}).")
        self.hold_id = hold_id
        self.status = status


class InvalidHoldOperationError(DomainError):
    """Operação não se aplica ao tipo de hold (ex.: consumir um bloqueio)."""

    code = "INVALID_HOLD_OPERATION"


class StockInvariantViolationError(Exception):
    """Estado interno impossível: indica bug, não erro do cliente (vira HTTP 500).

    Não herda de DomainError de propósito: não é uma regra que o cliente violou.
    """
