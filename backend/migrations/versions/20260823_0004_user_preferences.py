"""add per-user preferences for proactive assistant behavior

Revision ID: 20260823_0004
Revises: 20260820_0003
Create Date: 2026-08-23
"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "20260823_0004"
down_revision: str | Sequence[str] | None = "20260820_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not op.get_context().as_sql and sa.inspect(op.get_bind()).has_table("user_preferences"):
        return

    op.create_table(
        "user_preferences",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.UniqueConstraint("user_id", "key", name="uk_user_preferences_user_key"),
    )
    op.create_index("idx_user_preferences_user", "user_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_user_preferences_user", table_name="user_preferences")
    op.drop_table("user_preferences")
