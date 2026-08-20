"""add observable LLM call log

Revision ID: 20260820_0002
Revises: 20260820_0001
Create Date: 2026-08-20
"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "20260820_0002"
down_revision: str | Sequence[str] | None = "20260820_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_call_log",
        sa.Column("conversation_id", sa.CHAR(length=36), nullable=True),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt_tokens", mysql.INTEGER(unsigned=True), server_default=sa.text("0"), nullable=False),
        sa.Column("completion_tokens", mysql.INTEGER(unsigned=True), server_default=sa.text("0"), nullable=False),
        sa.Column("total_tokens", mysql.INTEGER(unsigned=True), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", mysql.INTEGER(unsigned=True), server_default=sa.text("0"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_llm_call_log_agent_time", "llm_call_log", ["agent_name", "created_at"])
    op.create_index("idx_llm_call_log_conversation", "llm_call_log", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_llm_call_log_conversation", table_name="llm_call_log")
    op.drop_index("idx_llm_call_log_agent_time", table_name="llm_call_log")
    op.drop_table("llm_call_log")
