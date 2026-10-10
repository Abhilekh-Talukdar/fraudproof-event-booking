"""Add signed ticket records and reservation attendee names.

Revision ID: 0003_signed_tickets
Revises: 0002_mock_payment_orders
Create Date: 2026-10-02
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_signed_tickets"
down_revision = "0002_mock_payment_orders"
branch_labels = None
depends_on = None


def upgrade():
    ticket_status = sa.Enum("ISSUED", "USED", "REVOKED", name="ticket_status")
    ticket_status.create(op.get_bind(), checkfirst=True)
    op.add_column("reservations", sa.Column("attendee_names", sa.JSON(), nullable=True))
    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("holder_name", sa.String(length=200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_ticket_version_positive"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nonce"),
    )
    op.create_index("ix_tickets_event_id", "tickets", ["event_id"])
    op.create_index("ix_tickets_expires_at", "tickets", ["expires_at"])
    op.create_index("ix_tickets_order_id", "tickets", ["order_id"])


def downgrade():
    op.drop_index("ix_tickets_order_id", table_name="tickets")
    op.drop_index("ix_tickets_expires_at", table_name="tickets")
    op.drop_index("ix_tickets_event_id", table_name="tickets")
    op.drop_table("tickets")
    op.drop_column("reservations", "attendee_names")
    sa.Enum(name="ticket_status").drop(op.get_bind(), checkfirst=True)
