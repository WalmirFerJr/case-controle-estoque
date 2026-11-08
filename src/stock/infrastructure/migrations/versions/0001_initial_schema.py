"""Schema inicial: produtos, holds (reservas/bloqueios) e ledger de movimentos.

Revision ID: 0001
Revises:
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("total_quantity", sa.BigInteger(), nullable=False),
        sa.Column("reserved_quantity", sa.BigInteger(), nullable=False),
        sa.Column("blocked_quantity", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("sku", name="pk_products"),
        sa.CheckConstraint("total_quantity >= 0", name="ck_products_total_non_negative"),
        sa.CheckConstraint("reserved_quantity >= 0", name="ck_products_reserved_non_negative"),
        sa.CheckConstraint("blocked_quantity >= 0", name="ck_products_blocked_non_negative"),
        sa.CheckConstraint(
            "reserved_quantity + blocked_quantity <= total_quantity",
            name="ck_products_holds_within_total",
        ),
    )

    op.create_table(
        "holds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("reference", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_holds"),
        sa.ForeignKeyConstraint(["sku"], ["products.sku"], name="fk_holds_sku_products"),
        sa.CheckConstraint("quantity > 0", name="ck_holds_quantity_positive"),
        sa.CheckConstraint("type IN ('RESERVATION', 'BLOCK')", name="ck_holds_type_valid"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'RELEASED', 'CONSUMED')", name="ck_holds_status_valid"
        ),
        sa.CheckConstraint(
            "(status = 'ACTIVE') = (closed_at IS NULL)", name="ck_holds_closed_at_matches"
        ),
        sa.CheckConstraint(
            "status <> 'CONSUMED' OR type = 'RESERVATION'",
            name="ck_holds_only_reservations_consumed",
        ),
    )
    op.create_index("ix_holds_sku_status", "holds", ["sku", "status"])
    op.create_index("ix_holds_reference", "holds", ["reference"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("hold_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_stock_movements"),
        sa.ForeignKeyConstraint(["sku"], ["products.sku"], name="fk_stock_movements_sku_products"),
        sa.ForeignKeyConstraint(["hold_id"], ["holds.id"], name="fk_stock_movements_hold_id_holds"),
        sa.CheckConstraint("quantity > 0", name="ck_stock_movements_quantity_positive"),
        sa.CheckConstraint(
            "type IN ('ENTRY', 'EXIT', 'RESERVE', 'BLOCK', 'RELEASE_RESERVATION', "
            "'RELEASE_BLOCK', 'CONSUME_RESERVATION')",
            name="ck_stock_movements_type_valid",
        ),
    )
    op.create_index("ix_stock_movements_sku_occurred_at", "stock_movements", ["sku", "occurred_at"])


def downgrade() -> None:
    op.drop_table("stock_movements")
    op.drop_table("holds")
    op.drop_table("products")
