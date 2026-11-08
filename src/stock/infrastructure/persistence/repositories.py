"""Implementações SQLAlchemy dos ports de repositório."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from stock.application.ports import HoldFilters
from stock.domain.entities import Hold, Product, StockMovement
from stock.domain.value_objects import Sku
from stock.infrastructure.persistence.mappers import (
    hold_to_entity,
    hold_to_model,
    movement_to_entity,
    movement_to_model,
    product_to_entity,
)
from stock.infrastructure.persistence.models import HoldModel, ProductModel, StockMovementModel


class SqlAlchemyProductRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, sku: Sku) -> Product | None:
        model = self._session.scalar(select(ProductModel).where(ProductModel.sku == sku.value))
        return product_to_entity(model) if model else None

    def get_for_update(self, sku: Sku) -> Product | None:
        # SELECT ... FOR UPDATE: outras transações que queiram alterar este produto
        # esperam este commit/rollback. populate_existing garante dados frescos
        # mesmo se o objeto já estiver no identity map da sessão.
        stmt = (
            select(ProductModel)
            .where(ProductModel.sku == sku.value)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = self._session.scalar(stmt)
        return product_to_entity(model) if model else None

    def add_if_absent(self, product: Product) -> None:
        # INSERT ... ON CONFLICT DO NOTHING: duas primeiras entradas simultâneas do
        # mesmo SKU não geram erro de chave duplicada; ambas seguem para o lock.
        stmt = (
            insert(ProductModel)
            .values(
                sku=product.sku.value,
                total_quantity=product.total,
                reserved_quantity=product.reserved,
                blocked_quantity=product.blocked,
            )
            .on_conflict_do_nothing(index_elements=[ProductModel.sku])
        )
        self._session.execute(stmt)

    def save(self, product: Product) -> None:
        model = self._session.get(ProductModel, product.sku.value)
        if model is None:
            model = ProductModel(sku=product.sku.value)
            self._session.add(model)
        model.total_quantity = product.total
        model.reserved_quantity = product.reserved
        model.blocked_quantity = product.blocked
        self._session.flush()


class SqlAlchemyHoldRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, hold_id: UUID) -> Hold | None:
        model = self._session.scalar(select(HoldModel).where(HoldModel.id == hold_id))
        return hold_to_entity(model) if model else None

    def get_for_update(self, hold_id: UUID) -> Hold | None:
        stmt = (
            select(HoldModel)
            .where(HoldModel.id == hold_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = self._session.scalar(stmt)
        return hold_to_entity(model) if model else None

    def add(self, hold: Hold) -> None:
        self._session.add(hold_to_model(hold))
        self._session.flush()

    def save(self, hold: Hold) -> None:
        model = self._session.get(HoldModel, hold.id)
        if model is None:
            self.add(hold)
            return
        model.status = hold.status.value
        model.closed_at = hold.closed_at
        self._session.flush()

    def list(self, filters: HoldFilters) -> Sequence[Hold]:
        stmt = select(HoldModel)
        if filters.sku is not None:
            stmt = stmt.where(HoldModel.sku == filters.sku.value)
        if filters.reference is not None:
            stmt = stmt.where(HoldModel.reference == filters.reference)
        if filters.hold_type is not None:
            stmt = stmt.where(HoldModel.type == filters.hold_type.value)
        if filters.status is not None:
            stmt = stmt.where(HoldModel.status == filters.status.value)
        stmt = (
            stmt.order_by(HoldModel.created_at, HoldModel.id)
            .limit(filters.limit)
            .offset(filters.offset)
        )
        return [hold_to_entity(model) for model in self._session.scalars(stmt)]


class SqlAlchemyMovementRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, movement: StockMovement) -> None:
        self._session.add(movement_to_model(movement))
        self._session.flush()

    def list_by_sku(self, sku: Sku, *, limit: int, offset: int) -> Sequence[StockMovement]:
        stmt = (
            select(StockMovementModel)
            .where(StockMovementModel.sku == sku.value)
            .order_by(StockMovementModel.occurred_at, StockMovementModel.id)
            .limit(limit)
            .offset(offset)
        )
        return [movement_to_entity(model) for model in self._session.scalars(stmt)]
