"""Add outbox_events table for transactional outbox pattern.

Events are written atomically within the same DB transaction as the triggering
business operation and processed by a background worker exactly once.

Revision ID: 0006_outbox_events
Revises: 0005_audit_logs
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_outbox_events"
down_revision = "0005_audit_logs"
branch_labels = None
depends_on = None


def upgrade():
    outbox_status = sa.Enum("PENDING", "PROCESSING", "DONE", "FAILED", name="outbox_event_status")
    outbox_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", outbox_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_created_at", "outbox_events", ["created_at"])


def downgrade():
    op.drop_index("ix_outbox_events_created_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_table("outbox_events")
    sa.Enum(name="outbox_event_status").drop(op.get_bind(), checkfirst=True)
