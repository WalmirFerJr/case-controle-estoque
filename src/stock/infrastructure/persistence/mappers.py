"""Conversão entre modelos ORM e entidades de domínio."""

from stock.domain.entities import Hold, HoldStatus, HoldType, Product, StockMovement
from stock.domain.entities.stock_movement import MovementType
from stock.domain.value_objects import Quantity, Sku
from stock.infrastructure.persistence.models import HoldModel, ProductModel, StockMovementModel


def product_to_entity(model: ProductModel) -> Product:
    return Product(
        sku=Sku(model.sku),
        total=model.total_quantity,
        reserved=model.reserved_quantity,
        blocked=model.blocked_quantity,
    )


def hold_to_entity(model: HoldModel) -> Hold:
    return Hold(
        id=model.id,
        sku=Sku(model.sku),
        type=HoldType(model.type),
        quantity=Quantity(model.quantity),
        reference=model.reference,
        reason=model.reason,
        status=HoldStatus(model.status),
        created_at=model.created_at,
        closed_at=model.closed_at,
    )


def hold_to_model(hold: Hold) -> HoldModel:
    return HoldModel(
        id=hold.id,
        sku=hold.sku.value,
        type=hold.type.value,
        status=hold.status.value,
        quantity=hold.quantity.value,
        reference=hold.reference,
        reason=hold.reason,
        created_at=hold.created_at,
        closed_at=hold.closed_at,
    )


def movement_to_entity(model: StockMovementModel) -> StockMovement:
    return StockMovement(
        id=model.id,
        sku=Sku(model.sku),
        type=MovementType(model.type),
        quantity=Quantity(model.quantity),
        hold_id=model.hold_id,
        occurred_at=model.occurred_at,
    )


def movement_to_model(movement: StockMovement) -> StockMovementModel:
    return StockMovementModel(
        id=movement.id,
        sku=movement.sku.value,
        type=movement.type.value,
        quantity=movement.quantity.value,
        hold_id=movement.hold_id,
        occurred_at=movement.occurred_at,
    )
