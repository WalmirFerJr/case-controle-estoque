"""Mapeamento ORM. Separado das entidades de domínio de propósito (ver ADR-0002).

As CHECK constraints repetem as invariantes do domínio: são a última linha de
defesa caso algum código (ou alguém via SQL) tente gravar um estado impossível.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ProductModel(Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(64), primary_key=True)
    total_quantity: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_quantity: Mapped[int] = mapped_column(BigInteger, default=0)
    blocked_quantity: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("total_quantity >= 0", name="total_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="reserved_non_negative"),
        CheckConstraint("blocked_quantity >= 0", name="blocked_non_negative"),
        CheckConstraint(
            "reserved_quantity + blocked_quantity <= total_quantity", name="holds_within_total"
        ),
    )


class HoldModel(Base):
    __tablename__ = "holds"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[int] = mapped_column(BigInteger)
    reference: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("type IN ('RESERVATION', 'BLOCK')", name="type_valid"),
        CheckConstraint("status IN ('ACTIVE', 'RELEASED', 'CONSUMED')", name="status_valid"),
        CheckConstraint("(status = 'ACTIVE') = (closed_at IS NULL)", name="closed_at_matches"),
        CheckConstraint(
            "status <> 'CONSUMED' OR type = 'RESERVATION'", name="only_reservations_consumed"
        ),
        Index(None, "sku", "status"),
        Index(None, "reference"),
    )


class StockMovementModel(Base):
    __tablename__ = "stock_movements"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    type: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[int] = mapped_column(BigInteger)
    hold_id: Mapped[UUID | None] = mapped_column(ForeignKey("holds.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "type IN ('ENTRY', 'EXIT', 'RESERVE', 'BLOCK', 'RELEASE_RESERVATION', "
            "'RELEASE_BLOCK', 'CONSUME_RESERVATION')",
            name="type_valid",
        ),
        Index(None, "sku", "occurred_at"),
    )
