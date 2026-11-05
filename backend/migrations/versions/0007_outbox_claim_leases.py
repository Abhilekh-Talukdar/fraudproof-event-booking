"""Add claim leases to outbox events.

Revision ID: 0007_outbox_claim_leases
Revises: 0006_outbox_events
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_outbox_claim_leases"
down_revision = "0006_outbox_events"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "outbox_events",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("claim_token", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_outbox_events_status_claimed_at",
        "outbox_events",
        ["status", "claimed_at"],
    )


def downgrade():
    op.drop_index("ix_outbox_events_status_claimed_at", table_name="outbox_events")
    op.drop_column("outbox_events", "claim_token")
    op.drop_column("outbox_events", "claimed_at")
