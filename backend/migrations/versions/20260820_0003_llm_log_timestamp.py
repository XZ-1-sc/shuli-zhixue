"""align LLM log timestamp with ORM metadata

Revision ID: 20260820_0003
Revises: 20260820_0002
Create Date: 2026-08-20
"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "20260820_0003"
down_revision: str | Sequence[str] | None = "20260820_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "llm_call_log",
        "created_at",
        existing_type=mysql.DATETIME(),
        type_=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def downgrade() -> None:
    op.alter_column(
        "llm_call_log",
        "created_at",
        existing_type=sa.TIMESTAMP(),
        type_=mysql.DATETIME(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
