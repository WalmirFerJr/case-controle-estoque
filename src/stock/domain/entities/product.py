"""Produto: raiz de agregado que guarda os saldos e protege as invariantes do estoque."""

from dataclasses import dataclass
from datetime import datetime

from stock.domain.entities.hold import Hold, HoldType
from stock.domain.exceptions import (
    InsufficientAvailableStockError,
    StockInvariantViolationError,
    StockLimitExceededError,
)
from stock.domain.value_objects import Quantity, Sku

MAX_PRODUCT_STOCK = 1_000_000_000
"""Limite de unidades por produto: margem segura para BIGINT e para somas em relatórios."""


@dataclass(slots=True)
class Product:
    """Saldos de um produto.

    Guardamos ``total``, ``reserved`` e ``blocked``. O ``available`` é **derivado**
    (``total - reserved - blocked``) e nunca armazenado: assim é impossível ele
    divergir dos demais saldos.

    Invariantes (garantidas aqui e repetidas como CHECK no banco):
        total >= 0, reserved >= 0, blocked >= 0, reserved + blocked <= total
    """

    sku: Sku
    total: int = 0
    reserved: int = 0
    blocked: int = 0

    @classmethod
    def new(cls, sku: Sku) -> "Product":
        return cls(sku=sku)

    @property
    def available(self) -> int:
        return self.total - self.reserved - self.blocked

    # ------------------------------------------------------------------ operações

    def register_entry(self, quantity: Quantity) -> None:
        """Entrada: unidades novas chegam como disponíveis."""
        if self.total + quantity.value > MAX_PRODUCT_STOCK:
            raise StockLimitExceededError(
                f"A entrada excederia o limite de {MAX_PRODUCT_STOCK} unidades "
                f"para o produto '{self.sku}'."
            )
        self.total += quantity.value
        self._assert_invariants()

    def register_exit(self, quantity: Quantity) -> None:
        """Saída avulsa: só pode retirar do disponível (reservado/bloqueado são intocáveis)."""
        self._ensure_available(quantity)
        self.total -= quantity.value
        self._assert_invariants()

    def reserve(self, quantity: Quantity, *, reference: str, now: datetime) -> Hold:
        """Reserva unidades disponíveis para uma solicitação/pedido."""
        self._ensure_available(quantity)
        hold = Hold.create(
            sku=self.sku,
            hold_type=HoldType.RESERVATION,
            quantity=quantity,
            reference=reference,
            reason=None,
            now=now,
        )
        self.reserved += quantity.value
        self._assert_invariants()
        return hold

    def block(
        self, quantity: Quantity, *, reference: str, reason: str | None, now: datetime
    ) -> Hold:
        """Bloqueia unidades disponíveis (ex.: avaria, inspeção de qualidade)."""
        self._ensure_available(quantity)
        hold = Hold.create(
            sku=self.sku,
            hold_type=HoldType.BLOCK,
            quantity=quantity,
            reference=reference,
            reason=reason,
            now=now,
        )
        self.blocked += quantity.value
        self._assert_invariants()
        return hold

    def release(self, hold: Hold, *, now: datetime) -> None:
        """Libera um hold ativo: as unidades voltam a ficar disponíveis."""
        self._ensure_owns(hold)
        hold.release(now)
        if hold.type is HoldType.RESERVATION:
            self.reserved -= hold.quantity.value
        else:
            self.blocked -= hold.quantity.value
        self._assert_invariants()

    def consume_reservation(self, hold: Hold, *, now: datetime) -> None:
        """Baixa uma reserva: as unidades reservadas saem do estoque (pedido expedido)."""
        self._ensure_owns(hold)
        hold.consume(now)
        self.reserved -= hold.quantity.value
        self.total -= hold.quantity.value
        self._assert_invariants()

    # ------------------------------------------------------------------ regras internas

    def _ensure_available(self, quantity: Quantity) -> None:
        if quantity.value > self.available:
            raise InsufficientAvailableStockError(
                sku=self.sku.value, requested=quantity.value, available=self.available
            )

    def _ensure_owns(self, hold: Hold) -> None:
        if hold.sku != self.sku:
            raise StockInvariantViolationError(
                f"Hold {hold.id} pertence a '{hold.sku}', não a '{self.sku}'."
            )

    def _assert_invariants(self) -> None:
        """Rede de segurança: se algo escapar das validações acima, falha alto (bug)."""
        if min(self.total, self.reserved, self.blocked) < 0 or (
            self.reserved + self.blocked > self.total
        ):
            raise StockInvariantViolationError(
                f"Estado inválido para '{self.sku}': total={self.total}, "
                f"reserved={self.reserved}, blocked={self.blocked}."
            )
