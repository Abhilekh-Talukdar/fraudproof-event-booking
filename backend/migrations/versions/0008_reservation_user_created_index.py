"""Index the reservation abuse-detection lookup.

Revision ID: 0008_reservation_user_created_index
Revises: 0007_outbox_claim_leases
Create Date: 2026-11-13
"""
from alembic import op


revision = "0008_reservation_user_created_index"
down_revision = "0007_outbox_claim_leases"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_reservations_user_created_at",
        "reservations",
        ["user_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_reservations_user_created_at", table_name="reservations")
