"""Add application identities and roles.

Revision ID: 0004_users_and_session_auth
Revises: 0003_signed_tickets
Create Date: 2026-10-02
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_users_and_session_auth"
down_revision = "0003_signed_tickets"
branch_labels = None
depends_on = None


def upgrade():
    user_role = sa.Enum("USER", "ORGANIZER", "SCANNER", "ADMIN", name="user_role")
    user_status = sa.Enum("ACTIVE", "DISABLED", name="user_status")
    user_role.create(op.get_bind(), checkfirst=True)
    user_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("status", user_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )


def downgrade():
    op.drop_table("users")
    sa.Enum(name="user_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
