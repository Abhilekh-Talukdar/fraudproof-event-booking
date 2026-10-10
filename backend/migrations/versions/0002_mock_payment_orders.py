"""Add durable mock payment and order state.

Revision ID: 0002_mock_payment_orders
Revises: 0001_inventory_reservations
Create Date: 2026-10-02
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_mock_payment_orders"
down_revision = "0001_inventory_reservations"
branch_labels = None
depends_on = None


def upgrade():
    order_status = sa.Enum("PAYMENT_PENDING", "PAID", "PAYMENT_FAILED", name="order_status")
    order_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reservation_id", sa.String(length=36), nullable=False),
        sa.Column("status", order_status, nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payment_reference", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_order_amount_nonnegative"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_reference"),
        sa.UniqueConstraint("reservation_id", name="uq_order_reservation"),
    )
    op.create_table(
        "payment_idempotency_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_payment_idempotency_key"),
    )
    op.create_index("ix_payment_idempotency_records_expires_at", "payment_idempotency_records", ["expires_at"])


def downgrade():
    op.drop_index("ix_payment_idempotency_records_expires_at", table_name="payment_idempotency_records")
    op.drop_table("payment_idempotency_records")
    op.drop_table("orders")
    sa.Enum(name="order_status").drop(op.get_bind(), checkfirst=True)
