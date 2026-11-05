"""Create the transactional inventory and reservation foundation.

Revision ID: 0001_inventory_reservations
Revises:
Create Date: 2026-10-02
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_inventory_reservations"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    reservation_status = sa.Enum("HELD", "CONFIRMED", "RELEASED", name="reservation_status")
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_starts_at", "events", ["starts_at"])
    op.create_table(
        "inventory",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("total_quantity", sa.Integer(), nullable=False),
        sa.Column("available_quantity", sa.Integer(), nullable=False),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False),
        sa.Column("sold_quantity", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("available_quantity >= 0", name="ck_inventory_available_nonnegative"),
        sa.CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_nonnegative"),
        sa.CheckConstraint("sold_quantity >= 0", name="ck_inventory_sold_nonnegative"),
        sa.CheckConstraint("total_quantity >= 0", name="ck_inventory_total_nonnegative"),
        sa.CheckConstraint("total_quantity = available_quantity + reserved_quantity + sold_quantity", name="ck_inventory_quantity_invariant"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_table(
        "reservations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", reservation_status, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_reservation_quantity_positive"),
        sa.CheckConstraint("status IN ('HELD', 'CONFIRMED', 'RELEASED')", name="ck_reservation_valid_status"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reservations_event_id", "reservations", ["event_id"])
    op.create_index("ix_reservations_expires_at", "reservations", ["expires_at"])
    op.create_index("ix_reservations_user_id", "reservations", ["user_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_idempotency_record_key"),
    )
    op.create_index("ix_idempotency_records_expires_at", "idempotency_records", ["expires_at"])


def downgrade():
    op.drop_index("ix_idempotency_records_expires_at", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("ix_reservations_user_id", table_name="reservations")
    op.drop_index("ix_reservations_expires_at", table_name="reservations")
    op.drop_index("ix_reservations_event_id", table_name="reservations")
    op.drop_table("reservations")
    op.drop_table("inventory")
    op.drop_index("ix_events_starts_at", table_name="events")
    op.drop_table("events")
    sa.Enum(name="reservation_status").drop(op.get_bind(), checkfirst=True)
